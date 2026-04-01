"""CLI backend — executes Proxmox operations via ``pct`` commands (async).

Supports both local execution (asyncio subprocess) and remote execution
(async SSH pool). This is the default backend.
"""

import asyncio
import logging
import re
import shlex
from typing import Any, Dict, List, Optional, Union

from backends.base import ProxmoxBackend

logger = logging.getLogger(__name__)

_CTID_RE = re.compile(r"^[0-9]+$")


def _validate_ctid(ctid: str) -> None:
    if not _CTID_RE.match(ctid):
        raise ValueError(f"Invalid container ID: {ctid!r}")


class CLIBackend(ProxmoxBackend):
    """Proxmox backend using ``pct`` CLI commands (async)."""

    def __init__(self, app_config):
        self._config = app_config
        self._ssh_pool = None
        self._use_remote = app_config.defaults.use_remote_proxmox

        if self._use_remote:
            from ssh import AsyncSSHPool
            ssh_cfg = app_config.defaults.get_ssh_config()
            self._ssh_pool = AsyncSSHPool(ssh_cfg)

    # -- command execution ---------------------------------------------------

    async def run_raw(self, cmd: Union[str, List[str]], timeout: int = 30) -> Optional[str]:
        if self._use_remote and self._ssh_pool:
            return await self._ssh_pool.run_command(cmd, timeout)
        return await self._run_local(cmd, timeout)

    @staticmethod
    async def _run_local(cmd: Union[str, List[str]], timeout: int = 30) -> Optional[str]:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if proc.returncode == 0:
                result = stdout.decode("utf-8").strip()
                logger.debug("Command OK: %s", cmd)
                return result
            else:
                logger.error("Command failed (rc=%d): %s — %s",
                             proc.returncode, cmd, stderr.decode("utf-8").strip())
        except asyncio.TimeoutError:
            logger.error("Command timed out after %ds: %s", timeout, cmd)
            proc.kill()
            await proc.wait()
        except OSError as e:
            logger.error("OS error executing %s: %s", cmd, e)
        return None

    # -- ProxmoxBackend interface --------------------------------------------

    async def list_containers(self) -> List[str]:
        output = await self.run_raw(["pct", "list"])
        if not output:
            return []
        containers = []
        for line in output.splitlines()[1:]:
            parts = line.split()
            if parts and _CTID_RE.match(parts[0]):
                containers.append(parts[0])
        return containers

    async def get_container_config(self, ctid: str) -> Optional[Dict[str, Any]]:
        _validate_ctid(ctid)
        output = await self.run_raw(["pct", "config", ctid])
        if not output:
            return None
        cfg: Dict[str, Any] = {}
        for line in output.splitlines():
            if ":" not in line:
                continue
            key, value = [x.strip() for x in line.split(":", 1)]
            if key == "cores":
                cfg["cores"] = int(value)
            elif key == "memory":
                cfg["memory"] = int(value)
            else:
                cfg[key] = value
        return cfg

    async def is_running(self, ctid: str) -> bool:
        _validate_ctid(ctid)
        status = await self.run_raw(["pct", "status", ctid])
        return bool(status and "status: running" in status.lower())

    async def set_cores(self, ctid: str, cores: int) -> bool:
        _validate_ctid(ctid)
        return await self.run_raw(["pct", "set", ctid, "-cores", str(cores)]) is not None

    async def set_memory(self, ctid: str, memory_mb: int) -> bool:
        _validate_ctid(ctid)
        return await self.run_raw(["pct", "set", ctid, "-memory", str(memory_mb)]) is not None

    async def start(self, ctid: str) -> bool:
        _validate_ctid(ctid)
        return await self.run_raw(["pct", "start", ctid]) is not None

    async def stop(self, ctid: str) -> bool:
        _validate_ctid(ctid)
        return await self.run_raw(["pct", "stop", ctid]) is not None

    async def snapshot(self, ctid: str, name: str, description: str = "") -> bool:
        _validate_ctid(ctid)
        cmd = ["pct", "snapshot", ctid, name]
        if description:
            cmd += ["--description", description]
        return await self.run_raw(cmd) is not None

    async def clone(self, source: str, target: str, snapname: str = "",
                    hostname: str = "") -> bool:
        _validate_ctid(source)
        _validate_ctid(target)
        cmd = ["pct", "clone", source, target]
        if snapname:
            cmd += ["--snapname", snapname]
        if hostname:
            cmd += ["--hostname", hostname]
        timeout = self._config.defaults.timeout_extended
        return await self.run_raw(cmd, timeout=timeout) is not None

    async def set_network(self, ctid: str, net_config: str) -> bool:
        _validate_ctid(ctid)
        return await self.run_raw(["pct", "set", ctid, "-net0", net_config]) is not None

    async def get_status(self, ctid: str) -> Optional[str]:
        _validate_ctid(ctid)
        return await self.run_raw(["pct", "status", ctid])

    async def close(self) -> None:
        """Clean up SSH pool if remote mode was used."""
        if self._ssh_pool:
            await self._ssh_pool.close_all()
