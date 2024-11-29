import config
import logging
from time import sleep
import lxc_utils
import scaling_manager
import notification
import paramiko
from concurrent.futures import ThreadPoolExecutor, as_completed

import paramiko

# Debug print statement to ensure paramiko is imported
# print(f"Paramiko version: {paramiko.__version__}")



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

import time

def main_loop(poll_interval: int, energy_mode: bool):
    """
    Main loop that handles the resource allocation and scaling process.

    Args:
        poll_interval (int): The interval in seconds between each resource allocation process.
        energy_mode (bool): A flag to indicate if energy efficiency mode should be enabled during off-peak hours.
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
                sleep(sleep_duration)
            else:
                logging.warning("The loop took longer than the poll interval! No sleep will occur.")

        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            logging.exception("Exception traceback:")
            # Optional: Decide if you want to continue or handle specific exceptions differently.
            sleep(poll_interval)  # Optional: Handle the error more gracefully or exit

