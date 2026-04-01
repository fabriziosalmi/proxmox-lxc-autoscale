"""Centralized container state cache.

Encapsulates all per-container caches that were previously spread across
module-level globals in lxc_utils.py. Provides a single eviction point
and eliminates the scattered global state anti-pattern.
"""

import asyncio
import logging
from threading import Lock
from typing import Any, Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ContainerStateCache:
    """Thread-safe, evictable cache for per-container runtime state.

    Replaces the module-level dictionaries: _cgroup_path_cache,
    _prev_cpu_readings, _core_count_cache, _cgroup_mem_path_cache,
    _cgroup_negative_cache, _cgroup_mem_negative_cache,
    _applied_pinning, _last_backup_settings, _container_locks.
    """

    NEGATIVE_CACHE_TTL = 5  # poll cycles before retrying failed cgroup paths

    def __init__(self):
        self.cgroup_cpu_paths: Dict[str, str] = {}
        self.prev_cpu_readings: Dict[str, Tuple[float, float]] = {}
        self.core_counts: Dict[str, int] = {}
        self.cgroup_mem_paths: Dict[str, Tuple[str, str]] = {}
        self.cpu_negative: Dict[str, int] = {}
        self.mem_negative: Dict[str, int] = {}
        self.applied_pinning: Dict[str, str] = {}
        self.last_backup: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._locks_mutex = Lock()

    def get_container_lock(self, ctid: str) -> asyncio.Lock:
        """Return a per-container async lock, creating on first access."""
        with self._locks_mutex:
            if ctid not in self._locks:
                self._locks[ctid] = asyncio.Lock()
            return self._locks[ctid]

    def set_core_count(self, ctid: str, cores: int) -> None:
        """Cache core count. Never stores 0."""
        self.core_counts[ctid] = max(1, cores)

    def get_core_count(self, ctid: str) -> Optional[int]:
        """Return cached core count or None."""
        return self.core_counts.get(ctid)

    def is_cpu_negative_cached(self, ctid: str) -> bool:
        """Check if cgroup CPU path discovery should be skipped."""
        ttl = self.cpu_negative.get(ctid, 0)
        if ttl > 0:
            self.cpu_negative[ctid] = ttl - 1
            return True
        return False

    def set_cpu_negative(self, ctid: str) -> None:
        """Mark CPU cgroup discovery as failed for N cycles."""
        self.cpu_negative[ctid] = self.NEGATIVE_CACHE_TTL

    def is_mem_negative_cached(self, ctid: str) -> bool:
        """Check if cgroup memory path discovery should be skipped."""
        ttl = self.mem_negative.get(ctid, 0)
        if ttl > 0:
            self.mem_negative[ctid] = ttl - 1
            return True
        return False

    def set_mem_negative(self, ctid: str) -> None:
        """Mark memory cgroup discovery as failed for N cycles."""
        self.mem_negative[ctid] = self.NEGATIVE_CACHE_TTL

    def backup_unchanged(self, ctid: str, settings: Dict[str, Any]) -> bool:
        """Return True if settings match last backup (skip write)."""
        return self.last_backup.get(ctid) == settings

    def record_backup(self, ctid: str, settings: Dict[str, Any]) -> None:
        """Record that a backup was written."""
        self.last_backup[ctid] = settings.copy()

    def pinning_unchanged(self, ctid: str, cpu_range: str) -> bool:
        """Return True if pinning matches last applied state."""
        return self.applied_pinning.get(ctid) == cpu_range

    def record_pinning(self, ctid: str, cpu_range: str) -> None:
        """Record that pinning was applied."""
        self.applied_pinning[ctid] = cpu_range

    def evict_stale(self, active_ctids: Set[str]) -> None:
        """Remove all cache entries for containers not in active_ctids."""
        for cache in (
            self.cgroup_cpu_paths, self.prev_cpu_readings, self.core_counts,
            self.cgroup_mem_paths, self.cpu_negative, self.mem_negative,
            self.applied_pinning, self.last_backup,
        ):
            stale = [k for k in cache if k not in active_ctids]
            for k in stale:
                del cache[k]
        with self._locks_mutex:
            stale_locks = [k for k in self._locks if k not in active_ctids]
            for k in stale_locks:
                del self._locks[k]


# Module-level singleton
_instance: Optional[ContainerStateCache] = None


def get_state_cache() -> ContainerStateCache:
    """Get the global ContainerStateCache singleton."""
    global _instance
    if _instance is None:
        _instance = ContainerStateCache()
    return _instance
