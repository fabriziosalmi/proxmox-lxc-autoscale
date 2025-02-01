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
    """Determine the behavior multiplier based on the current configuration.

    Returns:
         The behavior multiplier (1.0 for normal, 0.5 for conservative, 2.0 for aggressive).
    """
    if DEFAULTS['behaviour'] == 'conservative':
        multiplier = 0.5
    elif DEFAULTS['behaviour'] == 'aggressive':
        multiplier = 2.0
    else:
        multiplier = 1.0
    logging.debug(f"Behavior multiplier set to {multiplier} based on configuration: {DEFAULTS['behaviour']}")
    return multiplier


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
            logging.info(f"Increasing memory for container {ctid} by {increment}MB (current: {current_memory}MB, new: {new_memory}MB)")
            new_memory = current_memory + increment
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
            logging.info(f"Decreasing memory for container {ctid} by {decrease_amount}MB (current: {current_memory}MB, new: {new_memory}MB)")
            new_memory = current_memory - decrease_amount
            run_command(f"pct set {ctid} -memory {new_memory}")
            available_memory += decrease_amount
            memory_changed = True
            log_json_event(ctid, "Decrease Memory", f"{decrease_amount}MB")
            send_notification(f"Memory Decreased for Container {ctid}", f"Memory decreased by {decrease_amount}MB.")

    return available_memory, memory_changed


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


def validate_tier_settings(ctid: str, tier_config: Dict[str, Any]) -> bool:
    """Validate tier settings for a container.

    Args:
        ctid: The container ID.
        tier_config: The tier configuration to validate.

    Returns:
        bool: True if settings are valid, False otherwise.
    """
    required_settings = [
        ('cpu_upper_threshold', 0, 100),
        ('cpu_lower_threshold', 0, 100),
        ('memory_upper_threshold', 0, 100),
        ('memory_lower_threshold', 0, 100),
        ('min_cores', 1, None),
        ('max_cores', 1, None),
        ('min_memory', 128, None),
    ]

    for setting, min_val, max_val in required_settings:
        value = tier_config.get(setting)
        if value is None:
            logging.error(f"Missing {setting} in tier configuration for container {ctid}")
            return False
        if not isinstance(value, (int, float)):
            logging.error(f"Invalid type for {setting} in container {ctid}: {type(value)}")
            return False
        if min_val is not None and value < min_val:
            logging.error(f"{setting} cannot be less than {min_val} in container {ctid}")
            return False
        if max_val is not None and value > max_val:
            logging.error(f"{setting} cannot be greater than {max_val} in container {ctid}")
            return False

    # Additional validation for thresholds
    if tier_config['cpu_lower_threshold'] >= tier_config['cpu_upper_threshold']:
        logging.error(f"CPU thresholds misconfigured for container {ctid}: lower ({tier_config['cpu_lower_threshold']}) >= upper ({tier_config['cpu_upper_threshold']})")
        return False
    if tier_config['memory_lower_threshold'] >= tier_config['memory_upper_threshold']:
        logging.error(f"Memory thresholds misconfigured for container {ctid}: lower ({tier_config['memory_lower_threshold']}) >= upper ({tier_config['memory_upper_threshold']})")
        return False
    if tier_config['min_cores'] > tier_config['max_cores']:
        logging.error(f"Core limits misconfigured for container {ctid}: min ({tier_config['min_cores']}) > max ({tier_config['max_cores']})")
        return False

    logging.info(f"Tier settings validated successfully for container {ctid}")
    return True


def manage_horizontal_scaling(containers: Dict[str, Dict[str, Any]]) -> None:
    """Manage horizontal scaling based on CPU and memory usage across containers.

    Args:
        containers: A dictionary of container resource usage data.
    """
    for group_name, group_config in HORIZONTAL_SCALING_GROUPS.items():
        current_time = datetime.now()
        last_action_time = scale_last_action.get(group_name, current_time - timedelta(hours=1))

        # Filter out ignored containers
        group_lxc = [
            ctid for ctid in group_config['lxc_containers']
            if ctid in containers and not is_ignored(ctid)
        ]

        # Calculate average CPU and memory usage for the group
        total_cpu_usage = sum(containers[ctid]['cpu'] for ctid in group_lxc)
        total_mem_usage = sum(containers[ctid]['mem'] for ctid in group_lxc)
        num_containers = len(group_lxc)

        if num_containers > 0:
            avg_cpu_usage = total_cpu_usage / num_containers
            avg_mem_usage = total_mem_usage / num_containers
        else:
            avg_cpu_usage = 0
            avg_mem_usage = 0

        logging.debug(f"Group: {group_name} | Average CPU Usage: {avg_cpu_usage}% | Average Memory Usage: {avg_mem_usage}%")

        # Check if scaling out is needed based on usage thresholds
        if (
            avg_cpu_usage > group_config['horiz_cpu_upper_threshold']
            or avg_mem_usage > group_config['horiz_memory_upper_threshold']
        ):
            logging.debug(f"Thresholds exceeded for {group_name}. Evaluating scale-out conditions.")

            # Ensure enough time has passed since the last scaling action
            if current_time - last_action_time >= timedelta(
                seconds=group_config.get('scale_out_grace_period', 300)
            ):
                scale_out(group_name, group_config)
        else:
            logging.debug(f"No scaling needed for {group_name}. Average usage below thresholds.")


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
    logging.debug(f"Current hour: {current_hour}, Off-peak hours: {DEFAULTS['off_peak_start']} - {DEFAULTS['off_peak_end']}")
    return DEFAULTS['off_peak_start'] <= current_hour or current_hour < DEFAULTS['off_peak_end']