import requests
import logging
import time
import sys
import pandas as pd

# Ensure all modules in the lxc_autoscale_ml directory are accessible
sys.path.append('/usr/local/bin/lxc_autoscale_ml')

# Import custom modules
from logger import setup_logging
from lock_manager import create_lock_file, remove_lock_file
from config_manager import load_config
from model import train_anomaly_models, predict_anomalies
from signal_handler import setup_signal_handlers

def determine_scaling_action(latest_metrics, scaling_decision, confidence, config):
    cpu_action = "No Scaling"
    ram_action = "No Scaling"
    new_cores = None
    new_ram = None
    
    cpu_usage = latest_metrics["cpu_usage_percent"]
    memory_usage = latest_metrics["memory_usage_mb"]
    cpu_memory_ratio = latest_metrics.get("cpu_memory_ratio", None)
    io_ops_per_second = latest_metrics.get("io_ops_per_second", None)

    logging.debug(f"CPU usage: {cpu_usage}% | Memory usage: {memory_usage}MB | Confidence: {confidence}%")

    cpu_thresholds = config["scaling"]
    ram_thresholds = config["scaling"]

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

    # Ensure scaling stays within limits
    if cpu_action == "Scale Up":
        new_cores = min(cpu_thresholds["total_cores"], cpu_thresholds["max_cpu_cores"])
    elif cpu_action == "Scale Down":
        new_cores = max(cpu_thresholds["min_cpu_cores"], cpu_thresholds["min_cpu_cores"])
    
    if ram_action == "Scale Up":
        new_ram = min(ram_thresholds["total_ram_mb"], ram_thresholds["max_ram_mb"])
    elif ram_action == "Scale Down":
        new_ram = max(ram_thresholds["min_ram_mb"], ram_thresholds["min_ram_mb"])

    logging.debug(f"Final scaling actions: CPU -> {cpu_action}, RAM -> {ram_action} | Confidence: {confidence}%")
    return cpu_action, ram_action, new_cores, new_ram




def apply_scaling(lxc_id, new_cores, new_ram, config):
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

    if new_cores is not None:
        cpu_data = {"vm_id": lxc_id, "cores": new_cores}
        cpu_url = f"{base_url}{cores_endpoint}"
        if not perform_request(cpu_url, cpu_data, "CPU"):
            logging.error(f"Scaling operation aborted for LXC ID {lxc_id} due to CPU scaling failure.")

    if new_ram is not None:
        ram_data = {"vm_id": lxc_id, "memory": new_ram}
        ram_url = f"{base_url}{ram_endpoint}"
        if not perform_request(ram_url, ram_data, "RAM"):
            logging.error(f"Scaling operation aborted for LXC ID {lxc_id} due to RAM scaling failure.")
