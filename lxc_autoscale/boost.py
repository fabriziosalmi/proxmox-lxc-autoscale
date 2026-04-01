"""Boost/revert temporary scaling model.

Implements a state machine where containers receive a temporary resource
boost when saturated for N consecutive polls, then automatically revert
after a configurable duration. Detects manual changes during boost and
adopts them as the new baseline.

State machine per container, per resource (CPU and memory independent):

    NORMAL → saturated for N consecutive polls → BOOSTED
    BOOSTED → boost_duration expires →
      ├─ config changed manually → adopt new baseline, NORMAL
      ├─ still saturated → revert, re-boost next cycle
      └─ not saturated → revert to original, NORMAL
"""

import json
import logging
import math
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from state import get_state_cache

logger = logging.getLogger(__name__)


@dataclass
class BoostRecord:
    """Tracks an active boost for a single resource of a single container."""
    original: float       # value before boost (cores or MB)
    boosted: float        # value after boost
    factor: float         # multiplier applied (1.5 or 1.25)
    boosted_at: float     # time.time() when boost was applied
    duration: int         # seconds until auto-revert


class BoostManager:
    """Manages temporary resource boosts with automatic revert.

    Args:
        state_file: path to JSON persistence file for active boosts.
    """

    def __init__(self, state_file: str):
        self._state_file = state_file
        # ctid -> {"cpu": BoostRecord, "memory": BoostRecord}
        self._active: Dict[str, Dict[str, BoostRecord]] = {}
        self._state = get_state_cache()

    # ------------------------------------------------------------------
    # Saturation tracking
    # ------------------------------------------------------------------

    def check_saturation(self, ctid: str, resource: str,
                         usage_fraction: float, threshold: float) -> bool:
        """Increment saturation counter. Return True if threshold met for N samples."""
        counts = self._state.saturation_counts.setdefault(ctid, {})
        if usage_fraction >= threshold:
            counts[resource] = counts.get(resource, 0) + 1
        else:
            counts[resource] = 0
        return counts.get(resource, 0) >= self._required_samples(ctid)

    def _required_samples(self, ctid: str) -> int:
        """Get consecutive_samples from tier config or default."""
        from config import LXC_TIER_ASSOCIATIONS, DEFAULTS
        cfg = LXC_TIER_ASSOCIATIONS.get(ctid, DEFAULTS)
        return cfg.get('consecutive_samples', 3)

    def reset_saturation(self, ctid: str, resource: str) -> None:
        """Reset saturation counter (after boost applied or revert)."""
        counts = self._state.saturation_counts.get(ctid, {})
        counts[resource] = 0

    # ------------------------------------------------------------------
    # Boost computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_boost(
        current: float,
        factor: float,
        fallback_factor: float,
        available: float,
        is_cpu: bool = False,
    ) -> Tuple[Optional[float], float]:
        """Compute boosted value with fallback.

        Returns (new_value, factor_used) or (None, 0) if neither fits.
        For CPU (cores): rounds up to int. For memory (MB): rounds up to int.
        """
        for f in (factor, fallback_factor):
            candidate = current * f
            if is_cpu:
                candidate = math.ceil(candidate)
            else:
                candidate = math.ceil(candidate)
            needed = candidate - current
            if needed <= available:
                return candidate, f
        return None, 0.0

    # ------------------------------------------------------------------
    # Boost lifecycle
    # ------------------------------------------------------------------

    def is_boosted(self, ctid: str, resource: str) -> bool:
        """Check if a container resource is currently boosted."""
        return resource in self._active.get(ctid, {})

    def get_boost(self, ctid: str, resource: str) -> Optional[BoostRecord]:
        """Get the active boost record, if any."""
        return self._active.get(ctid, {}).get(resource)

    def apply_boost(self, ctid: str, resource: str,
                    original: float, boosted: float,
                    factor: float, duration: int) -> None:
        """Record a new boost and persist state."""
        record = BoostRecord(
            original=original, boosted=boosted, factor=factor,
            boosted_at=time.time(), duration=duration,
        )
        self._active.setdefault(ctid, {})[resource] = record
        self.reset_saturation(ctid, resource)
        self._save()
        logger.info(
            "Container %s: %s boosted %.0f -> %.0f (x%.2f, %ds)",
            ctid, resource, original, boosted, factor, duration,
        )

    def get_expired(self, ctid: str) -> List[Tuple[str, BoostRecord]]:
        """Return list of (resource, record) for expired boosts on a container."""
        now = time.time()
        expired = []
        for resource, rec in self._active.get(ctid, {}).items():
            if now - rec.boosted_at >= rec.duration:
                expired.append((resource, rec))
        return expired

    def detect_manual_change(self, ctid: str, resource: str,
                             live_value: float) -> bool:
        """Check if admin changed the value during boost.

        Returns True if live config differs from boosted value,
        meaning an admin modified it via Proxmox UI.
        """
        rec = self.get_boost(ctid, resource)
        if rec is None:
            return False
        return abs(live_value - rec.boosted) > 0.01

    def adopt_manual_change(self, ctid: str, resource: str,
                            live_value: float) -> None:
        """Admin changed config during boost — adopt as new baseline."""
        logger.info(
            "Container %s: %s was manually changed to %.0f during boost, adopting as baseline",
            ctid, resource, live_value,
        )
        self._remove_boost(ctid, resource)

    def revert(self, ctid: str, resource: str) -> Optional[float]:
        """Remove boost record and return original value for revert command.

        Returns the original value to revert to, or None if not boosted.
        """
        rec = self.get_boost(ctid, resource)
        if rec is None:
            return None
        original = rec.original
        logger.info(
            "Container %s: %s reverting %.0f -> %.0f (boost expired after %ds)",
            ctid, resource, rec.boosted, original, rec.duration,
        )
        self._remove_boost(ctid, resource)
        return original

    def _remove_boost(self, ctid: str, resource: str) -> None:
        """Remove a single boost record and persist."""
        boosts = self._active.get(ctid, {})
        boosts.pop(resource, None)
        if not boosts:
            self._active.pop(ctid, None)
        self.reset_saturation(ctid, resource)
        self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Persist active boosts to JSON file."""
        try:
            os.makedirs(os.path.dirname(self._state_file) or '.', exist_ok=True)
            data = {}
            for ctid, resources in self._active.items():
                data[ctid] = {res: asdict(rec) for res, rec in resources.items()}
            fd = os.open(self._state_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error("Failed to save boost state: %s", e)

    def load(self) -> None:
        """Load persisted boost state from JSON file."""
        if not os.path.exists(self._state_file):
            return
        try:
            with open(self._state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for ctid, resources in data.items():
                for resource, rec_data in resources.items():
                    self._active.setdefault(ctid, {})[resource] = BoostRecord(**rec_data)
            logger.info("Loaded %d active boosts from %s",
                        sum(len(r) for r in self._active.values()),
                        self._state_file)
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.error("Failed to load boost state: %s", e)

    async def reconcile(self, run_command_fn) -> None:
        """Reconcile persisted boosts against live Proxmox config.

        For each persisted boost:
        - If container doesn't exist: remove boost
        - If live value != boosted value: admin changed it, remove boost
        - If boost expired: queue revert
        - Otherwise: keep boost active
        """
        from lxc_utils import validate_container_id
        stale = []
        for ctid in list(self._active.keys()):
            try:
                validate_container_id(ctid)
            except ValueError:
                stale.append(ctid)
                continue

            output = await run_command_fn(["pct", "config", ctid])
            if output is None:
                stale.append(ctid)
                continue

            live_cores = 0
            live_memory = 0
            for line in output.splitlines():
                if line.startswith("cores:"):
                    live_cores = int(line.split()[1])
                elif line.startswith("memory:"):
                    live_memory = int(line.split()[1])

            for resource in list(self._active.get(ctid, {}).keys()):
                rec = self._active[ctid][resource]
                live = live_cores if resource == "cpu" else live_memory
                if abs(live - rec.boosted) > 0.01:
                    logger.info(
                        "Reconcile: container %s %s was %.0f (boosted), now %.0f — adopting",
                        ctid, resource, rec.boosted, live,
                    )
                    self._remove_boost(ctid, resource)

        for ctid in stale:
            logger.info("Reconcile: container %s no longer exists, removing boost", ctid)
            self._active.pop(ctid, None)

        if stale:
            self._save()

    def evict_stale(self, active_ctids: Set[str]) -> None:
        """Remove boost records for containers no longer active."""
        stale = [k for k in self._active if k not in active_ctids]
        if stale:
            for k in stale:
                del self._active[k]
            self._save()

    @property
    def active_count(self) -> int:
        """Total number of active boost records."""
        return sum(len(r) for r in self._active.values())
