import requests
import logging
import time
import numpy as np

def determine_scaling_action(latest_metrics, scaling_decision, config):
    cpu_action = "No Scaling"
    ram_action = "No Scaling"
    
    cpu_usage = latest_metrics["cpu_usage_percent"]
    memory_usage = latest_metrics["memory_usage_mb"]

    # Log detailed metrics
    logging.debug(f"CPU usage: {cpu_usage}% | Memory usage: {memory_usage}MB")

    cpu_thresholds = config["scaling"]
    ram_thresholds = config["scaling"]

    # Decision logic based on thresholds
    if scaling_decision:
        logging.debug("Anomaly detected. Scaling up CPU and RAM.")
        cpu_action = "Scale Up"
        ram_action = "Scale Up"
    else:
        if cpu_usage > cpu_thresholds["cpu_scale_up_threshold"]:
            cpu_action = "Scale Up"
            logging.debug(f"CPU usage {cpu_usage}% exceeds the scale-up threshold.")
        elif cpu_usage < cpu_thresholds["cpu_scale_down_threshold"]:
            cpu_action = "Scale Down"
            logging.debug(f"CPU usage {cpu_usage}% is below the scale-down threshold.")
        
        if memory_usage > ram_thresholds["ram_scale_up_threshold"]:
            ram_action = "Scale Up"
            logging.debug(f"Memory usage {memory_usage}MB exceeds the scale-up threshold.")
        elif memory_usage < ram_thresholds["ram_scale_down_threshold"]:
            ram_action = "Scale Down"
            logging.debug(f"Memory usage {memory_usage}MB is below the scale-down threshold.")

    logging.debug(f"Final scaling actions: CPU -> {cpu_action}, RAM -> {ram_action}")
    return cpu_action, ram_action

def apply_scaling(lxc_id, cpu_action, ram_action, config):
    max_retries = config.get("retry_logic", {}).get("max_retries", 3)
    retry_delay = config.get("retry_logic", {}).get("retry_delay", 2)
    base_url = config["api"]["api_url"]
    cores_endpoint = config["api"].get("cores_endpoint", "/scale/cores")
    ram_endpoint = config["api"].get("ram_endpoint", "/scale/ram")

    def perform_request(url, data, resource_type):
        resource_key = "cores" if resource_type == "CPU" else "memory"
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=data)
                response.raise_for_status()
                logging.info(f"Successfully scaled {resource_type} for LXC ID {lxc_id} to {data[resource_key]} {resource_type} units.")
                return True
            except requests.RequestException as e:
                if response.status_code == 500:
                    logging.error(f"Server error (500) encountered on attempt {attempt + 1} to scale {resource_type} for LXC ID {lxc_id}. Aborting further attempts.")
                    break  # Skip further retries for 500 errors
                logging.error(f"Attempt {attempt + 1} failed to scale {resource_type} for LXC ID {lxc_id}: {e}")
                if attempt < max_retries - 1:
                    logging.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Scaling {resource_type} for LXC ID {lxc_id} failed after {max_retries} attempts.")
                    return False
        return False

    if cpu_action in ["Scale Up", "Scale Down"]:
        cpu_data = {"vm_id": lxc_id, "cores": config["scaling"]["min_cpu_cores"] if cpu_action == "Scale Down" else config["scaling"]["total_cores"]}
        cpu_url = f"{base_url}{cores_endpoint}"
        if not perform_request(cpu_url, cpu_data, "CPU"):
            logging.error(f"Scaling operation aborted for LXC ID {lxc_id} due to CPU scaling failure.")

    if ram_action in ["Scale Up", "Scale Down"]:
        ram_data = {"vm_id": lxc_id, "memory": config["scaling"]["min_ram_mb"] if ram_action == "Scale Down" else config["scaling"]["total_ram_mb"]}
        ram_url = f"{base_url}{ram_endpoint}"
        if not perform_request(ram_url, ram_data, "RAM"):
            logging.error(f"Scaling operation aborted for LXC ID {lxc_id} due to RAM scaling failure.")
