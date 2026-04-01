"""Tests for scaling_manager async orchestration functions."""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

import scaling_manager as sm


class TestAdjustResources:
    """Test the main adjust_resources orchestration."""

    @patch.object(sm, 'run_command', new_callable=AsyncMock, return_value="")
    @patch.object(sm, 'log_json_event', new_callable=AsyncMock)
    @patch.object(sm, 'resolve_cpu_pinning', new_callable=AsyncMock, return_value=None)
    @patch.object(sm, 'get_total_memory', new_callable=AsyncMock, return_value=16000)
    @patch.object(sm, 'get_total_cores', new_callable=AsyncMock, return_value=8)
    async def test_scale_up_cpu(self, m_cores, m_mem, m_pin, m_log, m_cmd):
        containers = {
            "100": {
                "cpu": 95.0, "mem": 50.0,
                "initial_cores": 2, "initial_memory": 1024,
            }
        }
        await sm.adjust_resources(containers, energy_mode=False)
        # Should have called pct set to increase cores
        calls = [str(c) for c in m_cmd.call_args_list]
        assert any("-cores" in c for c in calls)

    @patch.object(sm, 'run_command', new_callable=AsyncMock, return_value="")
    @patch.object(sm, 'log_json_event', new_callable=AsyncMock)
    @patch.object(sm, 'resolve_cpu_pinning', new_callable=AsyncMock, return_value=None)
    @patch.object(sm, 'get_total_memory', new_callable=AsyncMock, return_value=16000)
    @patch.object(sm, 'get_total_cores', new_callable=AsyncMock, return_value=8)
    async def test_scale_down_cpu(self, m_cores, m_mem, m_pin, m_log, m_cmd):
        containers = {
            "100": {
                "cpu": 5.0, "mem": 50.0,
                "initial_cores": 4, "initial_memory": 1024,
            }
        }
        await sm.adjust_resources(containers, energy_mode=False)
        calls = [str(c) for c in m_cmd.call_args_list]
        assert any("-cores" in c for c in calls)

    @patch.object(sm, 'run_command', new_callable=AsyncMock, return_value="")
    @patch.object(sm, 'log_json_event', new_callable=AsyncMock)
    @patch.object(sm, 'resolve_cpu_pinning', new_callable=AsyncMock, return_value=None)
    @patch.object(sm, 'get_total_memory', new_callable=AsyncMock, return_value=16000)
    @patch.object(sm, 'get_total_cores', new_callable=AsyncMock, return_value=8)
    async def test_no_scale_in_range(self, m_cores, m_mem, m_pin, m_log, m_cmd):
        containers = {
            "100": {
                "cpu": 50.0, "mem": 50.0,
                "initial_cores": 2, "initial_memory": 1024,
            }
        }
        await sm.adjust_resources(containers, energy_mode=False)
        # Should NOT call pct set for cores (in range)
        core_calls = [c for c in m_cmd.call_args_list if "-cores" in str(c)]
        assert len(core_calls) == 0

    @patch.object(sm, 'run_command', new_callable=AsyncMock, return_value="")
    @patch.object(sm, 'log_json_event', new_callable=AsyncMock)
    @patch.object(sm, 'resolve_cpu_pinning', new_callable=AsyncMock, return_value="0-3")
    @patch.object(sm, 'apply_cpu_pinning', new_callable=AsyncMock, return_value=True)
    @patch.object(sm, 'get_total_memory', new_callable=AsyncMock, return_value=16000)
    @patch.object(sm, 'get_total_cores', new_callable=AsyncMock, return_value=8)
    async def test_applies_cpu_pinning(self, m_cores, m_mem, m_apply, m_pin, m_log, m_cmd):
        with patch.dict(sm.LXC_TIER_ASSOCIATIONS, {"100": {
            'cpu_upper_threshold': 80, 'cpu_lower_threshold': 20,
            'memory_upper_threshold': 80, 'memory_lower_threshold': 20,
            'min_cores': 1, 'max_cores': 4, 'min_memory': 512,
            'core_min_increment': 1, 'core_max_increment': 2,
            'memory_min_increment': 256, 'min_decrease_chunk': 128,
            'cpu_pinning': 'p-cores',
        }}):
            containers = {
                "100": {"cpu": 50.0, "mem": 50.0, "initial_cores": 2, "initial_memory": 1024}
            }
            await sm.adjust_resources(containers, energy_mode=False)
            m_apply.assert_called_once()

    @patch.object(sm, 'is_off_peak', return_value=True)
    @patch.object(sm, 'run_command', new_callable=AsyncMock, return_value="")
    @patch.object(sm, 'log_json_event', new_callable=AsyncMock)
    @patch.object(sm, 'resolve_cpu_pinning', new_callable=AsyncMock, return_value=None)
    @patch.object(sm, 'get_total_memory', new_callable=AsyncMock, return_value=16000)
    @patch.object(sm, 'get_total_cores', new_callable=AsyncMock, return_value=8)
    async def test_energy_mode_reduces(self, m_cores, m_mem, m_pin, m_log, m_cmd, m_offpeak):
        containers = {
            "100": {"cpu": 50.0, "mem": 50.0, "initial_cores": 4, "initial_memory": 2048}
        }
        await sm.adjust_resources(containers, energy_mode=True)
        # Should reduce to min_cores and min_memory
        calls_str = " ".join(str(c) for c in m_cmd.call_args_list)
        assert "-cores" in calls_str
        assert "-memory" in calls_str


class TestScaleOut:
    @patch.object(sm, 'run_command', new_callable=AsyncMock, return_value="OK")
    @patch.object(sm, 'log_json_event', new_callable=AsyncMock)
    async def test_scale_out_clones(self, m_log, m_cmd):
        group_config = {
            'lxc_containers': {'100'},
            'starting_clone_id': 200,
            'max_instances': 5,
            'base_snapshot_name': '100',
            'clone_network_type': 'dhcp',
        }
        await sm.scale_out("test_group", group_config)
        calls_str = " ".join(str(c) for c in m_cmd.call_args_list)
        assert "clone" in calls_str
        assert "start" in calls_str

    @patch.object(sm, 'run_command', new_callable=AsyncMock, return_value="")
    @patch.object(sm, 'log_json_event', new_callable=AsyncMock)
    async def test_scale_out_max_reached(self, m_log, m_cmd):
        group_config = {
            'lxc_containers': {'100', '101', '102'},
            'starting_clone_id': 200,
            'max_instances': 3,
            'base_snapshot_name': '100',
        }
        await sm.scale_out("test_group", group_config)
        # Should not clone
        assert m_cmd.call_count == 0


class TestScaleIn:
    @patch.object(sm, 'run_command', new_callable=AsyncMock, return_value="")
    @patch.object(sm, 'log_json_event', new_callable=AsyncMock)
    async def test_scale_in_stops_last(self, m_log, m_cmd):
        group_config = {
            'lxc_containers': {'100', '101', '102'},
            'min_containers': 1,
        }
        await sm.scale_in("test_group", group_config)
        calls_str = " ".join(str(c) for c in m_cmd.call_args_list)
        assert "stop" in calls_str
        assert "102" in calls_str

    @patch.object(sm, 'run_command', new_callable=AsyncMock, return_value="")
    @patch.object(sm, 'log_json_event', new_callable=AsyncMock)
    async def test_scale_in_at_min(self, m_log, m_cmd):
        group_config = {
            'lxc_containers': {'100'},
            'min_containers': 1,
        }
        await sm.scale_in("test_group", group_config)
        assert m_cmd.call_count == 0


class TestManageHorizontalScaling:
    @patch.object(sm, 'log_scaling_event', new_callable=AsyncMock)
    async def test_skips_empty_groups(self, m_log):
        with patch.dict(sm.HORIZONTAL_SCALING_GROUPS, {"group1": {
            'lxc_containers': {'999'},
        }}):
            await sm.manage_horizontal_scaling({"100": {"cpu": 50, "mem": 50}})
            # Should log skip event
            assert m_log.called

    @patch.object(sm, 'scale_out', new_callable=AsyncMock)
    @patch.object(sm, 'log_scaling_event', new_callable=AsyncMock)
    async def test_triggers_scale_out(self, m_log, m_scale_out):
        sm.scale_last_action.clear()
        with patch.dict(sm.HORIZONTAL_SCALING_GROUPS, {"group1": {
            'lxc_containers': {'100'},
            'horiz_cpu_upper_threshold': 80,
            'horiz_memory_upper_threshold': 80,
            'scale_out_grace_period': 0,
        }}):
            containers = {"100": {"cpu": 95, "mem": 50}}
            await sm.manage_horizontal_scaling(containers)
            m_scale_out.assert_called_once()
