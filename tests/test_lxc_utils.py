"""Unit tests for lxc_utils — async functions with mocked subprocess."""

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
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

# Real probe output, AMD Ryzen AI MAX+ 395 (2 CCDs, 1 NUMA node, no core_type).
AMD_PROBE = """online:0-31
nproc:32
pmu:core:
pmu:atom:
l3:0-7,16-23:32768K
l3:0-7,16-23:32768K
l3:8-15,24-31:32768K
numa:node0:0-31"""

# Intel i5-13500 shape: 6 P-cores + HT (0-11), 8 E-cores (12-19), as the two
# hybrid PMUs report them.
INTEL_HYBRID_PROBE = """online:0-19
nproc:20
pmu:core:0-11
pmu:atom:12-19
l3:0-19:24576K
numa:node0:0-19"""

# Dual-socket EPYC: 2 NUMA nodes, 4 L3 domains, no core_type.
EPYC_PROBE = """online:0-31
nproc:32
pmu:core:
pmu:atom:
l3:0-7:32768K
l3:8-15:32768K
l3:16-23:32768K
l3:24-31:32768K
numa:node0:0-15
numa:node1:16-31"""


def _probe(text):
    async def run(cmd, **kw):
        return text
    return run


class TestRangeParsing:
    def test_cpus_to_range_contiguous(self):
        assert lxc_utils._cpus_to_range([0, 1, 2, 3]) == "0-3"

    def test_cpus_to_range_gaps(self):
        assert lxc_utils._cpus_to_range([0, 1, 4, 5, 6]) == "0-1,4-6"

    def test_cpus_to_range_single(self):
        assert lxc_utils._cpus_to_range([7]) == "7"

    def test_cpus_to_range_empty(self):
        assert lxc_utils._cpus_to_range([]) == ""

    def test_range_to_cpus_mixed(self):
        assert lxc_utils._range_to_cpus("0-3,8,10-11") == [0, 1, 2, 3, 8, 10, 11]

    def test_range_to_cpus_single(self):
        assert lxc_utils._range_to_cpus("5") == [5]

    def test_range_to_cpus_junk(self):
        assert lxc_utils._range_to_cpus("not-a-range") == []

    @pytest.mark.parametrize("cpus", [[0], [0, 1, 2, 3], [0, 1, 4, 5, 6], [2, 9, 10]])
    def test_round_trip(self, cpus):
        assert lxc_utils._range_to_cpus(lxc_utils._cpus_to_range(cpus)) == cpus


class TestCpuTopology:
    def setup_method(self):
        lxc_utils._cached_topology = None

    def teardown_method(self):
        lxc_utils._cached_topology = None

    async def test_amd_has_no_pe_groups(self):
        with patch.object(lxc_utils, 'run_command', side_effect=_probe(AMD_PROBE)):
            groups = await lxc_utils.detect_cpu_topology()
        assert 'p-cores' not in groups
        assert 'e-cores' not in groups
        assert groups['all'] == list(range(32))

    async def test_amd_l3_domains_are_ccds(self):
        with patch.object(lxc_utils, 'run_command', side_effect=_probe(AMD_PROBE)):
            groups = await lxc_utils.detect_cpu_topology()
        assert lxc_utils._cpus_to_range(groups['l3:0']) == "0-7,16-23"
        assert lxc_utils._cpus_to_range(groups['l3:1']) == "8-15,24-31"

    async def test_amd_numa_group(self):
        with patch.object(lxc_utils, 'run_command', side_effect=_probe(AMD_PROBE)):
            groups = await lxc_utils.detect_cpu_topology()
        assert groups['numa:0'] == list(range(32))

    async def test_l3_groups_ordered_by_lowest_cpu(self):
        shuffled = "nproc:32\nl3:8-15,24-31:32768K\nl3:0-7,16-23:32768K"
        with patch.object(lxc_utils, 'run_command', side_effect=_probe(shuffled)):
            groups = await lxc_utils.detect_cpu_topology()
        assert groups['l3:0'][0] == 0
        assert groups['l3:1'][0] == 8

    async def test_intel_hybrid_still_detected(self):
        with patch.object(lxc_utils, 'run_command', side_effect=_probe(INTEL_HYBRID_PROBE)):
            groups = await lxc_utils.detect_cpu_topology()
        assert lxc_utils._cpus_to_range(groups['p-cores']) == "0-11"
        assert lxc_utils._cpus_to_range(groups['e-cores']) == "12-19"

    async def test_epyc_numa_nodes_keep_their_ids(self):
        with patch.object(lxc_utils, 'run_command', side_effect=_probe(EPYC_PROBE)):
            groups = await lxc_utils.detect_cpu_topology()
        assert groups['numa:0'] == list(range(16))
        assert groups['numa:1'] == list(range(16, 32))
        assert lxc_utils._cpus_to_range(groups['l3:3']) == "24-31"

    async def test_probe_failure_yields_no_groups(self):
        async def run(cmd, **kw):
            return None
        with patch.object(lxc_utils, 'run_command', side_effect=run):
            groups = await lxc_utils.detect_cpu_topology()
        assert groups == {}

    async def test_probe_failure_is_not_cached(self):
        """A single SSH timeout must not disable pinning for the daemon's life."""
        results = [None, AMD_PROBE]

        async def run(cmd, **kw):
            return results.pop(0)

        with patch.object(lxc_utils, 'run_command', side_effect=run):
            assert await lxc_utils.detect_cpu_topology() == {}
            assert 'l3:0' in await lxc_utils.detect_cpu_topology()

    async def test_cpuless_numa_node_is_not_offered(self):
        """A CXL or persistent-memory node has an empty cpulist and cannot be pinned to."""
        probe = "online:0-15\nnuma:node0:0-15\nnuma:node1:"
        with patch.object(lxc_utils, 'run_command', side_effect=_probe(probe)):
            groups = await lxc_utils.detect_cpu_topology()
        assert 'numa:1' not in groups
        assert groups['numa:0'] == list(range(16))

    async def test_all_uses_online_cpus_not_the_affinity_mask(self):
        """nproc reports the daemon's own affinity, which CPUAffinity= or a cpuset narrows."""
        probe = "online:0-31\nnproc:2"
        with patch.object(lxc_utils, 'run_command', side_effect=_probe(probe)):
            groups = await lxc_utils.detect_cpu_topology()
        assert groups['all'] == list(range(32))

    async def test_all_falls_back_to_nproc_without_online(self):
        with patch.object(lxc_utils, 'run_command', side_effect=_probe("nproc:8")):
            groups = await lxc_utils.detect_cpu_topology()
        assert groups['all'] == list(range(8))

    async def test_online_cpus_may_be_sparse(self):
        with patch.object(lxc_utils, 'run_command', side_effect=_probe("online:0-3,8-11")):
            groups = await lxc_utils.detect_cpu_topology()
        assert groups['all'] == [0, 1, 2, 3, 8, 9, 10, 11]

    async def test_result_is_cached(self):
        calls = []

        async def run(cmd, **kw):
            calls.append(cmd)
            return AMD_PROBE

        with patch.object(lxc_utils, 'run_command', side_effect=run):
            await lxc_utils.detect_cpu_topology()
            await lxc_utils.detect_cpu_topology()
        assert len(calls) == 1


class TestTopologyProbeScript:
    """
    Runs `_TOPOLOGY_PROBE` itself, against a sysfs tree built on disk.

    Every other test in this file feeds `detect_cpu_topology` a canned string,
    which checks the parser and never the thing that produces the string. That
    is the gap the feature shipped through: `topology/core_type` does not exist
    in mainline Linux, the probe returned nothing for it on every machine, and
    no test could tell, because no test ran the probe.

    The trees below are the shapes the fixtures above claim to come from. The
    cache directories carry L1d, L1i and L2 alongside L3, and L3 is not always
    index3, so a probe that assumed the index rather than reading `level` would
    fail here.
    """

    @staticmethod
    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n")

    @classmethod
    def _build(cls, root: Path, cpus: int, l3: list, numa: dict,
               online: str = None, pmu: dict = None) -> Path:
        sysfs = root / "sys"
        if online is not None:
            cls._write(sysfs / "devices/system/cpu/online", online)
        owner = {}
        for domain in l3:
            for cpu in lxc_utils._range_to_cpus(domain):
                owner[cpu] = domain
        for cpu in range(cpus):
            base = sysfs / f"devices/system/cpu/cpu{cpu}"
            for index, (level, size) in enumerate([("1", "32K"), ("1", "32K"), ("2", "1024K")]):
                cls._write(base / f"cache/index{index}/level", level)
                cls._write(base / f"cache/index{index}/shared_cpu_list", str(cpu))
                cls._write(base / f"cache/index{index}/size", size)
            if cpu in owner:
                cls._write(base / "cache/index3/level", "3")
                cls._write(base / "cache/index3/shared_cpu_list", owner[cpu])
                cls._write(base / "cache/index3/size", "32768K")
        for node, cpulist in numa.items():
            cls._write(sysfs / f"devices/system/node/node{node}/cpulist", cpulist)
        for name, cpulist in (pmu or {}).items():
            cls._write(sysfs / f"devices/{name}/cpus", cpulist)
        return sysfs

    @staticmethod
    def _run(sysfs: Path, nproc: int) -> str:
        """The real probe, with /sys pointed at the tree and nproc pinned."""
        script = (lxc_utils._TOPOLOGY_PROBE
                  .replace("/sys/", f"{sysfs}/")
                  .replace('"$(nproc)"', f'"{nproc}"'))
        result = subprocess.run(["sh", "-c", script], capture_output=True, text=True)
        assert result.returncode == 0, (
            "the probe must exit 0 even when a glob matches nothing, or "
            "run_command reports a failure on every host without that file: "
            f"{result.stderr}"
        )
        return result.stdout.strip()

    async def _groups(self, sysfs: Path, nproc: int) -> dict:
        output = self._run(sysfs, nproc)
        lxc_utils._cached_topology = None
        with patch.object(lxc_utils, 'run_command', side_effect=_probe(output)):
            return await lxc_utils.detect_cpu_topology()

    async def test_amd_two_ccds(self, tmp_path):
        sysfs = self._build(tmp_path, 32, ["0-7,16-23", "8-15,24-31"],
                            {0: "0-31"}, online="0-31")
        groups = await self._groups(sysfs, 32)
        assert lxc_utils._cpus_to_range(groups['l3:0']) == "0-7,16-23"
        assert lxc_utils._cpus_to_range(groups['l3:1']) == "8-15,24-31"
        assert groups['numa:0'] == list(range(32))
        assert 'p-cores' not in groups

    async def test_intel_hybrid_from_the_pmu_directories(self, tmp_path):
        """
        The interface the kernel actually creates.

        arch/x86/events/intel/core.c registers one PMU per core type on hybrid
        parts, named cpu_core and cpu_atom, each with a `cpus` attribute. Their
        presence is the hybrid signal: a uniform CPU has a single PMU at
        /sys/devices/cpu.
        """
        sysfs = self._build(tmp_path, 20, ["0-19"], {0: "0-19"}, online="0-19",
                            pmu={"cpu_core": "0-11", "cpu_atom": "12-19"})
        groups = await self._groups(sysfs, 20)
        assert lxc_utils._cpus_to_range(groups['p-cores']) == "0-11"
        assert lxc_utils._cpus_to_range(groups['e-cores']) == "12-19"

    async def test_epyc_two_sockets(self, tmp_path):
        sysfs = self._build(tmp_path, 32, ["0-7", "8-15", "16-23", "24-31"],
                            {0: "0-15", 1: "16-31"}, online="0-31")
        groups = await self._groups(sysfs, 32)
        assert lxc_utils._cpus_to_range(groups['l3:3']) == "24-31"
        assert groups['numa:1'] == list(range(16, 32))

    async def test_a_vm_with_no_cache_or_numa_directories(self, tmp_path):
        """A guest often exposes neither. The probe must still exit 0."""
        sysfs = self._build(tmp_path, 4, [], {}, online="0-3")
        groups = await self._groups(sysfs, 4)
        assert groups == {'all': [0, 1, 2, 3]}

    async def test_no_sysfs_at_all_falls_back_to_nproc(self, tmp_path):
        sysfs = self._build(tmp_path, 0, [], {})
        groups = await self._groups(sysfs, 8)
        assert groups == {'all': list(range(8))}

    async def test_l3_is_found_by_level_not_by_index(self, tmp_path):
        """
        L3 is index3 on the shapes above; it is not guaranteed to be. A CPU
        without an L1i entry shifts every index down by one.
        """
        sysfs = self._build(tmp_path, 4, [], {}, online="0-3")
        for cpu in range(4):
            base = sysfs / f"devices/system/cpu/cpu{cpu}"
            shutil.rmtree(base / "cache/index3", ignore_errors=True)
            self._write(base / "cache/index2/level", "3")
            self._write(base / "cache/index2/shared_cpu_list", "0-3")
            self._write(base / "cache/index2/size", "8192K")
        groups = await self._groups(sysfs, 4)
        assert groups['l3:0'] == [0, 1, 2, 3]


# ═══════════════════════════════════════════════════════════════════════════
# CPU pinning resolution
# ═══════════════════════════════════════════════════════════════════════════

class TestResolvePinning:
    def setup_method(self):
        lxc_utils._cached_topology = None

    def teardown_method(self):
        lxc_utils._cached_topology = None

    async def _resolve(self, probe, value):
        with patch.object(lxc_utils, 'run_command', side_effect=_probe(probe)):
            return await lxc_utils.resolve_cpu_pinning(value)

    async def test_explicit_range(self):
        assert await self._resolve(AMD_PROBE, "0-3") == "0-3"

    async def test_explicit_list(self):
        assert await self._resolve(AMD_PROBE, "0,2,4-6") == "0,2,4-6"

    async def test_all(self):
        assert await self._resolve(AMD_PROBE, "all") == "0-31"

    async def test_p_cores_on_intel_hybrid(self):
        assert await self._resolve(INTEL_HYBRID_PROBE, "p-cores") == "0-11"

    async def test_e_cores_on_intel_hybrid(self):
        assert await self._resolve(INTEL_HYBRID_PROBE, "e-cores") == "12-19"

    async def test_p_cores_on_amd_skips_instead_of_pinning_everything(self, caplog):
        assert await self._resolve(AMD_PROBE, "p-cores") is None
        # The message has to say what was looked for and what this host offers
        # instead. The old one blamed AMD, which was never the reason.
        assert "cpu_core" in caplog.text
        assert "l3:0" in caplog.text

    async def test_e_cores_on_amd_warns(self, caplog):
        assert await self._resolve(AMD_PROBE, "e-cores") is None
        assert "l3:" in caplog.text

    async def test_l3_group_on_amd(self):
        assert await self._resolve(AMD_PROBE, "l3:1") == "8-15,24-31"

    async def test_numa_group_on_epyc(self):
        assert await self._resolve(EPYC_PROBE, "numa:1") == "16-31"

    async def test_case_insensitive(self):
        assert await self._resolve(EPYC_PROBE, "  NUMA:1  ") == "16-31"

    async def test_out_of_range_group(self, caplog):
        assert await self._resolve(AMD_PROBE, "l3:9") is None
        assert "l3:0" in caplog.text

    async def test_invalid_value(self):
        assert await self._resolve(AMD_PROBE, "invalid!") is None

    async def test_cpuless_numa_node_errors_rather_than_resolving_empty(self, caplog):
        """An empty range is falsy at the call site, so it would be dropped in silence."""
        probe = "online:0-15\nnuma:node0:0-15\nnuma:node1:"
        assert await self._resolve(probe, "numa:1") is None
        assert "Invalid cpu_pinning value" in caplog.text


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


# ═══════════════════════════════════════════════════════════════════════════
# #70: reading the address actually configured on a container
# ═══════════════════════════════════════════════════════════════════════════

class TestGetContainerIPv4:
    def _read(self, config_output):
        with patch.object(lxc_utils, 'run_command', new_callable=AsyncMock,
                          return_value=config_output):
            return asyncio.run(lxc_utils.get_container_ipv4("100"))

    def test_static_address_with_prefix(self):
        assert self._read(
            "cores: 2\nnet0: name=eth0,bridge=vmbr0,ip=10.0.0.50/24,gw=10.0.0.1\n"
        ) == "10.0.0.50"

    def test_static_address_without_prefix(self):
        assert self._read("net0: name=eth0,bridge=vmbr0,ip=192.168.1.7\n") == "192.168.1.7"

    def test_dhcp_returns_none(self):
        assert self._read("net0: name=eth0,bridge=vmbr0,ip=dhcp\n") is None

    def test_manual_returns_none(self):
        assert self._read("net0: name=eth0,bridge=vmbr0,ip=manual\n") is None

    def test_no_net0_returns_none(self):
        assert self._read("cores: 2\nmemory: 512\n") is None

    def test_unreadable_config_returns_none(self):
        assert self._read(None) is None

    def test_ignores_addresses_on_other_interfaces(self):
        # Only net0 is managed by horizontal scaling.
        assert self._read(
            "net1: name=eth1,bridge=vmbr1,ip=172.16.0.9/24\n"
            "net0: name=eth0,bridge=vmbr0,ip=dhcp\n"
        ) is None

    def test_rejects_invalid_ctid(self):
        with pytest.raises(ValueError):
            asyncio.run(lxc_utils.get_container_ipv4("100; rm -rf /"))
