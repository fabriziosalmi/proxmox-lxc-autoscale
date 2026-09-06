"""Tests for backend factory and CLI backend edge cases."""

import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

from backends import create_backend
from backends.cli import CLIBackend


class TestCreateBackend:
    def test_default_returns_cli(self):
        cfg = MagicMock()
        cfg.defaults.backend = "cli"
        cfg.defaults.use_remote_proxmox = False
        backend = create_backend(cfg)
        assert isinstance(backend, CLIBackend)

    def test_api_backend_requires_proxmoxer(self):
        """
        backend: api without proxmoxer installed must say so, not fail later.

        This used to simulate the missing package with
        `patch.dict('sys.modules', {'proxmoxer': None})`, inside a try/except
        that swallowed three exception types and asserted nothing, so the test
        passed whatever happened, including on a success.

        It also broke a different test. `patch.dict` restores a dict by clearing
        it and writing the snapshot back, so every module first imported inside
        the block is dropped from `sys.modules` on exit while the parent package
        keeps its attribute pointing at the old object. `backends.api` is
        imported inside the block, and afterwards
        `patch('backends.api.ProxmoxAPI')` and `import backends.api` no longer
        resolve to the same module: the patch lands on one, the code under test
        reads the other. `TestRESTBackend` then ran against the real proxmoxer
        and opened an HTTPS connection to the address in its own fixture,
        waiting five seconds for it to time out.

        Setting the name the module actually reads is enough, and it leaves
        `sys.modules` alone.
        """
        cfg = MagicMock()
        cfg.defaults.backend = "api"
        cfg.defaults.proxmox_api.host = "192.168.1.1"
        with patch('backends.api.ProxmoxAPI', None):
            with pytest.raises(RuntimeError, match="proxmoxer is required"):
                create_backend(cfg)


class TestCLIBackendEdgeCases:
    @pytest.fixture
    def backend(self):
        cfg = MagicMock()
        cfg.defaults.use_remote_proxmox = False
        cfg.defaults.timeout_extended = 300
        return CLIBackend(cfg)

    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_start_container(self, mock_run, backend):
        mock_run.return_value = ""
        assert await backend.start("100") is True
        mock_run.assert_called_once_with(["pct", "start", "100"], 30)

    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_stop_container(self, mock_run, backend):
        mock_run.return_value = ""
        assert await backend.stop("100") is True

    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_set_network(self, mock_run, backend):
        mock_run.return_value = ""
        assert await backend.set_network("100", "name=eth0,bridge=vmbr0,ip=dhcp") is True
        args = mock_run.call_args[0][0]
        assert "-net0" in args

    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_get_status(self, mock_run, backend):
        mock_run.return_value = "status: running"
        result = await backend.get_status("100")
        assert "running" in result

    @patch.object(CLIBackend, '_run_local', new_callable=AsyncMock)
    async def test_get_config_empty(self, mock_run, backend):
        mock_run.return_value = None
        assert await backend.get_container_config("100") is None

    async def test_invalid_ctid_start(self, backend):
        with pytest.raises(ValueError):
            await backend.start("bad")

    async def test_invalid_ctid_stop(self, backend):
        with pytest.raises(ValueError):
            await backend.stop("$(evil)")

    async def test_invalid_ctid_set_network(self, backend):
        with pytest.raises(ValueError):
            await backend.set_network("abc", "config")
