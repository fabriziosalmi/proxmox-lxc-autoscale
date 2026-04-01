"""Tests for boost/revert temporary scaling model."""

import asyncio
import json
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

from boost import BoostManager, BoostRecord


@pytest.fixture
def mgr(tmp_path):
    """Fresh BoostManager with temp state file."""
    return BoostManager(str(tmp_path / "boost_state.json"))


# ═══════════════════════════════════════════════════════════════════════════
# BoostRecord
# ═══════════════════════════════════════════════════════════════════════════

class TestBoostRecord:
    def test_creation(self):
        r = BoostRecord(original=2, boosted=3, factor=1.5,
                        boosted_at=time.time(), duration=120)
        assert r.original == 2
        assert r.boosted == 3
        assert r.factor == 1.5
        assert r.duration == 120


# ═══════════════════════════════════════════════════════════════════════════
# Saturation tracking
# ═══════════════════════════════════════════════════════════════════════════

class TestSaturationTracking:
    def test_increments_on_saturation(self, mgr):
        assert mgr.check_saturation("100", "cpu", 0.96, 0.95) is False  # 1/3
        assert mgr.check_saturation("100", "cpu", 0.97, 0.95) is False  # 2/3
        assert mgr.check_saturation("100", "cpu", 0.98, 0.95) is True   # 3/3

    def test_resets_on_drop(self, mgr):
        mgr.check_saturation("100", "cpu", 0.96, 0.95)  # 1
        mgr.check_saturation("100", "cpu", 0.97, 0.95)  # 2
        mgr.check_saturation("100", "cpu", 0.50, 0.95)  # reset!
        assert mgr.check_saturation("100", "cpu", 0.96, 0.95) is False  # 1 again

    def test_independent_resources(self, mgr):
        mgr.check_saturation("100", "cpu", 0.96, 0.95)
        mgr.check_saturation("100", "cpu", 0.96, 0.95)
        mgr.check_saturation("100", "cpu", 0.96, 0.95)
        # CPU hit 3, but memory should still be at 0
        assert mgr.check_saturation("100", "memory", 0.96, 0.95) is False

    def test_reset_saturation(self, mgr):
        mgr.check_saturation("100", "cpu", 0.96, 0.95)
        mgr.check_saturation("100", "cpu", 0.96, 0.95)
        mgr.reset_saturation("100", "cpu")
        assert mgr.check_saturation("100", "cpu", 0.96, 0.95) is False


# ═══════════════════════════════════════════════════════════════════════════
# Boost computation
# ═══════════════════════════════════════════════════════════════════════════

class TestComputeBoost:
    def test_primary_factor_fits(self):
        val, factor = BoostManager.compute_boost(
            current=4, factor=1.5, fallback_factor=1.25,
            available=10, is_cpu=True,
        )
        assert val == 6  # ceil(4 * 1.5) = 6
        assert factor == 1.5

    def test_fallback_when_primary_exceeds(self):
        val, factor = BoostManager.compute_boost(
            current=4, factor=1.5, fallback_factor=1.25,
            available=1, is_cpu=True,  # only 1 core available
        )
        assert val == 5  # ceil(4 * 1.25) = 5
        assert factor == 1.25

    def test_none_when_neither_fits(self):
        val, factor = BoostManager.compute_boost(
            current=4, factor=1.5, fallback_factor=1.25,
            available=0, is_cpu=True,
        )
        assert val is None
        assert factor == 0.0

    def test_memory_boost(self):
        val, factor = BoostManager.compute_boost(
            current=1024, factor=1.5, fallback_factor=1.25,
            available=1000, is_cpu=False,
        )
        assert val == 1536  # ceil(1024 * 1.5)
        assert factor == 1.5


# ═══════════════════════════════════════════════════════════════════════════
# Boost lifecycle
# ═══════════════════════════════════════════════════════════════════════════

class TestBoostLifecycle:
    def test_apply_and_check(self, mgr):
        assert mgr.is_boosted("100", "cpu") is False
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        assert mgr.is_boosted("100", "cpu") is True
        rec = mgr.get_boost("100", "cpu")
        assert rec.original == 2
        assert rec.boosted == 3

    def test_not_expired_immediately(self, mgr):
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        assert mgr.get_expired("100") == []

    def test_expired_after_duration(self, mgr):
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 1)
        # Simulate time passing
        mgr._active["100"]["cpu"].boosted_at = time.time() - 10
        expired = mgr.get_expired("100")
        assert len(expired) == 1
        assert expired[0][0] == "cpu"

    def test_revert(self, mgr):
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        original = mgr.revert("100", "cpu")
        assert original == 2
        assert mgr.is_boosted("100", "cpu") is False

    def test_revert_not_boosted(self, mgr):
        assert mgr.revert("100", "cpu") is None

    def test_manual_change_detection(self, mgr):
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        assert mgr.detect_manual_change("100", "cpu", 3) is False  # same
        assert mgr.detect_manual_change("100", "cpu", 4) is True   # changed!

    def test_adopt_manual_change(self, mgr):
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        mgr.adopt_manual_change("100", "cpu", 4)
        assert mgr.is_boosted("100", "cpu") is False

    def test_independent_cpu_memory(self, mgr):
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        mgr.apply_boost("100", "memory", 1024, 1536, 1.5, 120)
        assert mgr.is_boosted("100", "cpu") is True
        assert mgr.is_boosted("100", "memory") is True
        mgr.revert("100", "cpu")
        assert mgr.is_boosted("100", "cpu") is False
        assert mgr.is_boosted("100", "memory") is True


# ═══════════════════════════════════════════════════════════════════════════
# Persistence
# ═══════════════════════════════════════════════════════════════════════════

class TestPersistence:
    def test_save_and_load(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        mgr1 = BoostManager(state_file)
        mgr1.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        mgr1.apply_boost("100", "memory", 1024, 1536, 1.5, 120)

        mgr2 = BoostManager(state_file)
        mgr2.load()
        assert mgr2.is_boosted("100", "cpu") is True
        assert mgr2.is_boosted("100", "memory") is True
        rec = mgr2.get_boost("100", "cpu")
        assert rec.original == 2

    def test_load_missing_file(self, tmp_path):
        mgr = BoostManager(str(tmp_path / "nonexistent.json"))
        mgr.load()  # should not crash
        assert mgr.active_count == 0

    def test_state_file_permissions(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        mgr = BoostManager(state_file)
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        mode = os.stat(state_file).st_mode & 0o777
        assert mode == 0o600

    def test_active_count(self, mgr):
        assert mgr.active_count == 0
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        assert mgr.active_count == 1
        mgr.apply_boost("100", "memory", 1024, 1536, 1.5, 120)
        assert mgr.active_count == 2
        mgr.revert("100", "cpu")
        assert mgr.active_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# Reconciliation
# ═══════════════════════════════════════════════════════════════════════════

class TestReconciliation:
    async def test_reconcile_keeps_matching_boost(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        mgr = BoostManager(state_file)
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)

        async def mock_cmd(cmd, **kw):
            return "cores: 3\nmemory: 1024"

        await mgr.reconcile(mock_cmd)
        assert mgr.is_boosted("100", "cpu") is True

    async def test_reconcile_detects_manual_change(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        mgr = BoostManager(state_file)
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)

        async def mock_cmd(cmd, **kw):
            return "cores: 4\nmemory: 1024"  # admin changed from 3 to 4

        await mgr.reconcile(mock_cmd)
        assert mgr.is_boosted("100", "cpu") is False

    async def test_reconcile_removes_deleted_container(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        mgr = BoostManager(state_file)
        mgr.apply_boost("999", "cpu", 2, 3, 1.5, 120)

        async def mock_cmd(cmd, **kw):
            return None  # container doesn't exist

        await mgr.reconcile(mock_cmd)
        assert mgr.active_count == 0


# ═══════════════════════════════════════════════════════════════════════════
# Eviction
# ═══════════════════════════════════════════════════════════════════════════

class TestEviction:
    def test_evict_removes_inactive(self, mgr):
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        mgr.apply_boost("200", "cpu", 4, 6, 1.5, 120)
        mgr.evict_stale({"100"})
        assert mgr.is_boosted("100", "cpu") is True
        assert mgr.is_boosted("200", "cpu") is False

    def test_evict_no_active(self, mgr):
        mgr.evict_stale({"100"})  # should not crash


# ═══════════════════════════════════════════════════════════════════════════
# Integration: _adjust_boost_mode
# ═══════════════════════════════════════════════════════════════════════════

class TestAdjustBoostMode:
    @patch('scaling_manager.run_command', new_callable=AsyncMock, return_value="OK")
    @patch('scaling_manager.log_json_event', new_callable=AsyncMock)
    async def test_boost_applied_on_saturation(self, m_log, m_cmd):
        from scaling_manager import _adjust_boost_mode
        mgr = BoostManager("/dev/null")
        # Pre-saturate for 2 samples
        mgr.check_saturation("100", "cpu", 0.96, 0.95)
        mgr.check_saturation("100", "cpu", 0.96, 0.95)
        config = {
            'saturation_threshold': 0.95, 'boost_factor': 1.5,
            'boost_fallback_factor': 1.25, 'boost_duration': 120,
            'consecutive_samples': 3,
        }
        # Third sample triggers boost
        await _adjust_boost_mode(
            "100", config, mgr,
            cpu_usage=96.0, mem_usage=50.0,
            current_cores=2, current_memory=1024,
            available_cores=10, available_memory=4096,
        )
        assert mgr.is_boosted("100", "cpu") is True
        calls = " ".join(str(c) for c in m_cmd.call_args_list)
        assert "-cores" in calls
        assert "3" in calls  # ceil(2 * 1.5) = 3

    @patch('scaling_manager.run_command', new_callable=AsyncMock, return_value="OK")
    @patch('scaling_manager.log_json_event', new_callable=AsyncMock)
    async def test_boost_revert_on_expiry(self, m_log, m_cmd):
        from scaling_manager import _adjust_boost_mode
        mgr = BoostManager("/dev/null")
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 1)
        mgr._active["100"]["cpu"].boosted_at = time.time() - 10  # expired
        config = {
            'saturation_threshold': 0.95, 'boost_factor': 1.5,
            'boost_fallback_factor': 1.25, 'boost_duration': 1,
            'consecutive_samples': 3,
        }
        await _adjust_boost_mode(
            "100", config, mgr,
            cpu_usage=50.0, mem_usage=50.0,
            current_cores=3, current_memory=1024,
            available_cores=10, available_memory=4096,
        )
        assert mgr.is_boosted("100", "cpu") is False
        calls = " ".join(str(c) for c in m_cmd.call_args_list)
        assert "-cores" in calls
        assert "2" in calls  # reverted to original

    @patch('scaling_manager.run_command', new_callable=AsyncMock, return_value="OK")
    @patch('scaling_manager.log_json_event', new_callable=AsyncMock)
    async def test_manual_change_adopted(self, m_log, m_cmd):
        from scaling_manager import _adjust_boost_mode
        mgr = BoostManager("/dev/null")
        mgr.apply_boost("100", "cpu", 2, 3, 1.5, 120)
        config = {
            'saturation_threshold': 0.95, 'boost_factor': 1.5,
            'boost_fallback_factor': 1.25, 'boost_duration': 120,
            'consecutive_samples': 3,
        }
        # Admin changed cores from 3 to 8
        await _adjust_boost_mode(
            "100", config, mgr,
            cpu_usage=50.0, mem_usage=50.0,
            current_cores=8, current_memory=1024,
            available_cores=10, available_memory=4096,
        )
        assert mgr.is_boosted("100", "cpu") is False  # adopted

    @patch('scaling_manager.run_command', new_callable=AsyncMock, return_value="OK")
    @patch('scaling_manager.log_json_event', new_callable=AsyncMock)
    async def test_no_boost_below_threshold(self, m_log, m_cmd):
        from scaling_manager import _adjust_boost_mode
        mgr = BoostManager("/dev/null")
        config = {
            'saturation_threshold': 0.95, 'boost_factor': 1.5,
            'boost_fallback_factor': 1.25, 'boost_duration': 120,
            'consecutive_samples': 3,
        }
        await _adjust_boost_mode(
            "100", config, mgr,
            cpu_usage=50.0, mem_usage=50.0,
            current_cores=2, current_memory=1024,
            available_cores=10, available_memory=4096,
        )
        assert mgr.is_boosted("100", "cpu") is False
        m_cmd.assert_not_called()
