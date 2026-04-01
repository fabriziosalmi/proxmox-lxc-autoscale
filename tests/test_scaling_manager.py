"""Tests for scaling_manager — async scaling logic with mocked commands."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

import scaling_manager
from scaling_manager import (
    calculate_increment, calculate_decrement,
    get_behaviour_multiplier, is_off_peak,
    validate_tier_settings, scale_memory,
    calculate_group_metrics, should_scale_out, should_scale_in,
    calculate_dynamic_thresholds, log_scaling_event,
    send_detailed_notification, _now_tz,
)
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════════════
# Pure computation functions
# ═══════════════════════════════════════════════════════════════════════════

class TestBehaviourMultiplier:
    @patch('scaling_manager._current_hour', return_value=14)
    def test_normal_peak_hours(self, _):
        m = get_behaviour_multiplier()
        assert m == 1.0

    @patch('scaling_manager._current_hour', return_value=23)
    def test_normal_offpeak_hours(self, _):
        m = get_behaviour_multiplier()
        assert m == pytest.approx(0.8)

    @patch('scaling_manager._current_hour', return_value=14)
    @patch.dict('scaling_manager.DEFAULTS', {'behaviour': 'conservative', 'off_peak_start': 22, 'off_peak_end': 6})
    def test_conservative(self, _):
        assert get_behaviour_multiplier() == pytest.approx(0.5)

    @patch('scaling_manager._current_hour', return_value=14)
    @patch.dict('scaling_manager.DEFAULTS', {'behaviour': 'aggressive', 'off_peak_start': 22, 'off_peak_end': 6})
    def test_aggressive(self, _):
        assert get_behaviour_multiplier() == pytest.approx(2.0)


class TestDynamicThresholds:
    def test_empty_history_returns_defaults(self):
        lower, upper = calculate_dynamic_thresholds([])
        assert lower == scaling_manager.DEFAULTS['cpu_lower_threshold']
        assert upper == scaling_manager.DEFAULTS['cpu_upper_threshold']

    def test_with_history(self):
        history = [{'cpu_usage': 50}, {'cpu_usage': 60}, {'cpu_usage': 55}]
        lower, upper = calculate_dynamic_thresholds(history)
        assert lower > 0
        assert upper > lower


class TestGroupMetrics:
    def test_calculates_averages(self):
        containers = {
            "100": {"cpu": 80, "mem": 60},
            "101": {"cpu": 40, "mem": 20},
        }
        metrics = calculate_group_metrics(["100", "101"], containers)
        assert metrics['avg_cpu_usage'] == 60.0
        assert metrics['avg_mem_usage'] == 40.0
        assert metrics['total_containers'] == 2


class TestScaleOutDecision:
    def test_within_grace_period(self):
        now = datetime.now()
        assert should_scale_out(
            {'avg_cpu_usage': 99, 'avg_mem_usage': 99},
            {'horiz_cpu_upper_threshold': 80, 'horiz_memory_upper_threshold': 80, 'scale_out_grace_period': 300},
            now, now - timedelta(seconds=100)
        ) is False

    def test_above_threshold_after_grace(self):
        now = datetime.now()
        assert should_scale_out(
            {'avg_cpu_usage': 90, 'avg_mem_usage': 50},
            {'horiz_cpu_upper_threshold': 80, 'horiz_memory_upper_threshold': 80, 'scale_out_grace_period': 300},
            now, now - timedelta(seconds=600)
        ) is True

    def test_below_threshold(self):
        now = datetime.now()
        assert should_scale_out(
            {'avg_cpu_usage': 50, 'avg_mem_usage': 50},
            {'horiz_cpu_upper_threshold': 80, 'horiz_memory_upper_threshold': 80, 'scale_out_grace_period': 300},
            now, now - timedelta(seconds=600)
        ) is False


class TestScaleInDecision:
    def test_scale_in_when_idle(self):
        now = datetime.now()
        assert should_scale_in(
            {'avg_cpu_usage': 5, 'avg_mem_usage': 5, 'total_containers': 3},
            {'horiz_cpu_lower_threshold': 20, 'horiz_memory_lower_threshold': 20,
             'scale_in_grace_period': 600, 'min_containers': 1},
            now, now - timedelta(seconds=1000)
        ) is True

    def test_no_scale_in_at_min(self):
        now = datetime.now()
        assert should_scale_in(
            {'avg_cpu_usage': 5, 'avg_mem_usage': 5, 'total_containers': 1},
            {'horiz_cpu_lower_threshold': 20, 'horiz_memory_lower_threshold': 20,
             'scale_in_grace_period': 600, 'min_containers': 1},
            now, now - timedelta(seconds=1000)
        ) is False


# ═══════════════════════════════════════════════════════════════════════════
# Async scaling functions
# ═══════════════════════════════════════════════════════════════════════════

class TestScaleMemory:
    @patch('scaling_manager.run_command', new_callable=AsyncMock)
    @patch('scaling_manager.log_json_event', new_callable=AsyncMock)
    @patch('scaling_manager.get_behaviour_multiplier', return_value=1.0)
    async def test_increase_memory(self, _, mock_log, mock_cmd):
        mock_cmd.return_value = ""
        config = {'memory_min_increment': 256, 'min_decrease_chunk': 128}
        avail, changed = await scale_memory(
            "100", 90.0, 80.0, 20.0, 1024, 512, 4096, config
        )
        assert changed is True
        assert avail < 4096
        mock_cmd.assert_called_once()

    @patch('scaling_manager.run_command', new_callable=AsyncMock)
    @patch('scaling_manager.log_json_event', new_callable=AsyncMock)
    @patch('scaling_manager.get_behaviour_multiplier', return_value=1.0)
    async def test_decrease_memory(self, _, mock_log, mock_cmd):
        mock_cmd.return_value = ""
        config = {'memory_min_increment': 256, 'min_decrease_chunk': 128}
        avail, changed = await scale_memory(
            "100", 5.0, 80.0, 20.0, 2048, 512, 4096, config
        )
        assert changed is True
        assert avail > 4096

    @patch('scaling_manager.run_command', new_callable=AsyncMock)
    @patch('scaling_manager.get_behaviour_multiplier', return_value=1.0)
    async def test_no_change_in_range(self, _, mock_cmd):
        config = {'memory_min_increment': 256, 'min_decrease_chunk': 128}
        avail, changed = await scale_memory(
            "100", 50.0, 80.0, 20.0, 1024, 512, 4096, config
        )
        assert changed is False
        assert avail == 4096
        mock_cmd.assert_not_called()

    @patch('scaling_manager.run_command', new_callable=AsyncMock)
    @patch('scaling_manager.get_behaviour_multiplier', return_value=1.0)
    async def test_insufficient_memory(self, _, mock_cmd):
        config = {'memory_min_increment': 256, 'min_decrease_chunk': 128}
        avail, changed = await scale_memory(
            "100", 90.0, 80.0, 20.0, 1024, 512, 10, config  # only 10MB available
        )
        assert changed is False


class TestLogScalingEvent:
    @patch('scaling_manager.log_json_event', new_callable=AsyncMock)
    async def test_info_event(self, mock_log):
        await log_scaling_event("100", "test_event", {"key": "value"})
        mock_log.assert_called_once()
        args = mock_log.call_args
        assert args[0][0] == "100"
        assert args[0][1] == "test_event"

    @patch('scaling_manager.log_json_event', new_callable=AsyncMock)
    @patch('scaling_manager.send_detailed_notification', new_callable=AsyncMock)
    async def test_error_event_sends_notification(self, mock_notify, mock_log):
        await log_scaling_event("100", "error_event", {"err": "boom"}, error=True)
        mock_notify.assert_called_once()


class TestSendDetailedNotification:
    @patch('scaling_manager.log_json_event', new_callable=AsyncMock)
    async def test_builds_message(self, mock_log):
        # Just verify it doesn't crash and calls log_json_event
        await send_detailed_notification("100", "CPU Scaled", {"cores": 4})
        mock_log.assert_called_once()


class TestNowTz:
    def test_returns_aware_datetime(self):
        dt = _now_tz()
        assert dt.tzinfo is not None
