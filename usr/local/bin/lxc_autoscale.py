import subprocess
import logging
import sys
import os
import fcntl
import json
import argparse
import signal
from time import sleep, time

# Default Configuration
DEFAULT_POLL_INTERVAL = 300   # Polling interval in seconds (5 minutes)
DEFAULT_CPU_UPPER_THRESHOLD = 80
DEFAULT_CPU_LOWER_THRESHOLD = 20
DEFAULT_MEMORY_UPPER_THRESHOLD = 80
DEFAULT_MEMORY_LOWER_THRESHOLD = 20
DEFAULT_STORAGE_UPPER_THRESHOLD = 80

DEFAULT_CORE_MIN_INCREMENT = 1
DEFAULT_CORE_MAX_INCREMENT = 4
DEFAULT_MEMORY_MIN_INCREMENT = 512
DEFAULT_STORAGE_INCREMENT = 10240

DEFAULT_MIN_CORES = 1
DEFAULT_MAX_CORES = 8
DEFAULT_MIN_MEMORY = 512

DEFAULT_MIN_DECREASE_CHUNK = 512

IGNORED_CONTAINERS = []

LOCK_FILE = "/var/lock/lxc_autoscale.lock"
LOG_FILE = "/var/log/lxc_autoscale.log"
BACKUP_DIR = "/var/backups"

RESERVE_CPU_PERCENT = 10
RESERVE_MEMORY_MB = 2048
RESERVE_STORAGE_MB = 10240

# Set up logging
logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# CLI Argument Parsing
parser = argparse.ArgumentParser(description="LXC Resource Management Daemon")
parser.add_argument("--poll_interval", type=int, default=DEFAULT_POLL_INTERVAL, help="Polling interval in seconds")
parser.add_argument("--cpu_upper", type=int, default=DEFAULT_CPU_UPPER_THRESHOLD, help="CPU usage upper threshold")
parser.add_argument("--cpu_lower", type=int, default=DEFAULT_CPU_LOWER_THRESHOLD, help="CPU usage lower threshold")
parser.add_argument("--mem_upper", type=int, default=DEFAULT_MEMORY_UPPER_THRESHOLD, help="Memory usage upper threshold")
parser.add_argument("--mem_lower", type=int, default=DEFAULT_MEMORY_LOWER_THRESHOLD, help="Memory usage lower threshold")
parser.add_argument("--storage_upper", type=int, default=DEFAULT_STORAGE_UPPER_THRESHOLD, help="Storage usage upper threshold")
parser.add_argument("--core_min", type=int, default=DEFAULT_CORE_MIN_INCREMENT, help="Minimum core increment")
parser.add_argument("--core_max", type=int, default=DEFAULT_CORE_MAX_INCREMENT, help="Maximum core increment")
parser.add_argument("--mem_min", type=int, default=DEFAULT_MEMORY_MIN_INCREMENT, help="Minimum memory increment")
parser.add_argument("--storage_inc", type=int, default=DEFAULT_STORAGE_INCREMENT, help="Storage increment in MB")
parser.add_argument("--min_cores", type=int, default=DEFAULT_MIN_CORES, help="Minimum number of cores per container")
parser.add_argument("--max_cores", type=int, default=DEFAULT_MAX_CORES, help="Maximum number of cores per container")
parser.add_argument("--min_mem", type=int, default=DEFAULT_MIN_MEMORY, help="Minimum memory per container in MB")
parser.add_argument("--min_decrease_chunk", type=int, default=DEFAULT_MIN_DECREASE_CHUNK, help="Minimum memory decrease chunk in MB")
parser.add_argument("--rollback", action="store_true", help="Rollback to previous container configurations")
args = parser.parse_args()

running = True

# Signal handler for graceful shutdown
def handle_signal(signum, frame):
    global running
    logging.info(f"Received signal {signum}. Shutting down gracefully...")
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

# Helper function to execute shell commands
def run_command(cmd):
    try:
        result = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
        logging.debug(f"Command '{cmd}' executed successfully.")
        return result
    except subprocess.CalledProcessError as e:
        logging.error(f"Command '{cmd}' failed with error: {e}")
        return None

# Function to ensure singleton script execution
def acquire_lock():
    lock_file = open(LOCK_FILE, 'w')
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except IOError:
        logging.error("Another instance of the script is already running. Exiting to avoid overlap.")
        sys.exit(1)

# Function to get all containers
def get_containers():
    containers = run_command("pct list | awk 'NR>1 {print $1}'")
    return containers.splitlines() if containers else []

# Function to backup container settings
def backup_container_settings(ctid, settings):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
    with open(backup_file, 'w') as f:
        json.dump(settings, f)
    logging.info(f"Backup saved for container {ctid}: {settings}")

# Function to load backup settings
def load_backup_settings(ctid):
    backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
    if os.path.exists(backup_file):
        with open(backup_file, 'r') as f:
            settings = json.load(f)
        logging.info(f"Loaded backup for container {ctid}: {settings}")
        return settings
    logging.warning(f"No backup found for container {ctid}")
    return None

# Function to rollback container settings
def rollback_container_settings(ctid):
    settings = load_backup_settings(ctid)
    if settings:
        logging.info(f"Rolling back container {ctid} to backup settings")
        run_command(f"pct set {ctid} -cores {settings['cores']}")
        run_command(f"pct set {ctid} -memory {settings['memory']}")
        run_command(f"pct resize {ctid} rootfs={settings['storage']}M")

# Function to get total available CPU cores on the host
def get_total_cores():
    total_cores = int(run_command("nproc"))
    reserved_cores = max(1, int(total_cores * RESERVE_CPU_PERCENT / 100))
    available_cores = total_cores - reserved_cores
    logging.debug(f"Total cores: {total_cores}, Reserved cores: {reserved_cores}, Available cores: {available_cores}")
    return available_cores

# Function to get total available memory on the host (in MB)
def get_total_memory():
    total_memory = int(run_command("free -m | awk '/Mem:/ {print $2}'"))
    available_memory = max(0, total_memory - RESERVE_MEMORY_MB)
    logging.debug(f"Total memory: {total_memory}MB, Reserved memory: {RESERVE_MEMORY_MB}MB, Available memory: {available_memory}MB")
    return available_memory

# Function to get total available storage on the host (in MB)
def get_total_storage():
    total_storage = int(run_command("df -m --output=avail / | tail -n 1"))
    available_storage = max(0, total_storage - RESERVE_STORAGE_MB)
    logging.debug(f"Total storage: {total_storage}MB, Reserved storage: {RESERVE_STORAGE_MB}MB, Available storage: {available_storage}MB")
    return available_storage

# Function to get CPU usage of a container
def get_cpu_usage(ctid):
    cmd = f"pct exec {ctid} -- awk -v cores=$(nproc) '{{usage+=$1}} END {{print usage/cores}}' /proc/stat"
    usage = run_command(cmd)
    logging.debug(f"Container {ctid} CPU usage: {usage}%")
    return float(usage)

# Function to get memory usage of a container
def get_memory_usage(ctid):
    mem_used = int(run_command(f"pct exec {ctid} -- awk '/MemTotal/ {{total=$2}} /MemAvailable/ {{free=$2}} END {{print total-free}}' /proc/meminfo"))
    mem_total = int(run_command(f"pct exec {ctid} -- awk '/MemTotal/ {{print $2}}' /proc/meminfo"))
    usage = (mem_used * 100) / mem_total
    logging.debug(f"Container {ctid} memory usage: {usage}%")
    return usage

# Function to get storage usage of a container
def get_storage_usage(ctid):
    storage_used = run_command(f"pct exec {ctid} -- df -h / | awk 'NR==2 {{print $4}}'")
    if 'G' in storage_used:
        storage_used = float(storage_used.replace('G', '')) * 1024  # Convert GB to MB
    elif 'M' in storage_used:
        storage_used = float(storage_used.replace('M', ''))  # Already in MB
    else:
        storage_used = float(storage_used)  # Handle edge cases
    logging.debug(f"Container {ctid} storage usage: {storage_used}MB")
    return storage_used

# Function to collect data about all containers
def collect_container_data():
    containers = {}
    for ctid in get_containers():
        if ctid in IGNORED_CONTAINERS:
            logging.info(f"Ignoring container {ctid} as per configuration.")
            continue
        logging.info(f"Collecting data for container {ctid}...")
        cores = int(run_command(f"pct config {ctid} | grep cores | awk '{{print $2}}'"))
        memory = int(run_command(f"pct config {ctid} | grep memory | awk '{{print $2}}'"))
        storage = int(get_storage_usage(ctid))
        settings = {"cores": cores, "memory": memory, "storage": storage}
        backup_container_settings(ctid, settings)
        containers[ctid] = {
            "cpu": get_cpu_usage(ctid),
            "mem": get_memory_usage(ctid),
            "storage": storage,
            "initial_cores": cores,
            "initial_memory": memory,
            "initial_storage": storage
        }
        logging.debug(f"Container {ctid} data: {containers[ctid]}")
    return containers

# Function to prioritize containers based on resource needs
def prioritize_containers(containers):
    priorities = sorted(containers.items(), key=lambda item: (item[1]['cpu'], item[1]['mem']), reverse=True)
    logging.debug(f"Container priorities: {priorities}")
    return priorities

# Function to adjust resources based on priority and available resources
def adjust_resources(containers):
    initial_cores = get_total_cores()
    initial_memory = get_total_memory()
    initial_storage = get_total_storage()

    available_cores = initial_cores
    available_memory = initial_memory
    available_storage = initial_storage

    for ctid, usage in containers:
        cpu_usage = usage['cpu']
        mem_usage = usage['mem']
        storage_usage = usage['storage']

        current_cores = usage["initial_cores"]
        current_memory = usage["initial_memory"]
        current_storage = usage["initial_storage"]

        cores_changed = False
        memory_changed = False
        storage_changed = False

        # Adjust CPU cores if needed
        if cpu_usage > args.cpu_upper:
            increment = min(args.core_max, max(args.core_min, int((cpu_usage - args.cpu_upper) * args.core_min / 10)))
            new_cores = min(args.max_cores, current_cores + increment)
            if available_cores >= increment and new_cores <= args.max_cores:
                logging.info(f"Increasing cores for container {ctid} by {increment}...")
                run_command(f"pct set {ctid} -cores {new_cores}")
                available_cores -= increment
                cores_changed = True
            else:
                logging.warning(f"Not enough available cores to increase for container {ctid}")
        elif cpu_usage < args.cpu_lower and current_cores > args.min_cores:
            decrement = min(args.core_max, max(args.core_min, int((args.cpu_lower - cpu_usage) * args.core_min / 10)))
            new_cores = max(args.min_cores, current_cores - decrement)
            if new_cores >= args.min_cores:
                logging.info(f"Decreasing cores for container {ctid} by {decrement}...")
                run_command(f"pct set {ctid} -cores {new_cores}")
                available_cores += decrement
                cores_changed = True

        # Adjust memory if needed
        if mem_usage > args.mem_upper:
            increment = max(args.mem_min, int((mem_usage - args.mem_upper) * args.mem_min / 10))
            if available_memory >= increment:
                logging.info(f"Increasing memory for container {ctid} by {increment}MB...")
                run_command(f"pct set {ctid} -memory {current_memory + increment}")
                available_memory -= increment
                memory_changed = True
        elif mem_usage < args.mem_lower and current_memory > args.min_mem:
            decrease_amount = min(args.min_decrease_chunk * ((current_memory - args.min_mem) // args.min_decrease_chunk),
                                  current_memory - args.min_mem)
            if decrease_amount > 0:
                logging.info(f"Decreasing memory for container {ctid} by {decrease_amount}MB...")
                new_memory = current_memory - decrease_amount
                run_command(f"pct set {ctid} -memory {new_memory}")
                available_memory += decrease_amount
                memory_changed = True

        # Adjust storage if needed (only increase, no decrease)
        if storage_usage > args.storage_upper:
            if available_storage >= args.storage_inc:
                logging.info(f"Increasing storage for container {ctid} by {args.storage_inc}MB...")
                run_command(f"pct resize {ctid} rootfs={args.storage_inc}M")
                available_storage -= args.storage_inc
                storage_changed = True

    logging.info(f"Initial resources: {initial_cores} cores, {initial_memory} MB memory, {initial_storage} MB storage")
    logging.info(f"Final resources: {available_cores} cores, {available_memory} MB memory, {available_storage} MB storage")

def main_loop():
    while running:
        logging.info("Starting resource allocation process...")

        # Step 1: Collect data about all containers
        containers = collect_container_data()

        # Step 2: Prioritize containers based on their resource needs
        priorities = prioritize_containers(containers)

        # Step 3: Adjust resources based on the prioritized list and available host resources
        adjust_resources(priorities)

        logging.info(f"Resource allocation process completed. Next run in {args.poll_interval} seconds.")
        sleep(args.poll_interval)

# Main execution flow
if __name__ == "__main__":
    # Acquire lock to prevent multiple instances
    lock_file = acquire_lock()

    if args.rollback:
        logging.info("Starting rollback process...")
        for ctid in get_containers():
            rollback_container_settings(ctid)
        logging.info("Rollback process completed.")
    else:
        main_loop()

    # Release lock
    lock_file.close()
