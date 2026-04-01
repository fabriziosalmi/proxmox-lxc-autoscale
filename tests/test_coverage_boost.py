"""Coverage boost tests — target uncovered paths in lxc_utils, api backend, entry point."""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))


# ═══════════════════════════════════════════════════════════════════════════
# lxc_utils: evict_stale_caches
# ═══════════════════════════════════════════════════════════════════════════

class TestEvictStaleCaches:
    def test_removes_stale_entries(self):
        import lxc_utils
        lxc_utils._cgroup_path_cache["100"] = "/fake"
        lxc_utils._cgroup_path_cache["999"] = "/stale"
        lxc_utils._prev_cpu_readings["999"] = (0.0, 0.0)
        lxc_utils._core_count_cache["999"] = 4
        lxc_utils.evict_stale_caches({"100"})
        assert "100" in lxc_utils._cgroup_path_cache
        assert "999" not in lxc_utils._cgroup_path_cache
        assert "999" not in lxc_utils._prev_cpu_readings
        assert "999" not in lxc_utils._core_count_cache

    def test_removes_stale_locks(self):
        import lxc_utils
        lxc_utils._container_locks["888"] = asyncio.Lock()
        lxc_utils.evict_stale_caches({"100"})
        assert "888" not in lxc_utils._container_locks

    def test_keeps_active_entries(self):
        import lxc_utils
        lxc_utils._core_count_cache["100"] = 2
        lxc_utils._applied_pinning["100"] = "0-3"
        lxc_utils.evict_stale_caches({"100"})
        assert lxc_utils._core_count_cache["100"] == 2
        assert lxc_utils._applied_pinning["100"] == "0-3"


# ═══════════════════════════════════════════════════════════════════════════
# lxc_utils: JSON log rotation
# ═══════════════════════════════════════════════════════════════════════════

class TestJsonLogRotationEdgeCases:
    def test_multiple_rotations(self, tmp_path, monkeypatch):
        import lxc_utils
        monkeypatch.setattr('lxc_utils.LOG_FILE', str(tmp_path / "test.log"))
        monkeypatch.setattr('lxc_utils._JSON_LOG_MAX_BYTES', 50)
        monkeypatch.setattr('lxc_utils._JSON_LOG_BACKUP_COUNT', 2)
        monkeypatch.setattr('lxc_utils._json_log_file', None)

        json_path = str(tmp_path / "test.json")
        # First rotation
        with open(json_path, 'w') as f:
            f.write("x" * 100)
        lxc_utils._rotate_json_log_if_needed()
        assert os.path.exists(json_path + ".1")

        # Second rotation
        with open(json_path, 'w') as f:
            f.write("y" * 100)
        lxc_utils._rotate_json_log_if_needed()
        assert os.path.exists(json_path + ".2")

    def test_rotation_closes_open_handle(self, tmp_path, monkeypatch):
        import lxc_utils
        monkeypatch.setattr('lxc_utils.LOG_FILE', str(tmp_path / "test.log"))
        monkeypatch.setattr('lxc_utils._JSON_LOG_MAX_BYTES', 10)
        json_path = str(tmp_path / "test.json")
        # Open a handle
        fh = open(json_path, 'w')
        fh.write("x" * 100)
        fh.close()
        lxc_utils._json_log_file = open(json_path, 'a')
        lxc_utils._rotate_json_log_if_needed()
        assert lxc_utils._json_log_file is None or lxc_utils._json_log_file.closed


# ═══════════════════════════════════════════════════════════════════════════
# lxc_utils: negative cgroup cache
# ═══════════════════════════════════════════════════════════════════════════

class TestNegativeCgroupCache:
    async def test_cpu_negative_cache_skips_discovery(self):
        import lxc_utils
        lxc_utils._cgroup_negative_cache["500"] = 3
        result = await lxc_utils._read_cgroup_cpu_usec("500")
        assert result is None
        assert lxc_utils._cgroup_negative_cache["500"] == 2  # decremented

    async def test_cpu_negative_cache_expires(self):
        import lxc_utils
        lxc_utils._cgroup_negative_cache["501"] = 1
        # TTL=1, should decrement to 0 and return None
        result = await lxc_utils._read_cgroup_cpu_usec("501")
        assert result is None
        assert lxc_utils._cgroup_negative_cache["501"] == 0

    async def test_mem_negative_cache_skips(self):
        import lxc_utils
        lxc_utils._cgroup_mem_negative_cache["600"] = 2
        result = await lxc_utils._read_cgroup_memory("600")
        assert result is None
        assert lxc_utils._cgroup_mem_negative_cache["600"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# lxc_utils: get_container_data
# ═══════════════════════════════════════════════════════════════════════════

class TestGetContainerData:
    @patch('lxc_utils.get_memory_usage', new_callable=AsyncMock, return_value=40.0)
    @patch('lxc_utils.get_cpu_usage', new_callable=AsyncMock, return_value=25.0)
    @patch('lxc_utils.backup_container_settings', new_callable=AsyncMock)
    @patch('lxc_utils.run_command', new_callable=AsyncMock)
    @patch('lxc_utils.is_container_running', new_callable=AsyncMock, return_value=True)
    async def test_success(self, m_run, m_cmd, m_backup, m_cpu, m_mem):
        import lxc_utils
        m_cmd.return_value = "cores: 2\nmemory: 1024"
        result = await lxc_utils.get_container_data("100")
        assert result is not None
        assert result["cpu"] == 25.0
        assert result["mem"] == 40.0
        assert result["initial_cores"] == 2

    @patch('lxc_utils.is_container_running', new_callable=AsyncMock, return_value=False)
    async def test_stopped_returns_none(self, m_run):
        import lxc_utils
        assert await lxc_utils.get_container_data("100") is None

    @patch('lxc_utils.is_container_running', new_callable=AsyncMock, return_value=True)
    @patch('lxc_utils.run_command', new_callable=AsyncMock, return_value=None)
    async def test_no_config_returns_zeroed_data(self, m_cmd, m_running):
        """When pct config returns None, cores/memory default to 0."""
        import lxc_utils
        result = await lxc_utils.get_container_data("100")
        # Still returns data, but with zero values
        assert result is not None
        assert result["initial_cores"] == 0
        assert result["cpu"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# lxc_utils: memory fallback (pct exec path)
# ═══════════════════════════════════════════════════════════════════════════

class TestMemoryFallback:
    @patch('lxc_utils._read_cgroup_memory', new_callable=AsyncMock, return_value=None)
    @patch('lxc_utils.run_command', new_callable=AsyncMock)
    async def test_pct_exec_fallback(self, m_cmd, m_cgroup):
        import lxc_utils
        m_cmd.return_value = "MemTotal:       2048000 kB\nMemAvailable:   1024000 kB\n"
        result = await lxc_utils.get_memory_usage("100")
        assert 49.0 < result < 51.0  # ~50%

    @patch('lxc_utils._read_cgroup_memory', new_callable=AsyncMock, return_value=None)
    @patch('lxc_utils.run_command', new_callable=AsyncMock, return_value=None)
    async def test_all_methods_fail(self, m_cmd, m_cgroup):
        import lxc_utils
        result = await lxc_utils.get_memory_usage("100")
        assert result == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# lxc_utils: CPU pinning (remote path via tee)
# ═══════════════════════════════════════════════════════════════════════════

class TestCpuPinningRemote:
    @patch('lxc_utils.asyncio.create_subprocess_exec')
    @patch('lxc_utils.run_command', new_callable=AsyncMock)
    async def test_remote_append_via_tee(self, m_cmd, m_exec):
        import lxc_utils
        lxc_utils._applied_pinning.clear()
        cfg_mock = MagicMock()
        cfg_mock.defaults.use_remote_proxmox = True

        m_cmd.return_value = "arch: amd64\nmemory: 2048\n"  # no existing pinning

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        m_exec.return_value = mock_proc

        with patch('lxc_utils.get_app_config', return_value=cfg_mock):
            result = await lxc_utils.apply_cpu_pinning("100", "0-3")
            assert result is True
            assert lxc_utils._applied_pinning["100"] == "0-3"

    @patch('lxc_utils.run_command', new_callable=AsyncMock)
    async def test_remote_already_set(self, m_cmd):
        import lxc_utils
        lxc_utils._applied_pinning.clear()
        cfg_mock = MagicMock()
        cfg_mock.defaults.use_remote_proxmox = True

        m_cmd.return_value = "arch: amd64\nlxc.cgroup2.cpuset.cpus: 0-3\nmemory: 2048\n"

        with patch('lxc_utils.get_app_config', return_value=cfg_mock):
            result = await lxc_utils.apply_cpu_pinning("100", "0-3")
            assert result is True

    @patch('lxc_utils.run_command', new_callable=AsyncMock, return_value=None)
    async def test_remote_read_fails(self, m_cmd):
        import lxc_utils
        lxc_utils._applied_pinning.clear()
        cfg_mock = MagicMock()
        cfg_mock.defaults.use_remote_proxmox = True

        with patch('lxc_utils.get_app_config', return_value=cfg_mock):
            result = await lxc_utils.apply_cpu_pinning("100", "0-3")
            assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# lxc_utils: prune_old_backups
# ═══════════════════════════════════════════════════════════════════════════

class TestPruneOldBackups:
    def test_prune_with_no_dir(self, monkeypatch):
        import lxc_utils
        monkeypatch.setattr('lxc_utils.BACKUP_DIR', '/nonexistent_dir_xyz')
        lxc_utils.prune_old_backups(max_per_container=1)  # should not crash

    def test_prune_under_limit(self, tmp_path, monkeypatch):
        import lxc_utils
        monkeypatch.setattr('lxc_utils.BACKUP_DIR', str(tmp_path))
        (tmp_path / "100_backup.json").write_text("{}")
        lxc_utils.prune_old_backups(max_per_container=5)
        assert (tmp_path / "100_backup.json").exists()


# ═══════════════════════════════════════════════════════════════════════════
# lxc_utils: CPU second sample (delta computation)
# ═══════════════════════════════════════════════════════════════════════════

class TestCpuDeltaComputation:
    async def test_second_sample_computes_delta(self):
        import lxc_utils
        import time
        lxc_utils._prev_cpu_readings["700"] = (1_000_000.0, time.monotonic() - 5.0)
        lxc_utils._core_count_cache["700"] = 2

        async def mock_read(ctid):
            return 3_000_000.0  # 2 seconds of CPU across 2 cores

        with patch.object(lxc_utils, '_read_cgroup_cpu_usec', side_effect=mock_read):
            result = await lxc_utils._cgroup_method("700")
            assert result > 0.0
            assert result <= 100.0

    async def test_counter_reset_returns_zero(self):
        import lxc_utils
        import time
        # Previous reading is HIGHER than current (counter reset)
        lxc_utils._prev_cpu_readings["701"] = (9_000_000.0, time.monotonic() - 5.0)
        lxc_utils._core_count_cache["701"] = 1

        async def mock_read(ctid):
            return 1_000_000.0  # less than previous

        with patch.object(lxc_utils, '_read_cgroup_cpu_usec', side_effect=mock_read):
            result = await lxc_utils._cgroup_method("701")
            assert result == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# lxc_autoscale.py: entry point
# ═══════════════════════════════════════════════════════════════════════════

class TestEntryPoint:
    def _load_main(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "lxc_autoscale_main",
            os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale', 'lxc_autoscale.py'),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_parse_arguments(self):
        mod = self._load_main()
        with patch('sys.argv', ['prog', '--poll_interval', '60', '--debug']):
            args = mod.parse_arguments()
            assert args.poll_interval == 60
            assert args.debug is True
            assert args.rollback is False

    def test_parse_arguments_defaults(self):
        mod = self._load_main()
        with patch('sys.argv', ['prog']):
            args = mod.parse_arguments()
            assert args.poll_interval > 0
            assert args.energy_mode is False

    async def test_async_main_rollback(self):
        mod = self._load_main()
        from argparse import Namespace
        args = Namespace(rollback=True, poll_interval=300, energy_mode=False)
        with patch.object(mod, 'get_containers', new_callable=AsyncMock, return_value=["100", "101"]):
            with patch.object(mod, 'rollback_container_settings', new_callable=AsyncMock) as m_rb:
                await mod.async_main(args)
                assert m_rb.call_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# backends/api.py: RESTBackend (mocked proxmoxer)
# ═══════════════════════════════════════════════════════════════════════════

class TestRESTBackend:
    @pytest.fixture
    def mock_api_config(self):
        cfg = MagicMock()
        cfg.defaults.proxmox_api.host = "192.168.1.1"
        cfg.defaults.proxmox_api.user = "root@pam"
        cfg.defaults.proxmox_api.token_name = "autoscale"
        cfg.defaults.proxmox_api.token_value = "secret"
        cfg.defaults.proxmox_api.verify_ssl = False
        return cfg

    @patch('backends.api.ProxmoxAPI')
    async def test_list_containers(self, MockAPI, mock_api_config):
        from backends.api import RESTBackend
        mock_instance = MagicMock()
        MockAPI.return_value = mock_instance
        mock_instance.nodes.return_value.lxc.get.return_value = [
            {"vmid": 100}, {"vmid": 101}
        ]
        backend = RESTBackend(mock_api_config)
        backend._node = "pve"
        result = await backend.list_containers()
        assert result == ["100", "101"]

    @patch('backends.api.ProxmoxAPI')
    async def test_is_running(self, MockAPI, mock_api_config):
        from backends.api import RESTBackend
        mock_instance = MagicMock()
        MockAPI.return_value = mock_instance
        mock_instance.nodes.return_value.lxc.return_value.status.current.get.return_value = {
            "status": "running"
        }
        backend = RESTBackend(mock_api_config)
        backend._node = "pve"
        assert await backend.is_running("100") is True

    @patch('backends.api.ProxmoxAPI')
    async def test_set_cores(self, MockAPI, mock_api_config):
        from backends.api import RESTBackend
        mock_instance = MagicMock()
        MockAPI.return_value = mock_instance
        backend = RESTBackend(mock_api_config)
        backend._node = "pve"
        assert await backend.set_cores("100", 4) is True

    @patch('backends.api.ProxmoxAPI')
    async def test_set_memory(self, MockAPI, mock_api_config):
        from backends.api import RESTBackend
        mock_instance = MagicMock()
        MockAPI.return_value = mock_instance
        backend = RESTBackend(mock_api_config)
        backend._node = "pve"
        assert await backend.set_memory("100", 2048) is True

    @patch('backends.api.ProxmoxAPI')
    async def test_start_stop(self, MockAPI, mock_api_config):
        from backends.api import RESTBackend
        mock_instance = MagicMock()
        MockAPI.return_value = mock_instance
        backend = RESTBackend(mock_api_config)
        backend._node = "pve"
        assert await backend.start("100") is True
        assert await backend.stop("100") is True

    @patch('backends.api.ProxmoxAPI')
    async def test_snapshot_clone(self, MockAPI, mock_api_config):
        from backends.api import RESTBackend
        mock_instance = MagicMock()
        MockAPI.return_value = mock_instance
        backend = RESTBackend(mock_api_config)
        backend._node = "pve"
        assert await backend.snapshot("100", "snap1") is True
        assert await backend.clone("100", "200", snapname="snap1") is True

    @patch('backends.api.ProxmoxAPI')
    async def test_get_status(self, MockAPI, mock_api_config):
        from backends.api import RESTBackend
        mock_instance = MagicMock()
        MockAPI.return_value = mock_instance
        mock_instance.nodes.return_value.lxc.return_value.status.current.get.return_value = {
            "status": "stopped"
        }
        backend = RESTBackend(mock_api_config)
        backend._node = "pve"
        result = await backend.get_status("100")
        assert "stopped" in result

    @patch('backends.api.ProxmoxAPI')
    async def test_run_raw_logs_warning(self, MockAPI, mock_api_config):
        from backends.api import RESTBackend
        mock_instance = MagicMock()
        MockAPI.return_value = mock_instance
        backend = RESTBackend(mock_api_config)
        result = await backend.run_raw(["pct", "list"])
        assert result is None

    @patch('backends.api.ProxmoxAPI')
    async def test_error_handling(self, MockAPI, mock_api_config):
        from backends.api import RESTBackend
        mock_instance = MagicMock()
        MockAPI.return_value = mock_instance
        mock_instance.nodes.return_value.lxc.get.side_effect = RuntimeError("fail")
        backend = RESTBackend(mock_api_config)
        backend._node = "pve"
        result = await backend.list_containers()
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════
# notification: SSRF edge cases + proxy protection
# ═══════════════════════════════════════════════════════════════════════════

class TestNotificationSessionSecurity:
    def test_trust_env_false(self):
        import notification
        notification._http_session = None
        session = notification._get_session()
        assert session.trust_env is False

    def test_gotify_ssrf_blocked(self):
        import notification
        notification._notifiers_cache = None
        with patch.dict(notification.DEFAULTS, {
            'gotify_url': 'http://127.0.0.1:9000',
            'gotify_token': 'tok',
        }, clear=True):
            notifiers = notification._get_notifiers()
            assert len(notifiers) == 0  # blocked

    def test_kuma_ssrf_blocked(self):
        import notification
        notification._notifiers_cache = None
        with patch.dict(notification.DEFAULTS, {
            'uptime_kuma_webhook_url': 'http://169.254.169.254/latest',
        }, clear=True):
            notifiers = notification._get_notifiers()
            assert len(notifiers) == 0


# ═══════════════════════════════════════════════════════════════════════════
# scaling_manager: _fire_and_forget
# ═══════════════════════════════════════════════════════════════════════════

class TestFireAndForget:
    async def test_task_tracked_and_cleaned(self):
        from scaling_manager import _fire_and_forget, _background_tasks

        async def noop():
            pass

        initial = len(_background_tasks)
        _fire_and_forget(noop())
        assert len(_background_tasks) > initial
        # Let the task complete
        await asyncio.sleep(0.05)
        assert len(_background_tasks) == initial
