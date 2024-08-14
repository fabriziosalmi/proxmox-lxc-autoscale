"""
LXC Autoscale - A resource management daemon for LXC containers.
"""

import argparse
import configparser
import fcntl
import json
import logging
import os
import signal
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime
from socket import gethostname
from time import sleep

# Configuration file path
CONFIG_FILE = "/etc/lxc_autoscale/lxc_autoscale.conf"

# Default Configuration
DEFAULTS = {
    'poll_interval': 300,
    'cpu_upper_threshold': 80,
    'cpu_lower_threshold': 20,
    'memory_upper_threshold': 80,
    'memory_lower_threshold': 20,
    'core_min_increment': 1,
    'core_max_increment': 4,
    'memory_min_increment': 512,
    'min_cores': 1,
    'max_cores': 8,
    'min_memory': 512,
    'min_decrease_chunk': 512,
    'reserve_cpu_percent': 10,
    'reserve_memory_mb': 2048,
    'log_file': "/var/log/lxc_autoscale.log",
    'lock_file': "/var/lock/lxc_autoscale.lock",
    'backup_dir': "/var/lib/lxc_autoscale/backups",
    'off_peak_start': 22,
    'off_peak_end': 6,
    'energy_mode': False,
    'gotify_url': '',
    'gotify_token': ''
}

# Load configuration from file
config = configparser.ConfigParser(defaults=DEFAULTS)
if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE)

# Set up logging
LOG_FILE = config.get('DEFAULT', 'log_file')
LOCK_FILE = config.get('DEFAULT', 'lock_file')
BACKUP_DIR = config.get('DEFAULT', 'backup_dir')
RESERVE_CPU_PERCENT = config.getint('DEFAULT', 'reserve_cpu_percent')
RESERVE_MEMORY_MB = config.getint('DEFAULT', 'reserve_memory_mb')
OFF_PEAK_START = config.getint('DEFAULT', 'off_peak_start')
OFF_PEAK_END = config.getint('DEFAULT', 'off_peak_end')
PROXMOX_HOSTNAME = gethostname()

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# CLI Argument Parsing
parser = argparse.ArgumentParser(description="LXC Resource Management Daemon")
parser.add_argument(
    "--poll_interval",
    type=int,
    default=config.getint('DEFAULT', 'poll_interval'),
    help="Polling interval in seconds"
)
parser.add_argument(
    "--cpu_upper",
    type=int,
    default=config.getint('DEFAULT', 'cpu_upper_threshold'),
    help="CPU usage upper threshold"
)
parser.add_argument(
    "--cpu_lower",
    type=int,
    default=config.getint('DEFAULT', 'cpu_lower_threshold'),
    help="CPU usage lower threshold"
)
parser.add_argument(
    "--mem_upper",
    type=int,
    default=config.getint('DEFAULT', 'memory_upper_threshold'),
    help="Memory usage upper threshold"
)
parser.add_argument(
    "--mem_lower",
    type=int,
    default=config.getint('DEFAULT', 'memory_lower_threshold'),
    help="Memory usage lower threshold"
)
parser.add_argument(
    "--core_min",
    type=int,
    default=config.getint('DEFAULT', 'core_min_increment'),
    help="Minimum core increment"
)
parser.add_argument(
    "--core_max",
    type=int,
    default=config.getint('DEFAULT', 'core_max_increment'),
    help="Maximum core increment"
)
parser.add_argument(
    "--mem_min",
    type=int,
    default=config.getint('DEFAULT', 'memory_min_increment'),
    help="Minimum memory increment"
)
parser.add_argument(
    "--min_cores",
    type=int,
    default=config.getint('DEFAULT', 'min_cores'),
    help="Minimum number of cores per container"
)
parser.add_argument(
    "--max_cores",
    type=int,
    default=config.getint('DEFAULT', 'max_cores'),
    help="Maximum number of cores per container"
)
parser.add_argument(
    "--min_mem",
    type=int,
    default=config.getint('DEFAULT', 'min_memory'),
    help="Minimum memory per container in MB"
)
parser.add_argument(
    "--min_decrease_chunk",
    type=int,
    default=config.getint('DEFAULT', 'min_decrease_chunk'),
    help="Minimum memory decrease chunk in MB"
)
parser.add_argument(
    "--gotify_url",
    type=str,
    default=config.get('DEFAULT', 'gotify_url'),
    help="Gotify server URL for notifications"
)
parser.add_argument(
    "--gotify_token",
    type=str,
    default=config.get('DEFAULT', 'gotify_token'),
    help="Gotify server token for authentication"
)
parser.add_argument(
    "--energy_mode",
    action="store_true",
    default=config.getboolean('DEFAULT', 'energy_mode'),
    help="Enable energy efficiency mode during off-peak hours"
)
parser.add_argument(
    "--rollback",
    action="store_true",
    help="Rollback to previous container configurations"
)
args = parser.parse_args()

running = True


# Signal handler for graceful shutdown
def handle_signal(signum, frame):
    """Handle signals for graceful shutdown."""
    global running
    logging.info(f"Received signal {signum}. Shutting down gracefully...")
    running = False
    sys.exit(0)


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGHUP, handle_signal)  # Handle hangup signal


# Helper function to execute shell commands
def run_command(cmd, timeout=30):
    """Execute a shell command and return the result."""
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


# Function to ensure singleton script execution
@contextmanager
def acquire_lock():
    """Ensure only one instance of the script is running."""
    lock_file = open(LOCK_FILE, 'w')
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield lock_file
    except IOError:
        logging.error("Another instance of the script is already running. Exiting to avoid overlap.")
        sys.exit(1)
    finally:
        lock_file.close()


# Function to check if we are in off-peak hours
def is_off_peak():
    """Check if current time is within off-peak hours."""
    if args.energy_mode:
        current_hour = datetime.now().hour
        return OFF_PEAK_START <= current_hour or current_hour < OFF_PEAK_END
    return False


# Function to notify via Gotify
def send_gotify_notification(title, message, priority=5):
    """Send a notification using Gotify."""
    if args.gotify_url and args.gotify_token:
        hostname_info = f"[Host: {PROXMOX_HOSTNAME}]"
        full_message = f"{hostname_info} {message}"
        cmd = (
            f"curl -X POST {args.gotify_url}/message -F 'title={title}' "
            f"-F 'message={full_message}' -F 'priority={priority}' "
            f"-H 'X-Gotify-Key: {args.gotify_token}'"
        )
        if run_command(cmd):
            logging.info(f"Notification sent: {title} - {message}")
    else:
        logging.warning("Gotify URL or Token not provided. Notification not sent.")


# Function to get all containers
def get_containers():
    """Retrieve a list of all containers."""
    containers = run_command("pct list | awk 'NR>1 {print $1}'")
    return containers.splitlines() if containers else []


# Function to check if a container is running
def is_container_running(ctid):
    """Check if a container is currently running."""
    status = run_command(f"pct status {ctid}")
    if status and "status: running" in status.lower():
        return True
    logging.info(f"Container {ctid} is not running. Skipping adjustments.")
    return False


# Function to backup container settings
def backup_container_settings(ctid, settings):
    """Backup the current settings of a container."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f)
    logging.info(f"Backup saved for container {ctid}: {settings}")


# Function to load backup settings
def load_backup_settings(ctid):
    """Load the backup settings for a container."""
    backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
    if os.path.exists(backup_file):
        with open(backup_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        logging.info(f"Loaded backup for container {ctid}: {settings}")
        return settings
    logging.warning(f"No backup found for container {ctid}")
    return None


# Function to rollback container settings
def rollback_container_settings(ctid):
    """Rollback container settings to the backup state."""
    settings = load_backup_settings(ctid)
    if settings:
        logging.info(f"Rolling back container {ctid} to backup settings")
        run_command(f"pct set {ctid} -cores {settings['cores']}")
        run_command(f"pct set {ctid} -memory {settings['memory']}")
        send_gotify_notification(
            f"Rollback for Container {ctid}",
            "Container settings rolled back to previous state."
        )


# Function to get total available CPU cores on the host
def get_total_cores():
    """Get the total number of available CPU cores."""
    total_cores = int(run_command("nproc"))
    reserved_cores = max(1, int(total_cores * RESERVE_CPU_PERCENT / 100))
    available_cores = total_cores - reserved_cores
    logging.debug(
        f"Total cores: {total_cores}, Reserved cores: {reserved_cores}, "
        f"Available cores: {available_cores}"
    )
    return available_cores


# Function to get total available memory on the host (in MB)
def get_total_memory():
    """Get the total available memory on the host in MB."""
    total_memory = int(run_command("free -m | awk '/Mem:/ {print $2}'"))
    available_memory = max(0, total_memory - RESERVE_MEMORY_MB)
    logging.debug(
        f"Total memory: {total_memory}MB, Reserved memory: {RESERVE_MEMORY_MB}MB, "
        f"Available memory: {available_memory}MB"
    )
    return available_memory


# Function to get CPU usage of a container
def get_cpu_usage(ctid):
    """Retrieve the CPU usage of a specific container."""
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


# Function to get memory usage of a container
def get_memory_usage(ctid):
    """Retrieve the memory usage of a specific container."""
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


# Function to collect data about all containers
def collect_container_data():
    """Collect CPU and memory usage data for all running containers."""
    containers = {}
    for ctid in get_containers():
        if not is_container_running(ctid):
            continue
        logging.info(f"Collecting data for container {ctid}...")
        cores = int(run_command(f"pct config {ctid} | grep cores | awk '{{print $2}}'"))
        memory = int(run_command(f"pct config {ctid} | grep memory | awk '{{print $2}}'"))
        settings = {"cores": cores, "memory": memory}
        backup_container_settings(ctid, settings)
        containers[ctid] = {
            "cpu": get_cpu_usage(ctid),
            "mem": get_memory_usage(ctid),
            "initial_cores": cores,
            "initial_memory": memory,
        }
        logging.debug(f"Container {ctid} data: {containers[ctid]}")
    return containers


# Function to prioritize containers based on resource needs
def prioritize_containers(containers):
    """Prioritize containers based on their CPU and memory usage."""
    if not containers:
        logging.info("No containers to prioritize.")
        return []

    priorities = sorted(containers.items(), key=lambda item: (item[1]['cpu'], item[1]['mem']), reverse=True)
    logging.debug(f"Container priorities: {priorities}")
    return priorities


# Function to adjust resources based on priority and available resources
def adjust_resources(containers):
    """Adjust container resources based on their priority and available host resources."""
    if not containers:
        logging.info("No containers to adjust.")
        return

    total_cores = int(run_command("nproc"))
    total_memory = int(run_command("free -m | awk '/Mem:/ {print $2}'"))
    
    reserved_cores = max(1, int(total_cores * RESERVE_CPU_PERCENT / 100))
    reserved_memory = RESERVE_MEMORY_MB

    available_cores = total_cores - reserved_cores
    available_memory = total_memory - reserved_memory

    logging.info(f"Initial resources before adjustments: {available_cores} cores, {available_memory} MB memory")

    for ctid, usage in containers:
        cpu_usage = usage['cpu']
        mem_usage = usage['mem']

        current_cores = usage["initial_cores"]
        current_memory = usage["initial_memory"]

        cores_changed = False
        memory_changed = False

        # Adjust CPU cores if needed
        if cpu_usage > args.cpu_upper:
            increment = min(
                args.core_max,
                max(args.core_min, int((cpu_usage - args.cpu_upper) * args.core_min / 10))
            )
            new_cores = min(args.max_cores, current_cores + increment)
            if available_cores >= increment and new_cores <= args.max_cores:
                logging.info(f"Increasing cores for container {ctid} by {increment}...")
                run_command(f"pct set {ctid} -cores {new_cores}")
                available_cores -= increment
                cores_changed = True
                send_gotify_notification(
                    f"CPU Increased for Container {ctid}",
                    f"CPU cores increased to {new_cores}."
                )
            else:
                logging.warning(f"Not enough available cores to increase for container {ctid}")
        elif cpu_usage < args.cpu_lower and current_cores > args.min_cores:
            decrement = min(
                args.core_max,
                max(args.core_min, int((args.cpu_lower - cpu_usage) * args.core_min / 10))
            )
            new_cores = max(args.min_cores, current_cores - decrement)
            if new_cores >= args.min_cores:
                logging.info(f"Decreasing cores for container {ctid} by {decrement}...")
                run_command(f"pct set {ctid} -cores {new_cores}")
                available_cores += decrement
                cores_changed = True
                send_gotify_notification(
                    f"CPU Decreased for Container {ctid}",
                    f"CPU cores decreased to {new_cores}."
                )

        # Adjust memory if needed
        if mem_usage > args.mem_upper:
            increment = max(
                args.mem_min,
                int((mem_usage - args.mem_upper) * args.mem_min / 10)
            )
            if available_memory >= increment:
                logging.info(f"Increasing memory for container {ctid} by {increment}MB...")
                new_memory = current_memory + increment
                run_command(f"pct set {ctid} -memory {new_memory}")
                available_memory -= increment
                memory_changed = True
                send_gotify_notification(
                    f"Memory Increased for Container {ctid}",
                    f"Memory increased by {increment}MB."
                )
            else:
                logging.warning(f"Not enough available memory to increase for container {ctid}")
        elif mem_usage < args.mem_lower and current_memory > args.min_mem:
            decrease_amount = min(
                args.min_decrease_chunk * ((current_memory - args.min_mem) // args.min_decrease_chunk),
                current_memory - args.min_mem
            )
            if decrease_amount > 0:
                logging.info(f"Decreasing memory for container {ctid} by {decrease_amount}MB...")
                new_memory = current_memory - decrease_amount
                run_command(f"pct set {ctid} -memory {new_memory}")
                available_memory += decrease_amount
                memory_changed = True
                send_gotify_notification(
                    f"Memory Decreased for Container {ctid}",
                    f"Memory decreased by {decrease_amount}MB."
                )

        # Apply energy efficiency mode if enabled
        if args.energy_mode and is_off_peak():
            if current_cores > args.min_cores:
                logging.info(f"Reducing cores for energy efficiency during off-peak hours for container {ctid}...")
                run_command(f"pct set {ctid} -cores {args.min_cores}")
                available_cores += (current_cores - args.min_cores)
                send_gotify_notification(
                    f"CPU Reduced for Container {ctid}",
                    f"CPU cores reduced to {args.min_cores} for energy efficiency."
                )
            if current_memory > args.min_mem:
                logging.info(f"Reducing memory for energy efficiency during off-peak hours for container {ctid}...")
                run_command(f"pct set {ctid} -memory {args.min_mem}")
                available_memory += (current_memory - args.min_mem)
                send_gotify_notification(
                    f"Memory Reduced for Container {ctid}",
                    f"Memory reduced to {args.min_mem}MB for energy efficiency."
                )

    # Log final available resources once, after all adjustments are made
    logging.info(f"Final resources after adjustments: {available_cores} cores, {available_memory} MB memory")


def main_loop():
    """Main loop for resource allocation process."""
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
