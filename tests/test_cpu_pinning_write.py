"""
Writing a CPU pin into a container config.

Four defects meant no pin was ever written, on either path, and none of them
produced a visible error beyond one line at ERROR on the local path:

1. the symlink guard rejected the path pmxcfs actually produces
2. the remote branch wrote through a local subprocess, so the node never saw it
3. the remote read lost its trailing newline and fused the appended line onto
   the last key
4. the pin was appended after the snapshot sections, where it does nothing, and
   a cpuset line inside a snapshot was read as proof the live section had one

Each is covered below against the shape of a real config: pct stores every
snapshot as a `[name]` section holding a full copy of the configuration.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lxc_autoscale"))

import lxc_utils  # noqa: E402


# A config with one snapshot, which is the case the flat rewrite got wrong.
CONFIG_WITH_SNAPSHOT = """arch: amd64
hostname: web01
memory: 2048
swap: 512

[before-upgrade]
arch: amd64
hostname: web01
lxc.cgroup2.cpuset.cpus: 8-11
memory: 1024
swap: 512
"""


class TestLiveSectionRewrite:
    """_set_cpuset_line: the pure part, testable without a filesystem."""

    def test_appends_inside_the_live_section(self):
        new, changed = lxc_utils._set_cpuset_line(CONFIG_WITH_SNAPSHOT, "0-3")
        assert changed is True
        live = new.split("[before-upgrade]")[0]
        assert "lxc.cgroup2.cpuset.cpus: 0-3" in live, (
            "the pin has to land in the live section; appended after the "
            "snapshot header it has no effect on the running container"
        )

    def test_leaves_the_snapshot_untouched(self):
        new, _ = lxc_utils._set_cpuset_line(CONFIG_WITH_SNAPSHOT, "0-3")
        snapshot = new.split("[before-upgrade]")[1]
        assert "lxc.cgroup2.cpuset.cpus: 8-11" in snapshot, (
            "a snapshot is a record of what the config was; rewriting it "
            "would falsify history"
        )

    def test_a_pin_in_a_snapshot_is_not_mistaken_for_the_live_one(self):
        """
        The old code scanned the file flat, so the snapshot's cpuset line set
        found=True and the live section never got one.
        """
        new, changed = lxc_utils._set_cpuset_line(CONFIG_WITH_SNAPSHOT, "8-11")
        assert changed is True
        live = new.split("[before-upgrade]")[0]
        assert "lxc.cgroup2.cpuset.cpus: 8-11" in live

    def test_replaces_an_existing_live_pin(self):
        content = "arch: amd64\nlxc.cgroup2.cpuset.cpus: 0-1\nmemory: 2048\n"
        new, changed = lxc_utils._set_cpuset_line(content, "4-7")
        assert changed is True
        assert "lxc.cgroup2.cpuset.cpus: 4-7" in new
        assert "0-1" not in new

    def test_reports_no_change_when_already_correct(self):
        content = "arch: amd64\nlxc.cgroup2.cpuset.cpus: 0-3\n"
        new, changed = lxc_utils._set_cpuset_line(content, "0-3")
        assert changed is False
        assert new == content

    def test_restores_a_missing_trailing_newline(self):
        """run_command strips its output, so the content arrives without one."""
        new, changed = lxc_utils._set_cpuset_line("arch: amd64\nmemory: 2048", "0-3")
        assert changed is True
        assert new == "arch: amd64\nmemory: 2048\nlxc.cgroup2.cpuset.cpus: 0-3\n"
        assert "2048lxc" not in new

    def test_handles_a_config_with_no_snapshots(self):
        new, changed = lxc_utils._set_cpuset_line("arch: amd64\n", "0-3")
        assert changed is True
        assert new == "arch: amd64\nlxc.cgroup2.cpuset.cpus: 0-3\n"


class TestConfPathGuard:
    """_is_expected_conf_path: the guard that rejected every real path."""

    def test_accepts_the_path_pmxcfs_actually_produces(self):
        assert lxc_utils._is_expected_conf_path(
            "/etc/pve/nodes/pve1/lxc/100.conf", "100"
        ), (
            "/etc/pve/lxc is documented as a symlink to nodes/<node>/lxc/, so "
            "this is what realpath returns on every node"
        )

    def test_accepts_the_unresolved_path(self):
        assert lxc_utils._is_expected_conf_path("/etc/pve/lxc/100.conf", "100")

    def test_rejects_a_path_outside_pve(self):
        assert not lxc_utils._is_expected_conf_path("/tmp/evil/100.conf", "100")

    def test_rejects_another_containers_config(self):
        assert not lxc_utils._is_expected_conf_path(
            "/etc/pve/nodes/pve1/lxc/999.conf", "100"
        )

    def test_rejects_a_deeper_path_under_nodes(self):
        assert not lxc_utils._is_expected_conf_path(
            "/etc/pve/nodes/pve1/lxc/sub/100.conf", "100"
        )

    def test_rejects_a_node_name_containing_a_separator(self):
        assert not lxc_utils._is_expected_conf_path(
            "/etc/pve/nodes/a/b/lxc/100.conf", "100"
        )


@pytest.mark.asyncio
class TestLocalWrite:
    async def test_writes_through_a_symlinked_directory(self, tmp_path):
        """
        The whole local path, against a replica of the documented layout. The
        old guard required realpath to still start with /etc/pve/lxc/, which is
        false on every node, so this write was refused as a symlink attack.
        """
        node_dir = tmp_path / "nodes" / "pve1" / "lxc"
        node_dir.mkdir(parents=True)
        conf = node_dir / "100.conf"
        conf.write_text(CONFIG_WITH_SNAPSHOT)
        link = tmp_path / "lxc"
        link.symlink_to(node_dir)

        lxc_utils._applied_pinning.clear()
        cfg = MagicMock()
        cfg.defaults.use_remote_proxmox = False

        with patch("lxc_utils.get_app_config", return_value=cfg), \
             patch("lxc_utils._container_conf_path", return_value=str(link / "100.conf")), \
             patch("lxc_utils._is_expected_conf_path", return_value=True):
            assert await lxc_utils.apply_cpu_pinning("100", "0-3") is True

        written = conf.read_text()
        live = written.split("[before-upgrade]")[0]
        assert "lxc.cgroup2.cpuset.cpus: 0-3" in live
        assert "lxc.cgroup2.cpuset.cpus: 8-11" in written.split("[before-upgrade]")[1]

    async def test_refuses_an_unexpected_path(self, tmp_path):
        conf = tmp_path / "100.conf"
        conf.write_text("arch: amd64\n")
        lxc_utils._applied_pinning.clear()
        cfg = MagicMock()
        cfg.defaults.use_remote_proxmox = False

        with patch("lxc_utils.get_app_config", return_value=cfg), \
             patch("lxc_utils._container_conf_path", return_value=str(conf)):
            assert await lxc_utils.apply_cpu_pinning("100", "0-3") is False
        assert conf.read_text() == "arch: amd64\n"


@pytest.mark.asyncio
class TestRemoteWrite:
    async def test_the_write_reaches_the_node(self):
        lxc_utils._applied_pinning.clear()
        cfg = MagicMock()
        cfg.defaults.use_remote_proxmox = True

        with patch("lxc_utils.get_app_config", return_value=cfg), \
             patch("lxc_utils.run_command", new_callable=AsyncMock,
                   return_value=CONFIG_WITH_SNAPSHOT.strip()), \
             patch("lxc_utils.run_command_with_input", new_callable=AsyncMock,
                   return_value=True) as write:
            assert await lxc_utils.apply_cpu_pinning("100", "0-3") is True

        written = write.await_args.args[1]
        live = written.split("[before-upgrade]")[0]
        assert "lxc.cgroup2.cpuset.cpus: 0-3" in live
        assert "512lxc" not in written, "the stripped trailing newline was not restored"

    async def test_a_failed_write_is_not_recorded_as_applied(self):
        """
        _applied_pinning is consulted before every attempt, so recording a
        failure means never retrying for the life of the process.
        """
        lxc_utils._applied_pinning.clear()
        cfg = MagicMock()
        cfg.defaults.use_remote_proxmox = True

        with patch("lxc_utils.get_app_config", return_value=cfg), \
             patch("lxc_utils.run_command", new_callable=AsyncMock,
                   return_value="arch: amd64"), \
             patch("lxc_utils.run_command_with_input", new_callable=AsyncMock,
                   return_value=False):
            assert await lxc_utils.apply_cpu_pinning("100", "0-3") is False
        assert "100" not in lxc_utils._applied_pinning

    async def test_no_write_when_the_live_pin_is_already_correct(self):
        lxc_utils._applied_pinning.clear()
        cfg = MagicMock()
        cfg.defaults.use_remote_proxmox = True

        with patch("lxc_utils.get_app_config", return_value=cfg), \
             patch("lxc_utils.run_command", new_callable=AsyncMock,
                   return_value="arch: amd64\nlxc.cgroup2.cpuset.cpus: 0-3"), \
             patch("lxc_utils.run_command_with_input", new_callable=AsyncMock) as write:
            assert await lxc_utils.apply_cpu_pinning("100", "0-3") is True
        write.assert_not_awaited()
