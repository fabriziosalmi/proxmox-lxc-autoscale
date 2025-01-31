"""Manages resource allocation and scaling for LXC containers."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import paramiko

import lxc_utils
import scaling_manager
from config import config
from notification import send_notification


IGNORE_LXC = set(config.get("DEFAULTS", {}).get("ignore_lxc", []))  # Example list of containers to ignore


def collect_data_for_container(ctid: str) -> Optional[Dict[str, Any]]:
    """Collect resource usage data for a single LXC container.

    Args:
        ctid: The container ID.

    Returns:
        A dictionary with resource data for the container, or None if the container is not running.
    """
    if not lxc_utils.is_container_running(ctid):
        logging.debug(f"Container {ctid} is not running")
        return None

    try:
        # Get container config more reliably
        config_output = lxc_utils.run_command(f"pct config {ctid}")
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
            raise ValueError(f"Missing cores or memory configuration for container {ctid}")

        # Get resource usage with better error handling
        cpu_usage = lxc_utils.get_cpu_usage(ctid)
        mem_usage = lxc_utils.get_memory_usage(ctid)

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
    except Exception as e:
        logging.error(f"Error collecting data for container {ctid}: {str(e)}")
        return None


def collect_container_data() -> Dict[str, Dict[str, Any]]:
    """Collect resource usage data for all LXC containers."""
    containers: Dict[str, Dict[str, Any]] = {}
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(collect_data_for_container, ctid): ctid
            for ctid in lxc_utils.get_containers()
            if ctid not in IGNORE_LXC
        }
        
        for future in as_completed(futures):
            ctid = futures[future]
            try:
                result = future.result()
                if result:
                    containers.update(result)
                    # Apply tier settings with validation
                    tier_config = config.get("tiers", {}).get(ctid)
                    if tier_config:
                        if validate_tier_config(ctid, tier_config):
                            containers[ctid].update(tier_config)
                            logging.info(f"Applied validated tier settings for container {ctid}: {tier_config}")
                        else:
                            logging.warning(f"Using default settings for container {ctid} due to invalid tier configuration")
                            containers[ctid].update(config.get("DEFAULTS", {}))
                    else:
                        logging.info(f"No tier settings found for container {ctid}, using defaults")
                        containers[ctid].update(config.get("DEFAULTS", {}))
            except Exception as e:
                logging.error(f"Error collecting data for container {ctid}: {e}")
    
    return containers

def validate_tier_config(ctid: str, tier_config: Dict[str, Any]) -> bool:
    """Validate tier configuration settings.

    Args:
        ctid: The container ID.
        tier_config: The tier configuration to validate.

    Returns:
        bool: True if configuration is valid, False otherwise.
    """
    required_fields = [
        'cpu_upper_threshold',
        'cpu_lower_threshold',
        'memory_upper_threshold',
        'memory_lower_threshold',
        'min_cores',
        'max_cores',
        'min_memory'
    ]

    # Check for missing fields
    missing = [field for field in required_fields if field not in tier_config]
    if missing:
        logging.error(f"Missing required tier configuration fields for container {ctid}: {', '.join(missing)}")
        return False

    # Validate threshold relationships
    try:
        thresholds = [
            ('CPU', 'cpu_lower_threshold', 'cpu_upper_threshold'),
            ('Memory', 'memory_lower_threshold', 'memory_upper_threshold')
        ]
        
        for resource, lower, upper in thresholds:
            if not (0 <= tier_config[lower] < tier_config[upper] <= 100):
                logging.error(
                    f"Invalid {resource} thresholds for container {ctid}: "
                    f"lower={tier_config[lower]}, upper={tier_config[upper]}"
                )
                return False

        if not (0 < tier_config['min_cores'] <= tier_config['max_cores']):
            logging.error(
                f"Invalid core limits for container {ctid}: "
                f"min={tier_config['min_cores']}, max={tier_config['max_cores']}"
            )
            return False

        if tier_config['min_memory'] <= 0:
            logging.error(f"Invalid minimum memory for container {ctid}: {tier_config['min_memory']}")
            return False

        logging.info(f"Tier configuration validated successfully for container {ctid}")
        return True

    except (TypeError, ValueError) as e:
        logging.error(f"Invalid tier configuration values for container {ctid}: {e}")
        return False


def main_loop(poll_interval: int, energy_mode: bool) -> None:
    """Main loop that handles the resource allocation and scaling process.

    Args:
        poll_interval: The interval in seconds between each resource allocation process.
        energy_mode: A flag to indicate if energy efficiency mode should be enabled during off-peak hours.
    """
    while True:
        loop_start_time = time.time()
        logging.info("Starting resource allocation process...")

        try:
            # Log time before collecting data
            collect_start_time = time.time()
            logging.debug("Collecting container data...")
            containers = collect_container_data()
            collect_duration = time.time() - collect_start_time
            logging.debug(f"Container data collection took {collect_duration:.2f} seconds.")

            # Validate tier settings from config.yaml
            for ctid, data in containers.items():
                tier = config.get("tiers", {}).get(ctid)
                containers[ctid]["tier"] = tier
                if tier:
                    logging.info(f"Applying tier settings for container {ctid}: {tier}")
                else:
                    logging.info(f"No tier settings found for container {ctid} in /etc/lxc_autoscale/lxc_autoscale.yml")

            # Log time before adjusting resources
            adjust_start_time = time.time()
            logging.debug("Adjusting resources...")
            scaling_manager.adjust_resources(containers, energy_mode)
            adjust_duration = time.time() - adjust_start_time
            logging.debug(f"Resource adjustment took {adjust_duration:.2f} seconds.")

            # Log time before scaling horizontally
            scale_start_time = time.time()
            logging.debug("Managing horizontal scaling...")
            scaling_manager.manage_horizontal_scaling(containers)
            scale_duration = time.time() - scale_start_time
            logging.debug(f"Horizontal scaling took {scale_duration:.2f} seconds.")

            loop_duration = time.time() - loop_start_time
            logging.info(f"Resource allocation process completed. Total loop duration: {loop_duration:.2f} seconds.")

            # Log next run in `poll_interval` seconds
            if loop_duration < poll_interval:
                sleep_duration = poll_interval - loop_duration
                logging.debug(f"Sleeping for {sleep_duration:.2f} seconds until the next run.")
                time.sleep(sleep_duration)
            else:
                logging.warning("The loop took longer than the poll interval! No sleep will occur.")

        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            logging.exception("Exception traceback:")
            time.sleep(poll_interval)