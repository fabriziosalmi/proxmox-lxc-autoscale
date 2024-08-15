import argparse
import fcntl
import json
import logging
import os
import signal
import subprocess
import sys
import yaml
from contextlib import contextmanager
from datetime import datetime
from socket import gethostname
from time import sleep
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Configuration file path
CONFIG_FILE = "/etc/lxc_autoscale/lxc_autoscale.yaml"

# Load configuration from YAML file
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as file:
        config = yaml.safe_load(file)
else:
    sys.exit(f"Configuration file {CONFIG_FILE} does not exist. Exiting...")

DEFAULTS = config.get('DEFAULT', {})

# Set up logging
LOG_FILE = DEFAULTS.get('log_file', '/var/log/lxc_autoscale.log')
LOCK_FILE = DEFAULTS.get('lock_file', '/var/lock/lxc_autoscale.lock')
BACKUP_DIR = DEFAULTS.get('backup_dir', '/var/lib/lxc_autoscale/backups')
RESERVE_CPU_PERCENT = DEFAULTS.get('reserve_cpu_percent', 10)
RESERVE_MEMORY_MB = DEFAULTS.get('reserve_memory_mb', 2048)
OFF_PEAK_START = DEFAULTS.get('off_peak_start', 22)
OFF_PEAK_END = DEFAULTS.get('off_peak_end', 6)
IGNORE_LXC = DEFAULTS.get('ignore_lxc', [])
BEHAVIOUR = DEFAULTS.get('behaviour', 'normal').lower()
PROXMOX_HOSTNAME = gethostname()

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# Lock for thread-safe operations
lock = Lock()

# Function for logging JSON events
def log_json_event(ctid, action, resource_change):
    log_data = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "proxmox_host": PROXMOX_HOSTNAME,
        "container_id": ctid,
        "action": action,
        "change": resource_change
    }
    with lock:
        with open(LOG_FILE.replace('.log', '.json'), 'a') as json_log_file:
            json_log_file.write(json.dumps(log_data) + '\n')

# CLI Argument Parsing
parser = argparse.ArgumentParser(description="LXC Resource Management Daemon")
parser.add_argument("--poll_interval", type=int, default=DEFAULTS.get('poll_interval', 300), help="Polling interval in seconds")
parser.add_argument("--energy_mode", action="store_true", default=DEFAULTS.get('energy_mode', False), help="Enable energy efficiency mode during off-peak hours")
parser.add_argument("--rollback", action="store_true", help="Rollback to previous container configurations")
args = parser.parse_args()

running = True

# Signal handler for graceful shutdown
def handle_signal(signum, frame):
    global running
    logging.info(f"Received signal {signum}. Shutting down gracefully...")
    running = False
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGHUP, handle_signal)

# Helper function to execute shell commands
def run_command(cmd, timeout=30):
    try:
        result = subprocess.check_output(cmd, shell=True, timeout=timeout).decode('utf-8').strip()
        logging.debug(f"Command '{cmd}' executed successfully.")
        return result
    except subprocess.TimeoutExpired:
        logging.error(f"Command '{cmd}' timed out after {timeout} seconds.")
        return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Command '{cmd}' failed with error: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during command execution '{cmd}': {e}")
        return None

# Ensure singleton script execution
@contextmanager
def acquire_lock():
    lock_file = open(LOCK_FILE, 'w')
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield lock_file
    except IOError:
        logging.error("Another instance of the script is already running. Exiting to avoid overlap.")
        sys.exit(1)
    finally:
        lock_file.close()

# Ensure LXC_TIER_ASSOCIATIONS is defined
LXC_TIER_ASSOCIATIONS = {}

# Load tier configurations and associate LXC IDs with them
for section, tier_config in config.items():
    if section.startswith('TIER_'):
        nodes = tier_config.get('lxc_containers', [])
        for ctid in nodes:
            LXC_TIER_ASSOCIATIONS[str(ctid)] = tier_config

# Check if we are in off-peak hours
def is_off_peak():
    if args.energy_mode:
        current_hour = datetime.now().hour
        return OFF_PEAK_START <= current_hour or current_hour < OFF_PEAK_END
    return False

# Send notification via Gotify
def send_gotify_notification(title, message, priority=5):
    if DEFAULTS.get('gotify_url') and DEFAULTS.get('gotify_token'):
        hostname_info = f"[Host: {PROXMOX_HOSTNAME}]"
        full_message = f"{hostname_info} {message}"
        cmd = (
            f"curl -X POST {DEFAULTS['gotify_url']}/message -F 'title={title}' "
            f"-F 'message={full_message}' -F 'priority={priority}' "
            f"-H 'X-Gotify-Key: {DEFAULTS['gotify_token']}'"
        )
        if run_command(cmd):
            logging.info(f"Notification sent: {title} - {message}")
    else:
        logging.debug("Gotify URL or Token not provided. Notification not sent.")

# Get all containers
def get_containers():
    containers = run_command("pct list | awk 'NR>1 {print $1}'")
    return containers.splitlines() if containers else []

# Check if a container is running
def is_container_running(ctid):
    status = run_command(f"pct status {ctid}")
    if status and "status: running" in status.lower():
        return True
    logging.info(f"Container {ctid} is not running. Skipping adjustments.")
    return False

# Backup container settings
def backup_container_settings(ctid, settings):
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
        with lock:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f)
        logging.debug(f"Backup saved for container {ctid}: {settings}")
    except Exception as e:
        logging.error(f"Failed to backup settings for container {ctid}: {e}")

# Load backup settings
def load_backup_settings(ctid):
    try:
        backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
        if os.path.exists(backup_file):
            with lock:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            logging.debug(f"Loaded backup for container {ctid}: {settings}")
            return settings
        logging.warning(f"No backup found for container {ctid}")
        return None
    except Exception as e:
        logging.error(f"Failed to load backup settings for container {ctid}: {e}")
        return None

# Rollback container settings
def rollback_container_settings(ctid):
    settings = load_backup_settings(ctid)
    if settings:
        logging.info(f"Rolling back container {ctid} to backup settings")
        run_command(f"pct set {ctid} -cores {settings['cores']}")
        run_command(f"pct set {ctid} -memory {settings['memory']}")
        send_gotify_notification(
            f"Rollback for Container {ctid}",
            "Container settings rolled back to previous state."
        )

# Get total available CPU cores on the host
def get_total_cores():
    total_cores = int(run_command("nproc"))
    reserved_cores = max(1, int(total_cores * RESERVE_CPU_PERCENT / 100))
    available_cores = total_cores - reserved_cores
    logging.debug(
        f"Total cores: {total_cores}, Reserved cores: {reserved_cores}, "
        f"Available cores: {available_cores}"
    )
    return available_cores

# Get total available memory on the host (in MB)
def get_total_memory():
    total_memory = int(run_command("free -m | awk '/Mem:/ {print $2}'"))
    available_memory = max(0, total_memory - RESERVE_MEMORY_MB)
    logging.debug(
        f"Total memory: {total_memory}MB, Reserved memory: {RESERVE_MEMORY_MB}MB, "
        f"Available memory: {available_memory}MB"
    )
    return available_memory

# Get CPU usage of a container
def get_cpu_usage(ctid):
    cmd = (
        f"pct exec {ctid} -- awk -v cores=$(nproc) '{{usage+=$1}} END {{print usage/cores}}' /proc/stat"
    )
    usage = run_command(cmd)
    if usage is not None:
        try:
            return float(usage)
        except ValueError:
            logging.error(f"Failed to convert CPU usage to float for container {ctid}: '{usage}'")
    logging.error(f"Failed to retrieve CPU usage for container {ctid}")
    return 0.0

# Get memory usage of a container
def get_memory_usage(ctid):
    mem_used = run_command(
        f"pct exec {ctid} -- awk '/MemTotal/ {{total=$2}} /MemAvailable/ {{free=$2}} END {{print total-free}}' /proc/meminfo"
    )
    mem_total = run_command(f"pct exec {ctid} -- awk '/MemTotal/ {{print $2}}' /proc/meminfo")
    if mem_used and mem_total:
        try:
            return (int(mem_used) * 100) / int(mem_total)
        except ValueError:
            logging.error(f"Failed to calculate memory usage for container {ctid}")
    logging.error(f"Failed to retrieve memory usage for container {ctid}")
    return 0.0

# Get container data in parallel
def get_container_data(ctid):
    if ctid in IGNORE_LXC:
        logging.info(f"Container {ctid} is in the ignore list. Skipping...")
        return None

    if not is_container_running(ctid):
        return None

    logging.debug(f"Collecting data for container {ctid}...")
    try:
        cores = int(run_command(f"pct config {ctid} | grep cores | awk '{{print $2}}'"))
        memory = int(run_command(f"pct config {ctid} | grep memory | awk '{{print $2}}'"))
        settings = {"cores": cores, "memory": memory}
        backup_container_settings(ctid, settings)
        return {
            "cpu": get_cpu_usage(ctid),
            "mem": get_memory_usage(ctid),
            "initial_cores": cores,
            "initial_memory": memory,
        }
    except Exception as e:
        logging.error(f"Error collecting data for container {ctid}: {e}")
        return None

# Collect data about all containers in parallel
def collect_container_data():
    containers = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_ctid = {executor.submit(get_container_data, ctid): ctid for ctid in get_containers()}
        for future in as_completed(future_to_ctid):
            ctid = future_to_ctid[future]
            try:
                data = future.result()
                if data:
                    containers[ctid] = data
                    logging.debug(f"Container {ctid} data: {data}")
            except Exception as e:
                logging.error(f"Error retrieving data for container {ctid}: {e}")
    return containers

# Prioritize containers based on resource needs
def prioritize_containers(containers):
    if not containers:
        logging.info("No containers to prioritize.")
        return []

    try:
        priorities = sorted(
            containers.items(),
            key=lambda item: (item[1]['cpu'], item[1]['mem']),
            reverse=True
        )
        logging.debug(f"Container priorities: {priorities}")
        return priorities
    except Exception as e:
        logging.error(f"Error prioritizing containers: {e}")
        return []

# Get the configuration for a specific container based on its assigned tier
def get_container_config(ctid):
    return LXC_TIER_ASSOCIATIONS.get(ctid, DEFAULTS)

# Adjust resources based on priority and available resources
def adjust_resources(containers):
    if not containers:
        logging.info("No containers to adjust.")
        return

    total_cores = get_total_cores()
    total_memory = get_total_memory()

    reserved_cores = max(1, int(total_cores * RESERVE_CPU_PERCENT / 100))
    reserved_memory = RESERVE_MEMORY_MB

    available_cores = total_cores - reserved_cores
    available_memory = total_memory - reserved_memory

    logging.info(f"Initial resources before adjustments: {available_cores} cores, {available_memory} MB memory")

    for ctid, usage in containers.items():
        config = get_container_config(ctid)
        cpu_upper = config['cpu_upper_threshold']
        cpu_lower = config['cpu_lower_threshold']
        mem_upper = config['memory_upper_threshold']
        mem_lower = config['memory_lower_threshold']
        min_cores = config['min_cores']
        max_cores = config['max_cores']
        min_memory = config['min_memory']

        cpu_usage = usage['cpu']
        mem_usage = usage['mem']

        current_cores = usage["initial_cores"]
        current_memory = usage["initial_memory"]

        cores_changed = False
        memory_changed = False

        behaviour_multiplier = 1.0
        if BEHAVIOUR == 'conservative':
            behaviour_multiplier = 0.5
        elif BEHAVIOUR == 'aggressive':
            behaviour_multiplier = 2.0

        # Adjust CPU cores if needed
        if cpu_usage > cpu_upper:
            increment = min(
                int(config['core_max_increment'] * behaviour_multiplier),
                max(int(config['core_min_increment'] * behaviour_multiplier), int((cpu_usage - cpu_upper) * config['core_min_increment'] / 10))
            )
            new_cores = min(max_cores, current_cores + increment)
            if available_cores >= increment and new_cores <= max_cores:
                logging.info(f"Increasing cores for container {ctid} by {increment}...")
                run_command(f"pct set {ctid} -cores {new_cores}")
                available_cores -= increment
                cores_changed = True
                log_json_event(ctid, "Increase Cores", f"{increment}")
                send_gotify_notification(
                    f"CPU Increased for Container {ctid}",
                    f"CPU cores increased to {new_cores}."
                )
            else:
                logging.warning(f"Not enough available cores to increase for container {ctid}")
        elif cpu_usage < cpu_lower and current_cores > min_cores:
            decrement = min(
                int(config['core_max_increment'] * behaviour_multiplier),
                max(int(config['core_min_increment'] * behaviour_multiplier), int((cpu_lower - cpu_usage) * config['core_min_increment'] / 10))
            )
            new_cores = max(min_cores, current_cores - decrement)
            if new_cores >= min_cores:
                logging.info(f"Decreasing cores for container {ctid} by {decrement}...")
                run_command(f"pct set {ctid} -cores {new_cores}")
                available_cores += (current_cores - new_cores)
                cores_changed = True
                log_json_event(ctid, "Decrease Cores", f"{decrement}")
                send_gotify_notification(
                    f"CPU Decreased for Container {ctid}",
                    f"CPU cores decreased to {new_cores}."
                )
            else:
                logging.warning(f"Cannot decrease cores below min_cores for container {ctid}")

        # Adjust memory if needed
        if mem_usage > mem_upper:
            increment = max(
                int(config['memory_min_increment'] * behaviour_multiplier),
                int((mem_usage - mem_upper) * config['memory_min_increment'] / 10)
            )
            if available_memory >= increment:
                logging.info(f"Increasing memory for container {ctid} by {increment}MB...")
                new_memory = current_memory + increment
                run_command(f"pct set {ctid} -memory {new_memory}")
                available_memory -= increment
                memory_changed = True
                log_json_event(ctid, "Increase Memory", f"{increment}MB")
                send_gotify_notification(
                    f"Memory Increased for Container {ctid}",
                    f"Memory increased by {increment}MB."
                )
            else:
                logging.warning(f"Not enough available memory to increase for container {ctid}")
        elif mem_usage < mem_lower and current_memory > min_memory:
            decrease_amount = min(
                int(config['min_decrease_chunk'] * behaviour_multiplier) * ((current_memory - min_memory) // int(config['min_decrease_chunk'] * behaviour_multiplier)),
                current_memory - min_memory
            )
            if decrease_amount > 0:
                logging.info(f"Decreasing memory for container {ctid} by {decrease_amount}MB...")
                new_memory = current_memory - decrease_amount
                run_command(f"pct set {ctid} -memory {new_memory}")
                available_memory += decrease_amount
                memory_changed = True
                log_json_event(ctid, "Decrease Memory", f"{decrease_amount}MB")
                send_gotify_notification(
                    f"Memory Decreased for Container {ctid}",
                    f"Memory decreased by {decrease_amount}MB."
                )

        # Apply energy efficiency mode if enabled
        if args.energy_mode and is_off_peak():
            if current_cores > min_cores:
                logging.info(f"Reducing cores for energy efficiency during off-peak hours for container {ctid}...")
                run_command(f"pct set {ctid} -cores {min_cores}")
                available_cores += (current_cores - min_cores)
                log_json_event(ctid, "Reduce Cores (Off-Peak)", f"{current_cores - min_cores}")
                send_gotify_notification(
                    f"CPU Reduced for Container {ctid}",
                    f"CPU cores reduced to {min_cores} for energy efficiency."
                )
            if current_memory > min_memory:
                logging.info(f"Reducing memory for energy efficiency during off-peak hours for container {ctid}...")
                run_command(f"pct set {ctid} -memory {min_memory}")
                available_memory += (current_memory - min_memory)
                log_json_event(ctid, "Reduce Memory (Off-Peak)", f"{current_memory - min_memory}MB")
                send_gotify_notification(
                    f"Memory Reduced for Container {ctid}",
                    f"Memory reduced to {min_memory}MB for energy efficiency."
                )

    logging.info(f"Final resources after adjustments: {available_cores} cores, {available_memory} MB memory")

def main_loop():
    while running:
        logging.info("Starting resource allocation process...")

        try:
            containers = collect_container_data()
            priorities = prioritize_containers(containers)
            if isinstance(priorities, list) and all(isinstance(i, tuple) for i in priorities):
                adjust_resources(dict(priorities))

            logging.info(f"Resource allocation process completed. Next run in {args.poll_interval} seconds.")
            sleep(args.poll_interval)
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            break

if __name__ == "__main__":
    with acquire_lock() as lock_file:
        try:
            if args.rollback:
                logging.info("Starting rollback process...")
                for ctid in get_containers():
                    rollback_container_settings(ctid)
                logging.info("Rollback process completed.")
            else:
                main_loop()
        finally:
            logging.info("Releasing lock and exiting.")
