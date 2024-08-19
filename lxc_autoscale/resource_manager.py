from config import config
import logging  # For logging events and errors
from time import sleep  # To introduce delays in the main loop
from lxc_utils import (  # Import various utility functions related to LXC container management
    run_command, get_containers, is_container_running, backup_container_settings,
    load_backup_settings, rollback_container_settings, log_json_event, get_total_cores,
    get_total_memory, get_cpu_usage, get_memory_usage, is_ignored, get_container_data,
    collect_container_data, prioritize_containers, get_container_config,
    generate_unique_snapshot_name, generate_cloned_hostname
)
from scaling_manager import manage_horizontal_scaling, adjust_resources  # Import scaling management functions
from notification import send_notification  # Import notification function
from config import HORIZONTAL_SCALING_GROUPS, IGNORE_LXC, DEFAULTS  # Import configuration constants

def collect_container_data():
    """
    Collect resource usage data for all LXC containers.
    
    Returns:
        dict: A dictionary where the keys are container IDs and the values are their respective data.
    """
    containers = {}
    for ctid in get_containers():
        if not is_container_running(ctid):
            continue
        logging.debug(f"Collecting data for container {ctid}...")
        
        # Retrieve the current configuration of the container
        cores = int(run_command(f"pct config {ctid} | grep cores | awk '{{print $2}}'"))
        memory = int(run_command(f"pct config {ctid} | grep memory | awk '{{print $2}}'"))
        settings = {"cores": cores, "memory": memory}
        
        # Backup the current settings
        backup_container_settings(ctid, settings)
        
        # Collect CPU and memory usage data
        containers[ctid] = {
            "cpu": get_cpu_usage(ctid),
            "mem": get_memory_usage(ctid),
            "initial_cores": cores,
            "initial_memory": memory,
        }
    return containers

def main_loop(poll_interval, energy_mode):
    """
    Main loop that handles the resource allocation and scaling process.
    
    Args:
        poll_interval (int): The interval in seconds between each resource allocation process.
        energy_mode (bool): A flag to indicate if energy efficiency mode should be enabled during off-peak hours.
    """
    running = True
    while running:
        logging.info("Starting resource allocation process...")
        try:
            # Collect data for all containers
            containers = collect_container_data()
            
            # Adjust resources based on collected data
            adjust_resources(containers, energy_mode)
            
            # Manage horizontal scaling groups
            manage_horizontal_scaling(containers)
            
            logging.info(f"Resource allocation process completed. Next run in {poll_interval} seconds.")
            
            # Sleep until the next polling interval
            sleep(poll_interval)
        except Exception as e:
            # If an error occurs, log it and exit the loop
            logging.error(f"Error in main loop: {e}")
            running = False