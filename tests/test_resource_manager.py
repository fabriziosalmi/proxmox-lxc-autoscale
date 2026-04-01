"""Tests for resource_manager — async data collection with mocked infrastructure."""

import asyncio
import os
import sys
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

import resource_manager
import lxc_utils


class TestCollectDataForContainer:
    @patch.object(lxc_utils, 'get_memory_usage', new_callable=AsyncMock, return_value=55.0)
    @patch.object(lxc_utils, 'get_cpu_usage', new_callable=AsyncMock, return_value=42.5)
    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    @patch.object(lxc_utils, 'is_container_running', new_callable=AsyncMock, return_value=True)
    async def test_collects_data_successfully(self, mock_running, mock_cmd,
                                               mock_cpu, mock_mem):
        mock_cmd.return_value = "cores: 4\nmemory: 2048\nhostname: test"
        result = await resource_manager.collect_data_for_container("100")
        assert result is not None
        assert "100" in result
        data = result["100"]
        assert data["cpu"] == 42.5
        assert data["mem"] == 55.0
        assert data["initial_cores"] == 4
        assert data["initial_memory"] == 2048

    @patch.object(lxc_utils, 'is_container_running', new_callable=AsyncMock, return_value=False)
    async def test_skips_stopped_container(self, mock_running):
        result = await resource_manager.collect_data_for_container("100")
        assert result is None

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock, return_value=None)
    @patch.object(lxc_utils, 'is_container_running', new_callable=AsyncMock, return_value=True)
    async def test_handles_missing_config(self, mock_running, mock_cmd):
        result = await resource_manager.collect_data_for_container("100")
        assert result is None

    @patch.object(lxc_utils, 'run_command', new_callable=AsyncMock)
    @patch.object(lxc_utils, 'is_container_running', new_callable=AsyncMock, return_value=True)
    async def test_handles_missing_cores(self, mock_running, mock_cmd):
        mock_cmd.return_value = "hostname: test\nmemory: 2048"
        result = await resource_manager.collect_data_for_container("100")
        assert result is None

    async def test_skips_ignored_container(self):
        original = resource_manager.IGNORE_LXC
        resource_manager.IGNORE_LXC = {"100"}
        try:
            result = await resource_manager.collect_data_for_container("100")
            assert result is None
        finally:
            resource_manager.IGNORE_LXC = original


class TestCollectContainerData:
    @patch.object(resource_manager, 'collect_data_for_container', new_callable=AsyncMock)
    @patch.object(lxc_utils, 'get_containers', new_callable=AsyncMock)
    async def test_gathers_all_containers(self, mock_containers, mock_collect):
        mock_containers.return_value = ["100", "101"]
        mock_collect.side_effect = [
            {"100": {"cpu": 50, "mem": 30, "initial_cores": 2, "initial_memory": 1024}},
            {"101": {"cpu": 80, "mem": 70, "initial_cores": 4, "initial_memory": 2048}},
        ]
        result = await resource_manager.collect_container_data()
        assert "100" in result
        assert "101" in result
        assert result["100"]["cpu"] == 50
        assert result["101"]["cpu"] == 80

    @patch.object(resource_manager, 'collect_data_for_container', new_callable=AsyncMock)
    @patch.object(lxc_utils, 'get_containers', new_callable=AsyncMock)
    async def test_handles_exceptions_gracefully(self, mock_containers, mock_collect):
        mock_containers.return_value = ["100", "101"]
        mock_collect.side_effect = [
            {"100": {"cpu": 50, "mem": 30, "initial_cores": 2, "initial_memory": 1024}},
            ValueError("fail"),
        ]
        result = await resource_manager.collect_container_data()
        assert "100" in result
        assert "101" not in result

    @patch.object(lxc_utils, 'get_containers', new_callable=AsyncMock, return_value=[])
    async def test_empty_containers(self, mock_containers):
        result = await resource_manager.collect_container_data()
        assert result == {}


class TestValidateTierConfig:
    def test_valid_config(self):
        config = {
            'cpu_upper_threshold': 80, 'cpu_lower_threshold': 20,
            'memory_upper_threshold': 80, 'memory_lower_threshold': 20,
            'min_cores': 1, 'max_cores': 4, 'min_memory': 512,
        }
        assert resource_manager.validate_tier_config("100", config) is True

    def test_missing_fields(self):
        assert resource_manager.validate_tier_config("100", {}) is False

    def test_inverted_cpu_thresholds(self):
        config = {
            'cpu_upper_threshold': 20, 'cpu_lower_threshold': 80,
            'memory_upper_threshold': 80, 'memory_lower_threshold': 20,
            'min_cores': 1, 'max_cores': 4, 'min_memory': 512,
        }
        assert resource_manager.validate_tier_config("100", config) is False

    def test_zero_min_memory(self):
        config = {
            'cpu_upper_threshold': 80, 'cpu_lower_threshold': 20,
            'memory_upper_threshold': 80, 'memory_lower_threshold': 20,
            'min_cores': 1, 'max_cores': 4, 'min_memory': 0,
        }
        assert resource_manager.validate_tier_config("100", config) is False

    def test_min_cores_exceeds_max(self):
        config = {
            'cpu_upper_threshold': 80, 'cpu_lower_threshold': 20,
            'memory_upper_threshold': 80, 'memory_lower_threshold': 20,
            'min_cores': 8, 'max_cores': 2, 'min_memory': 512,
        }
        assert resource_manager.validate_tier_config("100", config) is False

    def test_type_error_handled(self):
        config = {
            'cpu_upper_threshold': "not_a_number", 'cpu_lower_threshold': 20,
            'memory_upper_threshold': 80, 'memory_lower_threshold': 20,
            'min_cores': 1, 'max_cores': 4, 'min_memory': 512,
        }
        assert resource_manager.validate_tier_config("100", config) is False
