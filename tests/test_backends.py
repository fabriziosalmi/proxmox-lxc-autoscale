"""Tests for backend abstraction layer (async)."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

from backends.base import ProxmoxBackend
from backends.cli import CLIBackend, _validate_ctid


class TestValidateCtid:
    def test_valid_numeric(self):
        _validate_ctid("100")
        _validate_ctid("0")
        _validate_ctid("999999")

    def test_invalid_alpha(self):
        with pytest.raises(ValueError):
            _validate_ctid("abc")

    def test_invalid_injection(self):
        with pytest.raises(ValueError):
            _validate_ctid("100; rm -rf /")

    def test_invalid_empty(self):
        with pytest.raises(ValueError):
            _validate_ctid("")


class TestCLIBackend:
    """Test CLI backend with mocked async subprocess."""

    @pytest.fixture
    def mock_config(self):
        cfg = MagicMock()
        cfg.defaults.use_remote_proxmox = False
        cfg.defaults.timeout_extended = 300
        return cfg

    @pytest.fixture
    def backend(self, mock_config):
        return CLIBackend(mock_config)

    @pytest.mark.asyncio
    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_list_containers(self, mock_run, backend):
        mock_run.return_value = (
            "VMID       Status     Lock         Name\n"
            "100        running                 ct100\n"
            "101        stopped                 ct101\n"
            "102        running                 ct102\n"
        )
        result = await backend.list_containers()
        assert result == ["100", "101", "102"]

    @pytest.mark.asyncio
    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_list_containers_empty(self, mock_run, backend):
        mock_run.return_value = None
        assert await backend.list_containers() == []

    @pytest.mark.asyncio
    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_is_running_true(self, mock_run, backend):
        mock_run.return_value = "status: running"
        assert await backend.is_running("100") is True

    @pytest.mark.asyncio
    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_is_running_false(self, mock_run, backend):
        mock_run.return_value = "status: stopped"
        assert await backend.is_running("100") is False

    @pytest.mark.asyncio
    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_set_cores(self, mock_run, backend):
        mock_run.return_value = ""
        assert await backend.set_cores("100", 4) is True
        mock_run.assert_called_once_with(
            ["pct", "set", "100", "-cores", "4"], 30
        )

    @pytest.mark.asyncio
    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_set_memory(self, mock_run, backend):
        mock_run.return_value = ""
        assert await backend.set_memory("100", 2048) is True
        mock_run.assert_called_once_with(
            ["pct", "set", "100", "-memory", "2048"], 30
        )

    @pytest.mark.asyncio
    async def test_set_cores_invalid_ctid(self, backend):
        with pytest.raises(ValueError):
            await backend.set_cores("abc", 4)

    @pytest.mark.asyncio
    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_get_container_config(self, mock_run, backend):
        mock_run.return_value = (
            "arch: amd64\n"
            "cores: 2\n"
            "memory: 1024\n"
            "hostname: test\n"
        )
        cfg = await backend.get_container_config("100")
        assert cfg['cores'] == 2
        assert cfg['memory'] == 1024

    @pytest.mark.asyncio
    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_snapshot(self, mock_run, backend):
        mock_run.return_value = ""
        assert await backend.snapshot("100", "snap1", "test snapshot") is True

    @pytest.mark.asyncio
    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_clone(self, mock_run, backend):
        mock_run.return_value = ""
        assert await backend.clone("100", "200", snapname="snap1", hostname="clone-1") is True


class TestProxmoxBackendAbstract:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ProxmoxBackend()
