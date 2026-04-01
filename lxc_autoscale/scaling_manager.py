"""Manages scaling operations for LXC containers based on resource usage (async)."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo

from config import (
    CPU_SCALE_DIVISOR, DEFAULTS, HORIZONTAL_SCALING_GROUPS,
    IGNORE_LXC, MEMORY_SCALE_FACTOR, TIMEOUT_EXTENDED,
    LXC_TIER_ASSOCIATIONS, get_app_config,
)
from lxc_utils import (
    apply_cpu_pinning, backup_container_settings,
    get_containers, get_cpu_usage, get_memory_usage,
    get_total_cores, get_total_memory, is_container_running,
    is_ignored, load_backup_settings, log_json_event,
    resolve_cpu_pinning, rollback_container_settings,
    run_command, generate_unique_snapshot_name, generate_cloned_hostname,
    validate_container_id,
)
import asyncio
from notification import send_notification_async

logger = logging.getLogger(__name__)

# Track last scale-out action per group
scale_last_action: Dict[str, datetime] = {}


def _now_tz() -> datetime:
    """Return timezone-aware current time using configured timezone."""
    cfg = get_app_config()
    return datetime.now(ZoneInfo(cfg.defaults.timezone))


def _current_hour() -> int:
    """Return current hour in the configured timezone."""
    return _now_tz().hour


# ---------------------------------------------------------------------------
# Scaling calculations (pure computation, sync)
# ---------------------------------------------------------------------------

def calculate_increment(current: float, upper_threshold: float,
                        min_increment: int, max_increment: int) -> int:
    proportional = int((current - upper_threshold) / CPU_SCALE_DIVISOR)
    return min(max(min_increment, proportional), max_increment)


def calculate_decrement(current: float, lower_threshold: float,
                        current_allocated: int, min_decrement: int,
                        min_allocated: int) -> int:
    dynamic = max(1, int((lower_threshold - current) / CPU_SCALE_DIVISOR))
    return max(min(current_allocated - min_allocated, dynamic), min_decrement)


def get_behaviour_multiplier() -> float:
    base = 1.0
    if DEFAULTS['behaviour'] == 'conservative':
        base = 0.5
    elif DEFAULTS['behaviour'] == 'aggressive':
        base = 2.0
    hour = _current_hour()
    if hour >= DEFAULTS['off_peak_start'] or hour < DEFAULTS['off_peak_end']:
        base *= 0.8
    return base


def is_off_peak() -> bool:
    """Determine if the current time is within off-peak hours (timezone-aware)."""
    hour = _current_hour()
    start = DEFAULTS['off_peak_start']
    end = DEFAULTS['off_peak_end']
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


# ---------------------------------------------------------------------------
# Notifications (async)
# ---------------------------------------------------------------------------

async def send_detailed_notification(ctid: str, event_type: str,
                                     details: Dict[str, Any]) -> None:
    tier_config = LXC_TIER_ASSOCIATIONS.get(str(ctid), DEFAULTS)
    message = f"Container {ctid} - {event_type}\n"
    message += "Current Settings:\n"
    message += f"  - CPU Thresholds: {tier_config['cpu_lower_threshold']}% - {tier_config['cpu_upper_threshold']}%\n"
    message += f"  - Memory Thresholds: {tier_config['memory_lower_threshold']}% - {tier_config['memory_upper_threshold']}%\n"
    for key, value in details.items():
        message += f"  - {key}: {value}\n"
    asyncio.create_task(send_notification_async(f"{event_type} - Container {ctid}", message))
    await log_json_event(ctid, event_type, details)


async def log_scaling_event(ctid: str, event_type: str, details: Dict[str, Any],
                            error: bool = False) -> None:
    level = logging.ERROR if error else logging.INFO
    structured = {
        'timestamp': _now_tz().isoformat(),
        'container_id': ctid,
        'event_type': event_type,
        'details': details,
    }
    logging.log(level, "Scaling event for container %s: %s", ctid, event_type)
    await log_json_event(ctid, event_type, structured)
    if error:
        await send_detailed_notification(ctid, f"Error: {event_type}", details)


# ---------------------------------------------------------------------------
# Dynamic thresholds (pure computation)
# ---------------------------------------------------------------------------

def calculate_dynamic_thresholds(
    container_history: List[Dict[str, Any]],
) -> Tuple[float, float]:
    if not container_history:
        return DEFAULTS['cpu_lower_threshold'], DEFAULTS['cpu_upper_threshold']
    usage_values = [p['cpu_usage'] for p in container_history]
    avg = sum(usage_values) / len(usage_values)
    std_dev = (sum((x - avg) ** 2 for x in usage_values) / len(usage_values)) ** 0.5
    return (max(DEFAULTS['cpu_lower_threshold'], avg - std_dev),
            min(DEFAULTS['cpu_upper_threshold'], avg + std_dev * 1.5))


# ---------------------------------------------------------------------------
# Memory scaling (async)
# ---------------------------------------------------------------------------

async def scale_memory(ctid: str, mem_usage: float, mem_upper: float,
                       mem_lower: float, current_memory: int, min_memory: int,
                       available_memory: int, config: Dict[str, Any]) -> Tuple[int, bool]:
    memory_changed = False
    validate_container_id(ctid)
    multiplier = get_behaviour_multiplier()

    if mem_usage > mem_upper:
        increment = max(
            int(config['memory_min_increment'] * multiplier),
            int((mem_usage - mem_upper) * config['memory_min_increment'] / MEMORY_SCALE_FACTOR),
        )
        if available_memory >= increment:
            new_memory = current_memory + increment
            logger.info("Container %s: memory +%dMB (%d -> %d)", ctid, increment, current_memory, new_memory)
            await run_command(["pct", "set", ctid, "-memory", str(new_memory)])
            available_memory -= increment
            memory_changed = True
            await log_json_event(ctid, "Increase Memory", f"{increment}MB")
            asyncio.create_task(send_notification_async(f"Memory Increased for Container {ctid}", f"Memory increased by {increment}MB."))
        else:
            logger.warning("Container %s: insufficient memory to increase", ctid)

    elif mem_usage < mem_lower and current_memory > min_memory:
        decrease = calculate_decrement(
            mem_usage, mem_lower, current_memory,
            int(config['min_decrease_chunk'] * multiplier), min_memory,
        )
        if decrease > 0:
            new_memory = current_memory - decrease
            logger.info("Container %s: memory -%dMB (%d -> %d)", ctid, decrease, current_memory, new_memory)
            await run_command(["pct", "set", ctid, "-memory", str(new_memory)])
            available_memory += decrease
            memory_changed = True
            await log_json_event(ctid, "Decrease Memory", f"{decrease}MB")
            asyncio.create_task(send_notification_async(f"Memory Decreased for Container {ctid}", f"Memory decreased by {decrease}MB."))

    return available_memory, memory_changed


# ---------------------------------------------------------------------------
# Tier validation (pure computation)
# ---------------------------------------------------------------------------

def validate_tier_settings(ctid: str, config: Dict[str, Any]) -> bool:
    required_fields = {
        'cpu_upper_threshold': (0, 100), 'cpu_lower_threshold': (0, 100),
        'memory_upper_threshold': (0, 100), 'memory_lower_threshold': (0, 100),
        'min_cores': (1, None), 'max_cores': (1, None), 'min_memory': (128, None),
    }
    for field, (min_val, max_val) in required_fields.items():
        value = config.get(field)
        if value is None:
            logger.error("Missing field '%s' for container %s", field, ctid)
            return False
        try:
            value = float(value)
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False
        except (ValueError, TypeError):
            return False
    if config['cpu_lower_threshold'] >= config['cpu_upper_threshold']:
        return False
    if config['memory_lower_threshold'] >= config['memory_upper_threshold']:
        return False
    if config['min_cores'] > config['max_cores']:
        return False
    return True


# ---------------------------------------------------------------------------
# Main vertical scaling (async)
# ---------------------------------------------------------------------------

async def adjust_resources(containers: Dict[str, Dict[str, Any]], energy_mode: bool) -> None:
    """Adjust CPU and memory resources for each container based on usage."""
    logger.info("Starting resource allocation...")
    total_cores = await get_total_cores()
    total_memory = await get_total_memory()
    reserved_cores = max(1, int(total_cores * DEFAULTS['reserve_cpu_percent'] / 100))
    available_cores = total_cores - reserved_cores
    available_memory = total_memory - DEFAULTS['reserve_memory_mb']

    for ctid, usage in containers.items():
        try:
            validate_container_id(ctid)
        except ValueError:
            continue

        if is_ignored(ctid):
            continue

        config = LXC_TIER_ASSOCIATIONS.get(str(ctid), DEFAULTS)
        if not validate_tier_settings(ctid, config):
            continue

        cpu_upper = config['cpu_upper_threshold']
        cpu_lower = config['cpu_lower_threshold']
        mem_upper = config['memory_upper_threshold']
        mem_lower = config['memory_lower_threshold']
        min_cores = config['min_cores']
        max_cores = config['max_cores']
        min_memory = config['min_memory']
        cpu_usage = usage['cpu']
        mem_usage = usage['mem']
        current_cores = usage['initial_cores']
        current_memory = usage['initial_memory']

        # CPU scaling
        if cpu_usage > cpu_upper:
            increment = calculate_increment(cpu_usage, cpu_upper, config['core_min_increment'], config['core_max_increment'])
            new_cores = current_cores + increment
            if new_cores <= max_cores and available_cores >= increment:
                logger.info("Container %s: CPU %.1f%%, scaling %d -> %d cores", ctid, cpu_usage, current_cores, new_cores)
                await run_command(["pct", "set", ctid, "-cores", str(new_cores)])
                available_cores -= increment
                await log_json_event(ctid, "Increase Cores", str(increment))
                asyncio.create_task(send_notification_async(f"CPU Increased for Container {ctid}", f"CPU cores increased to {new_cores}."))
        elif cpu_usage < cpu_lower and current_cores > min_cores:
            decrement = calculate_decrement(cpu_usage, cpu_lower, current_cores, config['core_min_increment'], min_cores)
            new_cores = max(min_cores, current_cores - decrement)
            if new_cores >= min_cores:
                await run_command(["pct", "set", ctid, "-cores", str(new_cores)])
                available_cores += (current_cores - new_cores)
                await log_json_event(ctid, "Decrease Cores", str(decrement))

        # Memory scaling
        available_memory, _ = await scale_memory(
            ctid, mem_usage, mem_upper, mem_lower, current_memory, min_memory, available_memory, config
        )

        # CPU pinning
        pinning_cfg = config.get('cpu_pinning')
        if pinning_cfg:
            cpu_range = await resolve_cpu_pinning(str(pinning_cfg))
            if cpu_range:
                await apply_cpu_pinning(ctid, cpu_range)

        # Energy mode
        if energy_mode and is_off_peak():
            if current_cores > min_cores:
                await run_command(["pct", "set", ctid, "-cores", str(min_cores)])
                available_cores += (current_cores - min_cores)
                await log_json_event(ctid, "Reduce Cores (Off-Peak)", str(current_cores - min_cores))
            if current_memory > min_memory:
                await run_command(["pct", "set", ctid, "-memory", str(min_memory)])
                available_memory += (current_memory - min_memory)
                await log_json_event(ctid, "Reduce Memory (Off-Peak)", f"{current_memory - min_memory}MB")

    logger.info("Final resources: %d cores, %d MB memory", available_cores, available_memory)


# ---------------------------------------------------------------------------
# Horizontal scaling (async)
# ---------------------------------------------------------------------------

def calculate_group_metrics(group_lxc: List[str],
                            containers: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    total_cpu = sum(containers[ctid]['cpu'] for ctid in group_lxc)
    total_mem = sum(containers[ctid]['mem'] for ctid in group_lxc)
    n = len(group_lxc)
    return {'avg_cpu_usage': total_cpu / n, 'avg_mem_usage': total_mem / n, 'total_containers': n}


def should_scale_out(metrics, group_config, current_time, last_action_time) -> bool:
    if current_time - last_action_time < timedelta(seconds=group_config.get('scale_out_grace_period', 300)):
        return False
    return (metrics['avg_cpu_usage'] > group_config['horiz_cpu_upper_threshold'] or
            metrics['avg_mem_usage'] > group_config['horiz_memory_upper_threshold'])


def should_scale_in(metrics, group_config, current_time, last_action_time) -> bool:
    if current_time - last_action_time < timedelta(seconds=group_config.get('scale_in_grace_period', 600)):
        return False
    return (metrics['avg_cpu_usage'] < group_config['horiz_cpu_lower_threshold'] and
            metrics['avg_mem_usage'] < group_config['horiz_memory_lower_threshold'] and
            metrics['total_containers'] > group_config.get('min_containers', 1))


async def scale_out(group_name: str, group_config: Dict[str, Any]) -> None:
    current_instances = sorted(map(int, group_config['lxc_containers']))
    starting_clone_id = group_config['starting_clone_id']
    if len(current_instances) >= group_config['max_instances']:
        logger.info("Max instances reached for %s", group_name)
        return

    new_ctid = starting_clone_id + len(
        [ctid for ctid in current_instances if int(ctid) >= starting_clone_id]
    )
    base_snapshot = group_config['base_snapshot_name']
    try:
        validate_container_id(str(new_ctid))
        validate_container_id(str(base_snapshot))
    except ValueError as e:
        logger.error("Invalid ID for scale_out in %s: %s", group_name, e)
        return

    unique_snap = generate_unique_snapshot_name("snap")
    if not await run_command(["pct", "snapshot", str(base_snapshot), unique_snap,
                              "--description", "Auto snapshot for scaling"]):
        logger.error("Failed to create snapshot %s", unique_snap)
        return

    clone_hostname = generate_cloned_hostname(base_snapshot, len(current_instances) + 1)
    if not await run_command(["pct", "clone", str(base_snapshot), str(new_ctid),
                              "--snapname", unique_snap, "--hostname", clone_hostname],
                             timeout=TIMEOUT_EXTENDED):
        logger.error("Failed to clone %s", base_snapshot)
        return

    net_type = group_config.get('clone_network_type', 'dhcp')
    if net_type == "dhcp":
        await run_command(["pct", "set", str(new_ctid), "-net0", "name=eth0,bridge=vmbr0,ip=dhcp"])
    elif net_type == "static":
        available_ips = [ip for ip in group_config.get('static_ip_range', [])
                         if ip not in current_instances]
        if available_ips:
            await run_command(["pct", "set", str(new_ctid), "-net0",
                               f"name=eth0,bridge=vmbr0,ip={available_ips[0]}/24"])

    await run_command(["pct", "start", str(new_ctid)])
    current_instances.append(new_ctid)
    group_config['lxc_containers'] = set(map(str, current_instances))
    scale_last_action[group_name] = _now_tz()
    asyncio.create_task(send_notification_async(f"Scale Out: {group_name}", f"New container {new_ctid} started."))
    await log_json_event(str(new_ctid), "Scale Out", f"Cloned {base_snapshot} to {new_ctid}.")


async def scale_in(group_name: str, group_config: Dict[str, Any]) -> None:
    current_instances = sorted(map(int, group_config['lxc_containers']))
    if len(current_instances) <= group_config.get('min_containers', 1):
        return
    remove_ctid = str(current_instances[-1])
    try:
        validate_container_id(remove_ctid)
    except ValueError as e:
        logger.error("Invalid ID for scale_in in %s: %s", group_name, e)
        return
    await run_command(["pct", "stop", remove_ctid])
    current_instances.pop()
    group_config['lxc_containers'] = set(map(str, current_instances))
    scale_last_action[group_name] = _now_tz()
    asyncio.create_task(send_notification_async(f"Scale In: {group_name}", f"Container {remove_ctid} stopped."))
    await log_json_event(remove_ctid, "Scale In", f"Container {remove_ctid} stopped.")


async def manage_horizontal_scaling(containers: Dict[str, Dict[str, Any]]) -> None:
    for group_name, group_config in HORIZONTAL_SCALING_GROUPS.items():
        try:
            current_time = _now_tz()
            last_action = scale_last_action.get(group_name, current_time - timedelta(hours=1))
            group_lxc = [ctid for ctid in group_config['lxc_containers']
                         if ctid in containers and not is_ignored(ctid)]
            if not group_lxc:
                await log_scaling_event(group_name, 'horizontal_scaling_skip',
                                        {'reason': 'No active containers'})
                continue
            metrics = calculate_group_metrics(group_lxc, containers)
            await log_scaling_event(group_name, 'group_metrics', metrics)
            if should_scale_out(metrics, group_config, current_time, last_action):
                await scale_out(group_name, group_config)
            elif should_scale_in(metrics, group_config, current_time, last_action):
                await scale_in(group_name, group_config)
        except (ValueError, KeyError, OSError) as e:
            await log_scaling_event(group_name, 'horizontal_scaling_error',
                                    {'error': str(e)}, error=True)
            logger.exception("Error in horizontal scaling for group %s", group_name)
