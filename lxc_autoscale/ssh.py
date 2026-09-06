"""SSH connection pool with configurable host key verification (async).

Provides ``AsyncSSHPool`` that wraps paramiko in ``asyncio.to_thread``
for non-blocking SSH operations. Falls back gracefully if asyncssh
is not available.
"""

import asyncio
import logging
import queue
import shlex
from threading import Lock
from typing import List, Optional, Union

try:
    import paramiko
except ImportError:
    paramiko = None  # type: ignore[assignment]

from config import SSHConfig

logger = logging.getLogger(__name__)


def _build_host_key_policy(name: str) -> "paramiko.MissingHostKeyPolicy":
    """Map config string to a Paramiko host-key policy.

    ``"reject"`` (default) — refuse unknown hosts (safe).
    ``"system"`` — warn on unknown but allow, load system known_hosts.
    ``"auto"``  — blindly accept (legacy behavior, NOT recommended).
    """
    if paramiko is None:
        raise RuntimeError("paramiko is not installed")
    policies = {
        "reject": paramiko.RejectPolicy,
        "system": paramiko.WarningPolicy,
        "auto": paramiko.AutoAddPolicy,  # DEPRECATED — see warning below
    }
    cls = policies.get(name)
    if cls is None:
        logger.warning("Unknown host_key_policy %r, falling back to RejectPolicy", name)
        cls = paramiko.RejectPolicy
    if name == "auto":
        logger.warning(
            "SECURITY WARNING: ssh_host_key_policy='auto' accepts ANY SSH host key. "
            "This is vulnerable to Man-in-the-Middle attacks. "
            "Use 'reject' (default) or 'system' instead, and provide a known_hosts file. "
            "The 'auto' policy is DEPRECATED and will be removed in a future version."
        )
    return cls()


class AsyncSSHPool:
    """Async-compatible SSH connection pool wrapping paramiko in threads.

    All I/O is delegated to ``asyncio.to_thread`` so the event loop
    never blocks on SSH operations.
    """

    def __init__(self, ssh_config: SSHConfig, max_connections: int = 4):
        if paramiko is None:
            raise RuntimeError("paramiko is not installed — SSH backend unavailable")
        self._config = ssh_config
        self._pool: queue.Queue[paramiko.SSHClient] = queue.Queue(maxsize=max_connections)
        self._lock = Lock()
        self._closed = False

    async def run_command(self, cmd: Union[str, List[str]], timeout: int = 30) -> Optional[str]:
        """Execute a command on the remote host (async, non-blocking)."""
        if isinstance(cmd, list):
            cmd = shlex.join(cmd)
        return await asyncio.to_thread(self._run_sync, cmd, timeout)

    async def run_command_with_input(
        self, cmd: Union[str, List[str]], data: str, timeout: int = 30,
    ) -> bool:
        """
        Execute a command on the remote host, feeding it `data` on stdin.

        Writing a file remotely needs the content to reach the far side without
        going through the shell: a here-document or an echo would interpolate
        it. This sends it down the channel's stdin instead, so nothing in the
        payload is ever parsed as a command.

        Args:
            cmd: The command to run.
            data: What to write to its standard input.
            timeout: Seconds to wait.

        Returns:
            True when the command exited zero.
        """
        if isinstance(cmd, list):
            cmd = shlex.join(cmd)
        return await asyncio.to_thread(self._run_sync_with_input, cmd, data, timeout)

    def _run_sync_with_input(self, cmd: str, data: str, timeout: int) -> bool:
        """Synchronous stdin-fed SSH execution (called in a thread)."""
        logger.debug("SSH command with input: %s (%d bytes)", cmd, len(data))
        client = self._acquire()
        try:
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            stdin.write(data)
            stdin.flush()
            stdin.channel.shutdown_write()
            # stdout has to be drained before waiting for the exit status.
            # `tee` echoes its input, so on a config large enough to fill the
            # channel window the remote command blocks writing, never exits,
            # and recv_exit_status() waits for it forever. Reading stderr first
            # does not help: it returns at EOF, which only arrives when the
            # command exits.
            stdout.read()
            err = stderr.read().decode("utf-8").strip()
            exit_code = stdout.channel.recv_exit_status()
            self._release(client)
            if exit_code != 0:
                logger.error("SSH command failed (rc=%d): %s — %s", exit_code, cmd, err)
                return False
            return True
        except paramiko.SSHException as e:
            logger.error("SSH execution failed: %s", e)
            self._discard(client)
        except OSError as e:
            logger.error("SSH connection error: %s", e)
            self._discard(client)
        return False

    def _run_sync(self, cmd: str, timeout: int) -> Optional[str]:
        """Synchronous SSH command execution (called in a thread)."""
        logger.debug("SSH command: %s", cmd)
        client = self._acquire()
        try:
            _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            output = stdout.read().decode("utf-8").strip()
            err = stderr.read().decode("utf-8").strip()
            exit_code = stdout.channel.recv_exit_status()
            if exit_code != 0:
                logger.error("SSH command failed (rc=%d): %s — %s", exit_code, cmd, err)
                self._release(client)
                return None
            logger.debug("SSH command OK: %s", output[:200])
            self._release(client)
            return output
        except paramiko.SSHException as e:
            logger.error("SSH execution failed: %s", e)
            self._discard(client)
        except OSError as e:
            logger.error("SSH connection error: %s", e)
            self._discard(client)
        return None

    async def close_all(self) -> None:
        """Close all pooled connections."""
        self._closed = True
        while not self._pool.empty():
            try:
                client = self._pool.get_nowait()
                client.close()
            except queue.Empty:
                break
        logger.debug("SSH pool closed")

    # -- internals -----------------------------------------------------------

    def _acquire(self) -> "paramiko.SSHClient":
        while not self._pool.empty():
            try:
                client = self._pool.get_nowait()
            except queue.Empty:
                break
            if self._is_alive(client):
                return client
            client.close()
        return self._create_new()

    def _release(self, client: "paramiko.SSHClient") -> None:
        if self._closed:
            client.close()
            return
        try:
            self._pool.put_nowait(client)
        except queue.Full:
            client.close()

    def _discard(self, client: "paramiko.SSHClient") -> None:
        try:
            client.close()
        except Exception:
            pass

    def _create_new(self) -> "paramiko.SSHClient":
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(
            _build_host_key_policy(self._config.host_key_policy)
        )
        connect_kwargs = {
            "hostname": self._config.host,
            "port": self._config.port,
            "username": self._config.user,
            "timeout": 10,
        }
        if self._config.password:
            connect_kwargs["password"] = self._config.password
        if self._config.key_path:
            connect_kwargs["key_filename"] = self._config.key_path
        ssh.connect(**connect_kwargs)
        logger.info("SSH connection established to %s:%d", self._config.host, self._config.port)
        return ssh

    @staticmethod
    def _is_alive(client: "paramiko.SSHClient") -> bool:
        transport = client.get_transport()
        if transport is None or not transport.is_active():
            return False
        try:
            transport.send_ignore()
            return True
        except Exception:
            return False
