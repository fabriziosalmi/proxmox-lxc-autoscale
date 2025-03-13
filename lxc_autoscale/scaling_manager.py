"""Manages scaling operations for LXC containers based on resource usage."""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Tuple

import paramiko

from config import (CPU_SCALE_DIVISOR, DEFAULTS, HORIZONTAL_SCALING_GROUPS,
                    IGNORE_LXC, MEMORY_SCALE_FACTOR, TIMEOUT_EXTENDED, config, LXC_TIER_ASSOCIATIONS)
from lxc_utils import (backup_container_settings, get_containers, get_cpu_usage,
                       get_memory_usage, get_total_cores, get_total_memory,
                       is_container_running, is_ignored, load_backup_settings,
                       log_json_event, rollback_container_settings,
                       run_command, generate_unique_snapshot_name, generate_cloned_hostname)
from notification import send_notification


# Dictionary to track the last scale-out action for each group
scale_last_action: Dict[str, datetime] = {}


def calculate_increment(current: float, upper_threshold: float, min_increment: int, max_increment: int) -> int:
    """Calculate the increment for resource scaling based on current usage and thresholds.

    Args:
        current: Current usage percentage.
        upper_threshold: The upper threshold for usage.
        min_increment: Minimum increment value.
        max_increment: Maximum increment value.

    Returns:
        Calculated increment value.
    """
    proportional_increment = int((current - upper_threshold) / CPU_SCALE_DIVISOR)
    logging.debug(f"Calculated increment: {proportional_increment} (current: {current}, upper_threshold: {upper_threshold}, min_increment: {min_increment}, max_increment: {max_increment})")
    return min(max(min_increment, proportional_increment), max_increment)


def calculate_decrement(current: float, lower_threshold: float, current_allocated: int, min_decrement: int, min_allocated: int) -> int:
    """Calculate the decrement for resource scaling based on current usage and thresholds.

    Args:
        current: Current usage percentage.
        lower_threshold: The lower threshold for usage.
        current_allocated: Currently allocated resources (CPU or memory).
        min_decrement: Minimum decrement value.
        min_allocated: Minimum allowed allocated resources.

    Returns:
         Calculated decrement value.
    """
    dynamic_decrement = max(1, int((lower_threshold - current) / CPU_SCALE_DIVISOR))
    logging.debug(f"Calculated decrement: {dynamic_decrement} (current: {current}, lower_threshold: {lower_threshold}, current_allocated: {current_allocated}, min_decrement: {min_decrement}, min_allocated: {min_allocated})")
    return max(min(current_allocated - min_allocated, dynamic_decrement), min_decrement)


def get_behaviour_multiplier() -> float:
    """Determine the behavior multiplier based on the current configuration and historical data.

    Returns:
         The behavior multiplier with dynamic adjustment based on scaling history.
    """
    base_multiplier = 1.0
    if DEFAULTS['behaviour'] == 'conservative':
        base_multiplier = 0.5
    elif DEFAULTS['behaviour'] == 'aggressive':
        base_multiplier = 2.0

    # Apply time-based adjustment
    current_hour = datetime.now().hour
    if current_hour >= DEFAULTS['off_peak_start'] or current_hour < DEFAULTS['off_peak_end']:
        base_multiplier *= 0.8  # More conservative during off-peak hours

    logging.debug(f"Behavior multiplier set to {base_multiplier} based on configuration and time")
    return base_multiplier


def send_detailed_notification(ctid: str, event_type: str, details: Dict[str, Any]) -> None:
    """Send detailed notifications with enhanced context.

    Args:
        ctid: Container ID.
        event_type: Type of scaling event.
        details: Dictionary containing event details.
    """
    tier_config = LXC_TIER_ASSOCIATIONS.get(str(ctid), DEFAULTS)
    message = f"Container {ctid} - {event_type}\n"
    message += f"Current Settings:\n"
    message += f"  - CPU Thresholds: {tier_config['cpu_lower_threshold']}% - {tier_config['cpu_upper_threshold']}%\n"
    message += f"  - Memory Thresholds: {tier_config['memory_lower_threshold']}% - {tier_config['memory_upper_threshold']}%\n"

    for key, value in details.items():
        message += f"  - {key}: {value}\n"

    send_notification(f"{event_type} - Container {ctid}", message)
    log_json_event(ctid, event_type, details)

def calculate_dynamic_thresholds(container_history: List[Dict[str, Any]]) -> Tuple[float, float]:
    """Calculate dynamic thresholds based on historical usage patterns.

    Args:
        container_history: List of historical usage data points.

    Returns:
        Tuple containing dynamic lower and upper thresholds.
    """
    if not container_history:
        return DEFAULTS['cpu_lower_threshold'], DEFAULTS['cpu_upper_threshold']

    usage_values = [point['cpu_usage'] for point in container_history]
    avg_usage = sum(usage_values) / len(usage_values)
    std_dev = (sum((x - avg_usage) ** 2 for x in usage_values) / len(usage_values)) ** 0.5

    dynamic_lower = max(DEFAULTS['cpu_lower_threshold'], avg_usage - std_dev)
    dynamic_upper = min(DEFAULTS['cpu_upper_threshold'], avg_usage + std_dev * 1.5)

    return dynamic_lower, dynamic_upper


def scale_memory(ctid: str, mem_usage: float, mem_upper: float, mem_lower: float, current_memory: int, min_memory: int, available_memory: int, config: Dict[str, Any]) -> Tuple[int, bool]:
    """Adjust memory for a container based on current usage.

    Args:
        ctid: Container ID.
        mem_usage: Current memory usage.
        mem_upper: Upper memory threshold.
        mem_lower: Lower memory threshold.
        current_memory: Currently allocated memory.
        min_memory: Minimum memory allowed.
        available_memory: Available memory.
        config: Configuration dictionary.

    Returns:
         Updated available memory and a flag indicating if memory was changed.
    """
    memory_changed = False
    behaviour_multiplier = get_behaviour_multiplier()

    logging.info(f"Memory scaling for container {ctid} - Usage: {mem_usage}%, Upper threshold: {mem_upper}%, Lower threshold: {mem_lower}%")

    if mem_usage > mem_upper:
        increment = max(
            int(config['memory_min_increment'] * behaviour_multiplier),
            int((mem_usage - mem_upper) * config['memory_min_increment'] / MEMORY_SCALE_FACTOR),
        )
        if available_memory >= increment:
            new_memory = current_memory + increment
            logging.info(f"Increasing memory for container {ctid} by {increment}MB (current: {current_memory}MB, new: {new_memory}MB)")
            run_command(f"pct set {ctid} -memory {new_memory}")
            available_memory -= increment
            memory_changed = True
            log_json_event(ctid, "Increase Memory", f"{increment}MB")
            send_notification(f"Memory Increased for Container {ctid}", f"Memory increased by {increment}MB.")
        else:
            logging.warning(f"Not enough available memory to increase for container {ctid}")

    elif mem_usage < mem_lower and current_memory > min_memory:
        decrease_amount = calculate_decrement(
            mem_usage, mem_lower, current_memory,
            int(config['min_decrease_chunk'] * behaviour_multiplier),
            min_memory,
        )
        if decrease_amount > 0:
            new_memory = current_memory - decrease_amount
            logging.info(f"Decreasing memory for container {ctid} by {decrease_amount}MB (current: {current_memory}MB, new: {new_memory}MB)")
            run_command(f"pct set {ctid} -memory {new_memory}")
            available_memory += decrease_amount
            memory_changed = True
            log_json_event(ctid, "Decrease Memory", f"{decrease_amount}MB")
            send_notification(f"Memory Decreased for Container {ctid}", f"Memory decreased by {decrease_amount}MB.")

    return available_memory, memory_changed


def log_scaling_event(ctid: str, event_type: str, details: Dict[str, Any], error: bool = False) -> None:
    """Log scaling events with structured data for better troubleshooting.

    Args:
        ctid: Container ID.
        event_type: Type of scaling event.
        details: Dictionary containing event details.
        error: Boolean indicating if this is an error event.
    """
    log_level = logging.ERROR if error else logging.INFO
    structured_log = {
        'timestamp': datetime.now().isoformat(),
        'container_id': ctid,
        'event_type': event_type,
        'details': details
    }
    
    logging.log(log_level, f"Scaling event for container {ctid}: {event_type}")
    log_json_event(ctid, event_type, structured_log)

    if error:
        send_detailed_notification(ctid, f"Error: {event_type}", details)

def adjust_resources(containers: Dict[str, Dict[str, Any]], energy_mode: bool) -> None:
    """Adjust CPU and memory resources for each container based on usage.

    Args:
        containers: A dictionary of container resource usage data.
        energy_mode: Flag to indicate if energy-saving adjustments should be made during off-peak hours.
    """
    logging.info("Starting resource allocation process...")
    logging.info(f"Ignoring LXC Containers: {IGNORE_LXC}")

    total_cores = get_total_cores()
    total_memory = get_total_memory()

    reserved_cores = max(1, int(total_cores * DEFAULTS['reserve_cpu_percent'] / 100))
    reserved_memory = DEFAULTS['reserve_memory_mb']

    available_cores = total_cores - reserved_cores
    available_memory = total_memory - reserved_memory

    logging.info(f"Initial resources before adjustments: {available_cores} cores, {available_memory} MB memory")

    # Print current resource usage and tier settings for all running LXC containers
    logging.info("Current resource usage and tier settings for all containers:")
    for ctid, usage in containers.items():
        # Get tier configuration
        tier_config = LXC_TIER_ASSOCIATIONS.get(str(ctid), DEFAULTS)
        rounded_cpu_usage = round(usage['cpu'], 2)
        rounded_mem_usage = round(usage['mem'], 2)
        total_mem_allocated = usage['initial_memory']
        free_mem_percent = round(100 - ((rounded_mem_usage / total_mem_allocated) * 100), 2)

        logging.info(
            f"Container {ctid}:\n"
            f"  CPU usage: {rounded_cpu_usage}% (Tier limits: {tier_config['cpu_lower_threshold']}%-{tier_config['cpu_upper_threshold']}%)\n"
            f"  Memory usage: {rounded_mem_usage}MB ({free_mem_percent}% free of {total_mem_allocated}MB total)\n"
            f"  Tier settings:\n"
            f"    Min cores: {tier_config['min_cores']}, Max cores: {tier_config['max_cores']}\n"
            f"    Min memory: {tier_config['min_memory']}MB\n"
            f"    Current cores: {usage['initial_cores']}"
        )

    # Proceed with the rest of the logic for adjusting resources
    for ctid, usage in containers.items():
        # Skip if container is in ignore list
        if is_ignored(ctid):
            logging.info(f"Skipping ignored container {ctid}")
            continue

        # Retrieve the tier configuration for the container
        config = LXC_TIER_ASSOCIATIONS.get(str(ctid), DEFAULTS)
        logging.info(f"Applying tier configuration for container {ctid}: {config}")

        # Validate tier settings
        if not validate_tier_settings(ctid, config):
            logging.error(f"Invalid tier settings for container {ctid}. Skipping resource adjustment.")
            continue

        cpu_upper = config.get('cpu_upper_threshold')
        cpu_lower = config.get('cpu_lower_threshold')
        mem_upper = config.get('memory_upper_threshold')
        mem_lower = config.get('memory_lower_threshold')
        min_cores = config.get('min_cores')
        max_cores = config.get('max_cores')
        min_memory = config.get('min_memory')

        if not all([cpu_upper, cpu_lower, mem_upper, mem_lower, min_cores, max_cores, min_memory]):
            missing_keys = []
            if cpu_upper is None:
                missing_keys.append('cpu_upper_threshold')
            if cpu_lower is None:
                missing_keys.append('cpu_lower_threshold')
            if mem_upper is None:
                missing_keys.append('memory_upper_threshold')
            if mem_lower is None:
                missing_keys.append('memory_lower_threshold')
            if min_cores is None:
                missing_keys.append('min_cores')
            if max_cores is None:
                missing_keys.append('max_cores')
            if min_memory is None:
                missing_keys.append('min_memory')
            logging.error(f"Missing configuration values for container {ctid}: {', '.join(missing_keys)}. Skipping resource adjustment.")
            continue

        cpu_usage = usage['cpu']
        mem_usage = usage['mem']

        current_cores = usage["initial_cores"]
        current_memory = usage["initial_memory"]

        cores_changed = False
        memory_changed = False

        behaviour_multiplier = get_behaviour_multiplier()

        logging.info(f"Container {ctid} - CPU usage: {cpu_usage}%, Memory usage: {mem_usage}MB")

        # Adjust CPU cores if needed
        if cpu_usage > cpu_upper:
            increment = calculate_increment(cpu_usage, cpu_upper, config['core_min_increment'], config['core_max_increment'])
            new_cores = current_cores + increment

            logging.info(f"Container {ctid} - CPU usage exceeds upper threshold. Increment: {increment}, New cores: {new_cores}")

            if available_cores >= increment and new_cores <= max_cores:
                run_command(f"pct set {ctid} -cores {new_cores}")
                available_cores -= increment
                cores_changed = True
                log_json_event(ctid, "Increase Cores", f"{increment}")
                send_notification(f"CPU Increased for Container {ctid}", f"CPU cores increased to {new_cores}.")
            else:
                logging.warning(f"Container {ctid} - Not enough available cores to increase.")

        elif cpu_usage < cpu_lower and current_cores > min_cores:
            decrement = calculate_decrement(cpu_usage, cpu_lower, current_cores, config['core_min_increment'], min_cores)
            new_cores = max(min_cores, current_cores - decrement)

            logging.info(f"Container {ctid} - CPU usage below lower threshold. Decrement: {decrement}, New cores: {new_cores}")

            if new_cores >= min_cores:
                run_command(f"pct set {ctid} -cores {new_cores}")
                available_cores += (current_cores - new_cores)
                cores_changed = True
                log_json_event(ctid, "Decrease Cores", f"{decrement}")
                send_notification(f"CPU Decreased for Container {ctid}", f"CPU cores decreased to {new_cores}.")
            else:
                logging.warning(f"Container {ctid} - Cannot decrease cores below min_cores.")

        # Adjust memory if needed
        available_memory, memory_changed = scale_memory(
            ctid, mem_usage, mem_upper, mem_lower, current_memory, min_memory, available_memory, config
        )

        # Apply energy efficiency mode if enabled
        if energy_mode and is_off_peak():
            if current_cores > min_cores:
                logging.info(f"Reducing cores for energy efficiency during off-peak hours for container {ctid}...")
                run_command(f"pct set {ctid} -cores {min_cores}")
                available_cores += (current_cores - min_cores)
                log_json_event(ctid, "Reduce Cores (Off-Peak)", f"{current_cores - min_cores}")
                send_notification(f"CPU Reduced for Container {ctid}", f"CPU cores reduced to {min_cores} for energy efficiency.")
            if current_memory > min_memory:
                logging.info(f"Reducing memory for energy efficiency during off-peak hours for container {ctid}...")
                run_command(f"pct set {ctid} -memory {min_memory}")
                available_memory += (current_memory - min_memory)
                log_json_event(ctid, "Reduce Memory (Off-Peak)", f"{current_memory - min_memory}MB")
                send_notification(f"Memory Reduced for Container {ctid}", f"Memory reduced to {min_memory}MB for energy efficiency.")

    logging.info(f"Final resources after adjustments: {available_cores} cores, {available_memory} MB memory")


def validate_tier_settings(ctid: str, config: Dict[str, Any]) -> bool:
    """Validate tier settings for a container.

    Args:
        ctid: Container ID.
        config: Tier configuration dictionary.

    Returns:
        bool: True if settings are valid, False otherwise.
    """
    required_fields = {
        'cpu_upper_threshold': (0, 100),
        'cpu_lower_threshold': (0, 100),
        'memory_upper_threshold': (0, 100),
        'memory_lower_threshold': (0, 100),
        'min_cores': (1, None),
        'max_cores': (1, None),
        'min_memory': (128, None)
    }

    for field, (min_val, max_val) in required_fields.items():
        value = config.get(field)
        if value is None:
            logging.error(f"Missing required field '{field}' in tier config for container {ctid}")
            return False
        
        try:
            value = float(value)
            if min_val is not None and value < min_val:
                logging.error(f"Field '{field}' value {value} is below minimum {min_val} for container {ctid}")
                return False
            if max_val is not None and value > max_val:
                logging.error(f"Field '{field}' value {value} exceeds maximum {max_val} for container {ctid}")
                return False
        except (ValueError, TypeError):
            logging.error(f"Invalid value type for field '{field}' in container {ctid}")
            return False

    # Validate logical relationships
    if config['cpu_lower_threshold'] >= config['cpu_upper_threshold']:
        logging.error(f"CPU lower threshold must be less than upper threshold for container {ctid}")
        return False

    if config['memory_lower_threshold'] >= config['memory_upper_threshold']:
        logging.error(f"Memory lower threshold must be less than upper threshold for container {ctid}")
        return False

    if config['min_cores'] > config['max_cores']:
        logging.error(f"Minimum cores must be less than or equal to maximum cores for container {ctid}")
        return False

    return True


def manage_horizontal_scaling(containers: Dict[str, Dict[str, Any]]) -> None:
    for group_name, group_config in HORIZONTAL_SCALING_GROUPS.items():
        try:
            current_time = datetime.now()
            last_action_time = scale_last_action.get(group_name, current_time - timedelta(hours=1))

            group_lxc = [
                ctid for ctid in group_config['lxc_containers']
                if ctid in containers and not is_ignored(ctid)
            ]

            if not group_lxc:
                log_scaling_event(group_name, 'horizontal_scaling_skip', {
                    'reason': 'No active containers in group'
                })
                continue

            metrics = calculate_group_metrics(group_lxc, containers)
            log_scaling_event(group_name, 'group_metrics', metrics)

            if should_scale_out(metrics, group_config, current_time, last_action_time):
                scale_out(group_name, group_config)
                scale_last_action[group_name] = current_time
            elif should_scale_in(metrics, group_config, current_time, last_action_time):
                scale_in(group_name, group_config)
                scale_last_action[group_name] = current_time

        except Exception as e:
            log_scaling_event(group_name, 'horizontal_scaling_error', {
                'error': str(e),
                'group_config': group_config
            }, error=True)
            logging.exception(f"Error in horizontal scaling for group {group_name}")

def calculate_group_metrics(group_lxc: List[str], containers: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    total_cpu = sum(containers[ctid]['cpu'] for ctid in group_lxc)
    total_mem = sum(containers[ctid]['mem'] for ctid in group_lxc)
    num_containers = len(group_lxc)
    
    return {
        'avg_cpu_usage': total_cpu / num_containers,
        'avg_mem_usage': total_mem / num_containers,
        'total_containers': num_containers
    }

def should_scale_out(metrics: Dict[str, float], group_config: Dict[str, Any], current_time: datetime, last_action_time: datetime) -> bool:
    if current_time - last_action_time < timedelta(seconds=group_config.get('scale_out_grace_period', 300)):
        return False
        
    return (metrics['avg_cpu_usage'] > group_config['horiz_cpu_upper_threshold'] or
            metrics['avg_mem_usage'] > group_config['horiz_memory_upper_threshold'])

def should_scale_in(metrics: Dict[str, float], group_config: Dict[str, Any], current_time: datetime, last_action_time: datetime) -> bool:
    if current_time - last_action_time < timedelta(seconds=group_config.get('scale_in_grace_period', 600)):
        return False
        
    return (metrics['avg_cpu_usage'] < group_config['horiz_cpu_lower_threshold'] and
            metrics['avg_mem_usage'] < group_config['horiz_memory_lower_threshold'] and
            metrics['total_containers'] > group_config.get('min_containers', 1))


def scale_out(group_name: str, group_config: Dict[str, Any]) -> None:
    """Scale out a horizontal scaling group by cloning a new container.

    Args:
        group_name: The name of the scaling group.
        group_config: Configuration details for the scaling group.
    """
    current_instances = sorted(map(int, group_config['lxc_containers']))
    starting_clone_id = group_config['starting_clone_id']
    max_instances = group_config['max_instances']

    # Check if the maximum number of instances has been reached
    if len(current_instances) >= max_instances:
        logging.info(f"Max instances reached for {group_name}. No scale out performed.")
        return

    # Determine the next available clone ID
    new_ctid = starting_clone_id + len(
        [ctid for ctid in current_instances if int(ctid) >= starting_clone_id]
    )
    base_snapshot = group_config['base_snapshot_name']

    # Create a unique snapshot name
    unique_snapshot_name = generate_unique_snapshot_name("snap")

    logging.info(f"Creating snapshot {unique_snapshot_name} of container {base_snapshot}...")

    # Create the snapshot
    snapshot_cmd = f"pct snapshot {base_snapshot} {unique_snapshot_name} --description 'Auto snapshot for scaling'"
    if run_command(snapshot_cmd):
        logging.info(f"Snapshot {unique_snapshot_name} created successfully.")

        logging.info(f"Cloning container {base_snapshot} to create {new_ctid} using snapshot {unique_snapshot_name}...")

        # Clone the container using the snapshot, with an extended timeout
        clone_hostname = generate_cloned_hostname(base_snapshot, len(current_instances) + 1)
        clone_cmd = f"pct clone {base_snapshot} {new_ctid} --snapname {unique_snapshot_name} --hostname {clone_hostname}"
        if run_command(clone_cmd, timeout=TIMEOUT_EXTENDED):  # Extended timeout to 300 seconds
            # Network setup based on group configuration
            if group_config['clone_network_type'] == "dhcp":
                run_command(f"pct set {new_ctid} -net0 name=eth0,bridge=vmbr0,ip=dhcp")
            elif group_config['clone_network_type'] == "static":
                static_ip_range = group_config.get('static_ip_range', [])
                if static_ip_range:
                    available_ips = [
                        ip for ip in static_ip_range if ip not in current_instances
                    ]
                    if available_ips:
                        ip_address = available_ips[0]
                        run_command(
                            f"pct set {new_ctid} -net0 name=eth0,bridge=vmbr0,ip={ip_address}/24"
                        )
                    else:
                        logging.warning(
                            "No available IPs in the specified range for static IP assignment."
                        )

            # Start the new container
            run_command(f"pct start {new_ctid}")
            current_instances.append(new_ctid)

            # Update the configuration and tracking
            group_config['lxc_containers'] = set(map(str, current_instances))
            scale_last_action[group_name] = datetime.now()

            logging.info(f"Container {new_ctid} started successfully as part of {group_name}.")
            send_notification(f"Scale Out: {group_name}", f"New container {new_ctid} with hostname {clone_hostname} started.")

            # Log the scale-out event to JSON
            log_json_event(
                new_ctid,
                "Scale Out",
                f"Container {base_snapshot} cloned to {new_ctid}. {new_ctid} started.",
            )
        else:
            logging.error(
                f"Failed to clone container {base_snapshot} using snapshot {unique_snapshot_name}."
            )
    else:
        logging.error(
            f"Failed to create snapshot {unique_snapshot_name} of container {base_snapshot}."
        )


def is_off_peak() -> bool:
    """Determine if the current time is within off-peak hours.

    Returns:
         True if it is off-peak, otherwise False.
    """
    current_hour = datetime.now().hour
    start = DEFAULTS['off_peak_start']
    end = DEFAULTS['off_peak_end']
    logging.debug(f"Current hour: {current_hour}, Off-peak hours: {start} - {end}")
    if start < end:
        return start <= current_hour < end
    else:
        return current_hour >= start or current_hour < end


def collect_performance_metrics(containers: Dict[str, Dict[str, Any]]) -> None:
    """Collect and log performance metrics for analysis.

    Args:
        containers: Dictionary containing container resource usage data.
    """
    for ctid, usage in containers.items():
        if is_ignored(ctid):
            continue

        metrics = {
            'timestamp': datetime.now().isoformat(),
            'container_id': ctid,
            'cpu_usage': round(usage['cpu'], 2),
            'memory_usage': round(usage['mem'], 2),
            'total_memory': usage['initial_memory'],
            'cpu_cores': usage['initial_cores'],
            'memory_utilization': round((usage['mem'] / usage['initial_memory']) * 100, 2)
        }

        log_json_event(ctid, 'performance_metrics', metrics)