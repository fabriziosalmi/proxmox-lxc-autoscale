import config
import logging
from time import sleep
import lxc_utils
import scaling_manager
import notification
from concurrent.futures import ThreadPoolExecutor, as_completed

def collect_data_for_container(ctid: str) -> dict:
    """
    Collect resource usage data for a single LXC container.
    
    Args:
        ctid (str): The container ID.
    
    Returns:
        dict: The data collected for the container, or None if the container is not running.
    """
    if not lxc_utils.is_container_running(ctid):
        return None
    
    logging.debug(f"Collecting data for container {ctid}...")
    
    try:
        # Retrieve the current configuration of the container using Python string operations
        config_output = lxc_utils.run_command(f"pct config {ctid}")
        cores = int([line.split()[1] for line in config_output.splitlines() if 'cores' in line][0])
        memory = int([line.split()[1] for line in config_output.splitlines() if 'memory' in line][0])
        settings = {"cores": cores, "memory": memory}
        
        # Backup the current settings
        lxc_utils.backup_container_settings(ctid, settings)
        
        # Collect CPU and memory usage data
        return {
            ctid: {
                "cpu": lxc_utils.get_cpu_usage(ctid),
                "mem": lxc_utils.get_memory_usage(ctid),
                "initial_cores": cores,
                "initial_memory": memory,
            }
        }
    except (ValueError, IndexError) as ve:
        logging.error(f"Error parsing core or memory values for container {ctid}: {ve}")
        return None
    except Exception as e:
        logging.error(f"Error retrieving or parsing configuration for container {ctid}: {e}")
        return None

def collect_container_data() -> dict:
    """
    Collect resource usage data for all LXC containers.
    
    Returns:
        dict: A dictionary where the keys are container IDs and the values are their respective data.
    """
    containers = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(collect_data_for_container, ctid): ctid for ctid in lxc_utils.get_containers()}
        for future in as_completed(futures):
            try:
                container_data = future.result()
                if container_data:
                    containers.update(container_data)
            except Exception as e:
                logging.error(f"Error collecting data for a container: {e}")
    return containers

def main_loop(poll_interval: int, energy_mode: bool):
    """
    Main loop that handles the resource allocation and scaling process.
    
    Args:
        poll_interval (int): The interval in seconds between each resource allocation process.
        energy_mode (bool): A flag to indicate if energy efficiency mode should be enabled during off-peak hours.
    """
    while True:
        logging.info("Starting resource allocation process...")
        try:
            containers = collect_container_data()
            scaling_manager.adjust_resources(containers, energy_mode)
            scaling_manager.manage_horizontal_scaling(containers)
            logging.info(f"Resource allocation process completed. Next run in {poll_interval} seconds.")
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            # Optional: consider if you want the loop to continue or handle certain errors more gracefully.
        sleep(poll_interval)
