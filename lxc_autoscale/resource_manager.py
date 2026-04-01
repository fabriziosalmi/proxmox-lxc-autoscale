"""Manages resource allocation and scaling for LXC containers (async).

Performance optimizations:
- #1: Bulk data collection — single ``pct list`` + concurrent per-container fetch
- #3: Core counts cached from config reads, not re-queried for CPU calc
- #6: Notifications dispatched as fire-and-forget tasks
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import lxc_utils
import scaling_manager
from config import DEFAULTS, LXC_TIER_ASSOCIATIONS, IGNORE_LXC
from notification import send_notification_async

logger = logging.getLogger(__name__)


async def collect_data_for_container(ctid: str) -> Optional[Dict[str, Any]]:
    """Collect resource usage data for a single LXC container."""
    if ctid in IGNORE_LXC:
        return None
    if not await lxc_utils.is_container_running(ctid):
        return None

    try:
        config_output = await lxc_utils.run_command(["pct", "config", ctid])
        if not config_output:
            raise ValueError(f"No configuration found for container {ctid}")

        cores = memory = None
        for line in config_output.splitlines():
            if ':' not in line:
                continue
            key, value = [x.strip() for x in line.split(':', 1)]
            if key == 'cores':
                cores = int(value)
            elif key == 'memory':
                memory = int(value)

        if cores is None or memory is None:
            raise ValueError(f"Missing cores or memory for container {ctid}")

        # #3: Cache core count so CPU calc doesn't re-query pct config
        lxc_utils.set_cached_core_count(ctid, cores)

        cpu_usage = await lxc_utils.get_cpu_usage(ctid)
        mem_usage = await lxc_utils.get_memory_usage(ctid)
        if cpu_usage is None or mem_usage is None:
            raise ValueError(f"Failed to get resource usage for container {ctid}")

        return {
            ctid: {
                "cpu": cpu_usage,
                "mem": mem_usage,
                "initial_cores": cores,
                "initial_memory": memory,
            }
        }
    except (ValueError, OSError) as e:
        logger.error("Error collecting data for container %s: %s", ctid, e)
        return None


async def collect_container_data() -> Dict[str, Dict[str, Any]]:
    """Collect resource usage data for all containers concurrently.

    #1: Uses a single ``pct list`` then fans out per-container queries
    via ``asyncio.gather`` for maximum concurrency.
    """
    containers: Dict[str, Dict[str, Any]] = {}
    ctids = await lxc_utils.get_containers()
    ctids = [c for c in ctids if c not in IGNORE_LXC]

    tasks = [collect_data_for_container(ctid) for ctid in ctids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for ctid, result in zip(ctids, results):
        if isinstance(result, Exception):
            logger.error("Failed to collect data for container %s: %s", ctid, result)
            if isinstance(result, ConnectionError):
                # #6: Fire-and-forget notification
                asyncio.create_task(send_notification_async(
                    "Resource Collection Error",
                    f"Connection issue collecting data for {ctid}: {result}",
                    priority=8,
                ))
            continue
        if result:
            containers.update(result)
            tier = LXC_TIER_ASSOCIATIONS.get(ctid)
            containers[ctid]["tier"] = tier
            containers[ctid]["last_update"] = time.time()

    return containers


def validate_tier_config(ctid: str, tier_config: Dict[str, Any]) -> bool:
    required_fields = [
        'cpu_upper_threshold', 'cpu_lower_threshold',
        'memory_upper_threshold', 'memory_lower_threshold',
        'min_cores', 'max_cores', 'min_memory',
    ]
    missing = [f for f in required_fields if f not in tier_config]
    if missing:
        logger.error("Missing tier fields for container %s: %s", ctid, ", ".join(missing))
        return False
    try:
        for resource, lower, upper in [
            ('CPU', 'cpu_lower_threshold', 'cpu_upper_threshold'),
            ('Memory', 'memory_lower_threshold', 'memory_upper_threshold'),
        ]:
            if not (0 <= tier_config[lower] < tier_config[upper] <= 100):
                return False
        if not (0 < tier_config['min_cores'] <= tier_config['max_cores']):
            return False
        if tier_config['min_memory'] <= 0:
            return False
        return True
    except (TypeError, ValueError) as e:
        logger.error("Invalid tier values for %s: %s", ctid, e)
        return False


async def main_loop(poll_interval: int, energy_mode: bool) -> None:
    """Main async loop — resource allocation and scaling."""
    while True:
        loop_start = time.time()
        logger.info("Starting resource allocation process...")

        try:
            containers = await collect_container_data()

            for ctid in list(containers.keys()):
                tier = LXC_TIER_ASSOCIATIONS.get(ctid)
                containers[ctid]["tier"] = tier
                if tier and not validate_tier_config(ctid, tier):
                    logger.error("Invalid tier for container %s, skipping", ctid)
                    del containers[ctid]

            await scaling_manager.adjust_resources(containers, energy_mode)
            await scaling_manager.manage_horizontal_scaling(containers)

            elapsed = time.time() - loop_start
            logger.info("Resource allocation completed in %.2fs", elapsed)

            if elapsed < poll_interval:
                await asyncio.sleep(poll_interval - elapsed)
            else:
                logger.warning("Loop took longer than poll interval (%.2fs > %ds)",
                               elapsed, poll_interval)

        except (ValueError, OSError, KeyError) as e:
            logger.error("Error in main loop: %s", e)
            logger.exception("Exception traceback:")
            await asyncio.sleep(poll_interval)
