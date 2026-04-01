"""Tests for SSH connection pool and host key policy builder."""

import os
import sys
import logging
import queue
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

pytestmark = pytest.mark.skipif(not HAS_PARAMIKO, reason="paramiko not installed")

from ssh import _build_host_key_policy, AsyncSSHPool
from config import SSHConfig


class TestBuildHostKeyPolicy:
    def test_reject_returns_reject_policy(self):
        assert isinstance(_build_host_key_policy("reject"), paramiko.RejectPolicy)

    def test_system_returns_warning_policy(self):
        assert isinstance(_build_host_key_policy("system"), paramiko.WarningPolicy)

    def test_auto_returns_auto_add_policy(self):
        assert isinstance(_build_host_key_policy("auto"), paramiko.AutoAddPolicy)

    def test_unknown_falls_back_to_reject(self):
        assert isinstance(_build_host_key_policy("unknown"), paramiko.RejectPolicy)

    def test_auto_logs_deprecation_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="ssh"):
            _build_host_key_policy("auto")
        assert any("DEPRECATED" in m for m in caplog.messages)

    def test_unknown_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="ssh"):
            _build_host_key_policy("nonsense")
        assert any("Unknown host_key_policy" in m for m in caplog.messages)


class TestAsyncSSHPool:
    @pytest.fixture
    def ssh_config(self):
        return SSHConfig(
            host="192.168.1.1",
            port=22,
            user="root",
            password="secret",
            host_key_policy="reject",
        )

    def test_init(self, ssh_config):
        pool = AsyncSSHPool(ssh_config, max_connections=2)
        assert pool._closed is False
        assert pool._pool.maxsize == 2

    def test_release_to_pool(self, ssh_config):
        pool = AsyncSSHPool(ssh_config, max_connections=4)
        mock_client = MagicMock()
        pool._release(mock_client)
        assert pool._pool.qsize() == 1

    def test_release_when_closed_closes_client(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        pool._closed = True
        mock_client = MagicMock()
        pool._release(mock_client)
        mock_client.close.assert_called_once()

    def test_release_when_full_closes_client(self, ssh_config):
        pool = AsyncSSHPool(ssh_config, max_connections=1)
        pool._pool.put(MagicMock())  # fill the pool
        extra = MagicMock()
        pool._release(extra)
        extra.close.assert_called_once()

    def test_discard_closes_silently(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        mock_client = MagicMock()
        pool._discard(mock_client)
        mock_client.close.assert_called_once()

    def test_discard_handles_exception(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        mock_client = MagicMock()
        mock_client.close.side_effect = OSError("fail")
        pool._discard(mock_client)  # should not raise

    def test_is_alive_true(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_transport.send_ignore.return_value = None
        mock_client.get_transport.return_value = mock_transport
        assert pool._is_alive(mock_client) is True

    def test_is_alive_no_transport(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        mock_client = MagicMock()
        mock_client.get_transport.return_value = None
        assert pool._is_alive(mock_client) is False

    def test_is_alive_inactive_transport(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = False
        mock_client.get_transport.return_value = mock_transport
        assert pool._is_alive(mock_client) is False

    def test_is_alive_send_ignore_fails(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_transport.send_ignore.side_effect = OSError("dead")
        mock_client.get_transport.return_value = mock_transport
        assert pool._is_alive(mock_client) is False

    def test_acquire_reuses_alive_client(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_transport.send_ignore.return_value = None
        mock_client.get_transport.return_value = mock_transport
        pool._pool.put(mock_client)
        result = pool._acquire()
        assert result is mock_client

    def test_acquire_discards_dead_client(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        dead_client = MagicMock()
        dead_client.get_transport.return_value = None
        pool._pool.put(dead_client)

        with patch.object(pool, '_create_new') as mock_create:
            fresh = MagicMock()
            mock_create.return_value = fresh
            result = pool._acquire()
            assert result is fresh
            dead_client.close.assert_called_once()

    async def test_close_all(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        c1, c2 = MagicMock(), MagicMock()
        pool._pool.put(c1)
        pool._pool.put(c2)
        await pool.close_all()
        assert pool._closed is True
        c1.close.assert_called_once()
        c2.close.assert_called_once()

    def test_run_sync_success(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        mock_client = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""
        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        with patch.object(pool, '_acquire', return_value=mock_client):
            with patch.object(pool, '_release') as mock_release:
                result = pool._run_sync("echo hi", 30)
                assert result == "output"
                mock_release.assert_called_once_with(mock_client)

    def test_run_sync_failure_discards(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        mock_client = MagicMock()
        mock_client.exec_command.side_effect = paramiko.SSHException("fail")

        with patch.object(pool, '_acquire', return_value=mock_client):
            with patch.object(pool, '_discard') as mock_discard:
                result = pool._run_sync("bad cmd", 30)
                assert result is None
                mock_discard.assert_called_once_with(mock_client)

    def test_run_sync_nonzero_exit(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        mock_client = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"error"
        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        with patch.object(pool, '_acquire', return_value=mock_client):
            with patch.object(pool, '_release') as mock_release:
                result = pool._run_sync("fail cmd", 30)
                assert result is None
                mock_release.assert_called_once()

    async def test_run_command_async(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        with patch.object(pool, '_run_sync', return_value="async output"):
            result = await pool.run_command("echo test", 30)
            assert result == "async output"

    async def test_run_command_list_joined(self, ssh_config):
        pool = AsyncSSHPool(ssh_config)
        with patch.object(pool, '_run_sync', return_value="ok") as mock_sync:
            await pool.run_command(["pct", "list"], 30)
            mock_sync.assert_called_once()
            cmd_arg = mock_sync.call_args[0][0]
            assert "pct" in cmd_arg and "list" in cmd_arg
