"""Tests for state.py (ContainerStateCache) and errors.py (typed exceptions)."""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

from errors import (
    AutoScaleError, CommandError, CommandTimeout,
    ContainerNotFound, CgroupReadError, BackendError, ConfigurationError,
)
from state import ContainerStateCache, get_state_cache


# ═══════════════════════════════════════════════════════════════════════════
# errors.py
# ═══════════════════════════════════════════════════════════════════════════

class TestExceptionHierarchy:
    def test_base_exception(self):
        with pytest.raises(AutoScaleError):
            raise AutoScaleError("generic")

    def test_command_error(self):
        err = CommandError(["pct", "set", "100"], "permission denied", returncode=1)
        assert err.cmd == ["pct", "set", "100"]
        assert err.returncode == 1
        assert "permission denied" in str(err)

    def test_command_timeout(self):
        err = CommandTimeout(["pct", "list"], timeout=30)
        assert err.timeout == 30
        assert "timed out" in str(err)
        assert isinstance(err, CommandError)

    def test_container_not_found(self):
        err = ContainerNotFound("999")
        assert err.ctid == "999"
        assert isinstance(err, AutoScaleError)

    def test_cgroup_read_error(self):
        err = CgroupReadError("100", "path not found")
        assert err.ctid == "100"
        assert "path not found" in str(err)

    def test_backend_error(self):
        assert issubclass(BackendError, AutoScaleError)

    def test_configuration_error(self):
        assert issubclass(ConfigurationError, AutoScaleError)

    def test_all_inherit_from_base(self):
        for cls in (CommandError, CommandTimeout, ContainerNotFound,
                    CgroupReadError, BackendError, ConfigurationError):
            assert issubclass(cls, AutoScaleError)

    def test_catchable_as_exception(self):
        try:
            raise CommandError(["cmd"], "fail")
        except Exception as e:
            assert isinstance(e, CommandError)


# ═══════════════════════════════════════════════════════════════════════════
# state.py
# ═══════════════════════════════════════════════════════════════════════════

class TestContainerStateCache:
    @pytest.fixture
    def cache(self):
        return ContainerStateCache()

    def test_core_count_never_zero(self, cache):
        cache.set_core_count("100", 0)
        assert cache.get_core_count("100") == 1

    def test_core_count_stores(self, cache):
        cache.set_core_count("100", 4)
        assert cache.get_core_count("100") == 4

    def test_core_count_miss(self, cache):
        assert cache.get_core_count("999") is None

    def test_cpu_negative_cache(self, cache):
        assert cache.is_cpu_negative_cached("100") is False
        cache.set_cpu_negative("100")
        assert cache.is_cpu_negative_cached("100") is True  # TTL decremented
        # Decrement until 0
        for _ in range(10):
            cache.is_cpu_negative_cached("100")
        assert cache.is_cpu_negative_cached("100") is False

    def test_mem_negative_cache(self, cache):
        assert cache.is_mem_negative_cached("100") is False
        cache.set_mem_negative("100")
        assert cache.is_mem_negative_cached("100") is True

    def test_backup_unchanged(self, cache):
        settings = {"cores": 4, "memory": 2048}
        assert cache.backup_unchanged("100", settings) is False
        cache.record_backup("100", settings)
        assert cache.backup_unchanged("100", settings) is True
        assert cache.backup_unchanged("100", {"cores": 8}) is False

    def test_pinning_unchanged(self, cache):
        assert cache.pinning_unchanged("100", "0-3") is False
        cache.record_pinning("100", "0-3")
        assert cache.pinning_unchanged("100", "0-3") is True
        assert cache.pinning_unchanged("100", "0-7") is False

    def test_container_lock(self, cache):
        lock1 = cache.get_container_lock("100")
        lock2 = cache.get_container_lock("100")
        assert lock1 is lock2
        lock3 = cache.get_container_lock("200")
        assert lock3 is not lock1

    def test_evict_stale(self, cache):
        cache.set_core_count("100", 4)
        cache.set_core_count("200", 2)
        cache.cgroup_cpu_paths["100"] = "/path"
        cache.cgroup_cpu_paths["200"] = "/path"
        cache.record_pinning("200", "0-1")
        cache.get_container_lock("200")

        cache.evict_stale({"100"})

        assert cache.get_core_count("100") == 4
        assert cache.get_core_count("200") is None
        assert "200" not in cache.cgroup_cpu_paths
        assert "200" not in cache.applied_pinning
        assert "200" not in cache._locks

    def test_evict_preserves_active(self, cache):
        cache.set_core_count("100", 4)
        cache.record_backup("100", {"cores": 4})
        cache.evict_stale({"100"})
        assert cache.get_core_count("100") == 4
        assert cache.backup_unchanged("100", {"cores": 4}) is True


class TestGetStateCacheSingleton:
    def test_returns_same_instance(self):
        c1 = get_state_cache()
        c2 = get_state_cache()
        assert c1 is c2
