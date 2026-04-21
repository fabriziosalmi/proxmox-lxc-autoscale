"""Unit tests for lxc_utils — async functions with mocked subprocess."""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

import lxc_utils


# ═══════════════════════════════════════════════════════════════════════════
# Command execution
# ═══════════════════════════════════════════════════════════════════════════

class TestRunLocalCommand:
    @patch('lxc_utils.asyncio.create_subprocess_exec')
    async def test_successful_command(self, mock_exec):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"output_data", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        result = await lxc_utils.run_local_command(["echo", "hi"])
        assert result == "output_data"

    @patch('lxc_utils.asyncio.create_subprocess_exec')
    async def test_failed_command_returns_none(self, mock_exec):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"error msg")
        mock_proc.returncode = 1
        mock_exec.return_value = mock_proc

        result = await lxc_utils.run_local_command(["false"])
        assert result is None

    @patch('lxc_utils.asyncio.create_subprocess_exec')
    async def test_timeout_returns_none(self, mock_exec):
        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = asyncio.TimeoutError()
        mock_proc.kill = AsyncMock()
        mock_proc.wait = AsyncMock()
        mock_exec.return_value = mock_proc

        result = await lxc_utils.run_local_command(["sleep", "999"], timeout=1)
        assert result is None
        mock_proc.kill.assert_called_once()

    @patch('lxc_utils.asyncio.create_subprocess_exec')
    async def test_string_command_split(self, mock_exec):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"ok", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await lxc_utils.run_local_command("echo hello world")
        args = mock_exec.call_args[0]
        assert args == ("echo", "hello", "world")


# ═══════════════════════════════════════════════════════════════════════════
# Container queries
# ═══════════════════════════════════════════════════════════════════════════

class TestGetContainers:
    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_parses_pct_list(self, mock_cmd):
        mock_cmd.return_value = (
            "VMID       Status     Lock         Name\n"
            "100        running                 web\n"
            "101        stopped                 db\n"
        )
        result = await lxc_utils.get_containers()
        assert "100" in result
        assert "101" in result

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_empty_output(self, mock_cmd):
        mock_cmd.return_value = None
        result = await lxc_utils.get_containers()
        assert result == []

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_filters_invalid_ids(self, mock_cmd):
        mock_cmd.return_value = (
            "VMID       Status     Name\n"
            "100        running    ok\n"
            "bad        running    nope\n"
        )
        result = await lxc_utils.get_containers()
        assert "100" in result
        assert "bad" not in result


class TestIsContainerRunning:
    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_running(self, mock_cmd):
        mock_cmd.return_value = "status: running"
        assert await lxc_utils.is_container_running("100") is True

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_stopped(self, mock_cmd):
        mock_cmd.return_value = "status: stopped"
        assert await lxc_utils.is_container_running("100") is False

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_none_output(self, mock_cmd):
        mock_cmd.return_value = None
        assert await lxc_utils.is_container_running("100") is False

    async def test_invalid_id_raises(self):
        with pytest.raises(ValueError):
            await lxc_utils.is_container_running("abc")


# ═══════════════════════════════════════════════════════════════════════════
# Backup and rollback
# ═══════════════════════════════════════════════════════════════════════════

class TestBackupAndRollback:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        monkeypatch.setattr('lxc_utils.BACKUP_DIR', str(tmp_path))
        lxc_utils._last_backup_settings.clear()
        self.tmp = tmp_path

    async def test_backup_creates_file(self):
        await lxc_utils.backup_container_settings("100", {"cores": 4, "memory": 2048})
        f = self.tmp / "100_backup.json"
        assert f.exists()
        data = json.loads(f.read_text())
        assert data == {"cores": 4, "memory": 2048}

    async def test_load_backup(self):
        (self.tmp / "200_backup.json").write_text('{"cores": 2, "memory": 1024}')
        settings = await lxc_utils.load_backup_settings("200")
        assert settings == {"cores": 2, "memory": 1024}

    async def test_load_missing_backup(self):
        settings = await lxc_utils.load_backup_settings("999")
        assert settings is None

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_rollback_calls_pct_set(self, mock_cmd):
        (self.tmp / "300_backup.json").write_text('{"cores": 2, "memory": 1024}')
        mock_cmd.return_value = ""
        await lxc_utils.rollback_container_settings("300")
        calls = [str(c) for c in mock_cmd.call_args_list]
        assert any("-cores" in c and "2" in c for c in calls)
        assert any("-memory" in c and "1024" in c for c in calls)


# ═══════════════════════════════════════════════════════════════════════════
# JSON event logging
# ═══════════════════════════════════════════════════════════════════════════

class TestLogJsonEvent:
    async def test_writes_json_line(self, tmp_path, monkeypatch):
        json_path = str(tmp_path / "test.json")
        monkeypatch.setattr('lxc_utils.LOG_FILE', str(tmp_path / "test.log"))
        monkeypatch.setattr('lxc_utils._json_log_file', None)

        await lxc_utils.log_json_event("100", "Increase Cores", "2")
        assert os.path.exists(json_path)
        with open(json_path) as f:
            data = json.loads(f.readline())
        assert data["container_id"] == "100"
        assert data["action"] == "Increase Cores"
        assert data["change"] == "2"
        assert "proxmox_host" in data
        assert "timestamp" in data


# ═══════════════════════════════════════════════════════════════════════════
# Host resource queries
# ═══════════════════════════════════════════════════════════════════════════

class TestHostResources:
    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_get_total_cores(self, mock_cmd):
        mock_cmd.return_value = "16"
        cores = await lxc_utils.get_total_cores()
        # 16 cores - max(1, int(16*0.10)) = 16 - 1 = 15
        assert cores == 15

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_get_total_memory(self, mock_cmd):
        mock_cmd.return_value = (
            "              total        used        free\n"
            "Mem:          32000       16000       16000\n"
            "Swap:          4000           0        4000\n"
        )
        mem = await lxc_utils.get_total_memory()
        # 32000 - 2048 reserved = 29952
        assert mem == 29952

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_get_total_memory_none(self, mock_cmd):
        mock_cmd.return_value = None
        mem = await lxc_utils.get_total_memory()
        assert mem == 0


# ═══════════════════════════════════════════════════════════════════════════
# CPU topology
# ═══════════════════════════════════════════════════════════════════════════

class TestCpuTopology:
    def test_cpus_to_range_contiguous(self):
        assert lxc_utils._cpus_to_range([0, 1, 2, 3]) == "0-3"

    def test_cpus_to_range_gaps(self):
        assert lxc_utils._cpus_to_range([0, 1, 4, 5, 6]) == "0-1,4-6"

    def test_cpus_to_range_single(self):
        assert lxc_utils._cpus_to_range([7]) == "7"

    def test_cpus_to_range_empty(self):
        assert lxc_utils._cpus_to_range([]) == ""

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_detect_non_hybrid(self, mock_cmd):
        lxc_utils._cached_topology = None
        mock_cmd.side_effect = lambda cmd, **kw: asyncio.coroutine(
            lambda: "8" if cmd == ["nproc"] else ""
        )()

        async def mock(cmd, **kw):
            if cmd == ["nproc"]:
                return "8"
            return ""

        with patch.object(lxc_utils, 'run_command', side_effect=mock):
            topo = await lxc_utils.detect_cpu_topology()
            assert len(topo['all']) == 8
            assert topo['hybrid'] is False
            lxc_utils._cached_topology = None  # cleanup


# ═══════════════════════════════════════════════════════════════════════════
# CPU pinning resolution
# ═══════════════════════════════════════════════════════════════════════════

class TestResolvePinning:
    @patch.object(lxc_utils, 'detect_cpu_topology', new_callable=AsyncMock)
    async def test_explicit_range(self, mock_topo):
        mock_topo.return_value = {'p_cores': [0, 1], 'e_cores': [2, 3], 'all': [0, 1, 2, 3], 'hybrid': True}
        assert await lxc_utils.resolve_cpu_pinning("0-3") == "0-3"

    @patch.object(lxc_utils, 'detect_cpu_topology', new_callable=AsyncMock)
    async def test_p_cores(self, mock_topo):
        mock_topo.return_value = {'p_cores': [0, 1, 2, 3], 'e_cores': [4, 5], 'all': list(range(6)), 'hybrid': True}
        assert await lxc_utils.resolve_cpu_pinning("p-cores") == "0-3"

    @patch.object(lxc_utils, 'detect_cpu_topology', new_callable=AsyncMock)
    async def test_invalid_value(self, mock_topo):
        mock_topo.return_value = {'p_cores': [], 'e_cores': [], 'all': [], 'hybrid': False}
        assert await lxc_utils.resolve_cpu_pinning("invalid!") is None


# ═══════════════════════════════════════════════════════════════════════════
# Cgroup CPU parsing
# ═══════════════════════════════════════════════════════════════════════════

class TestCgroupCPU:
    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_parse_v2(self, mock_cmd):
        mock_cmd.return_value = "usage_usec 12345678\nuser_usec 1234\nsystem_usec 5678"
        result = await lxc_utils._parse_cgroup_v2("/fake/cpu.stat")
        assert result == 12345678.0

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_parse_v1(self, mock_cmd):
        mock_cmd.return_value = "12345678000"  # nanoseconds
        result = await lxc_utils._parse_cgroup_v1("/fake/cpuacct.usage")
        assert result == 12345678.0

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    async def test_parse_v2_missing(self, mock_cmd):
        mock_cmd.return_value = None
        assert await lxc_utils._parse_cgroup_v2("/fake/cpu.stat") is None


class TestGetCpuUsage:
    @patch.object(lxc_utils, 'pvesh_stat_method', new_callable=AsyncMock, return_value=12.5)
    async def test_prefers_pvesh_method_when_available(self, mock_pvesh):
        result = await lxc_utils.get_cpu_usage("100")
        assert result == 12.5
        mock_pvesh.assert_awaited_once_with("100")


# ═══════════════════════════════════════════════════════════════════════════
# Name generation
# ═══════════════════════════════════════════════════════════════════════════

class TestNameGeneration:
    def test_snapshot_name_format(self):
        name = lxc_utils.generate_unique_snapshot_name("snap")
        assert name.startswith("snap-")
        assert len(name) > 10

    def test_hostname_sanitization(self):
        assert lxc_utils.generate_cloned_hostname("web", 1) == "web-cloned-1"
        assert lxc_utils.generate_cloned_hostname("bad;name$(cmd)", 2).startswith("bad-name--cmd-")

    def test_hostname_empty_fallback(self):
        result = lxc_utils.generate_cloned_hostname(";;;", 3)
        assert result.startswith("container-cloned-")


# ═══════════════════════════════════════════════════════════════════════════
# Prioritize containers
# ═══════════════════════════════════════════════════════════════════════════

class TestPrioritize:
    def test_sorts_by_cpu_then_mem(self):
        containers = {
            "100": {"cpu": 90, "mem": 50},
            "101": {"cpu": 20, "mem": 80},
            "102": {"cpu": 90, "mem": 70},
        }
        result = lxc_utils.prioritize_containers(containers)
        # 102 first (90 cpu, 70 mem), then 100 (90, 50), then 101 (20, 80)
        assert result[0][0] == "102"
        assert result[1][0] == "100"

    def test_empty_returns_empty(self):
        assert lxc_utils.prioritize_containers({}) == []
