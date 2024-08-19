import argparse
import fcntl
import json
import logging
import os
import signal
import subprocess
import sys
import requests
import yaml
import paramiko
from contextlib import contextmanager
from datetime import datetime, timedelta
from socket import gethostname
from time import sleep
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from abc import ABC, abstractmethod
import smtplib
from email.mime.text import MIMEText

# Configuration file path
CONFIG_FILE = "/etc/lxc_autoscale/lxc_autoscale.yaml"

# Load configuration from YAML file
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as file:
        config = yaml.safe_load(file)
else:
    sys.exit(f"Configuration file {CONFIG_FILE} does not exist. Exiting...")

DEFAULTS = config.get('DEFAULT', {})

# Constants
LOG_FILE = DEFAULTS.get('log_file', '/var/log/lxc_autoscale.log')
LOCK_FILE = DEFAULTS.get('lock_file', '/var/lock/lxc_autoscale.lock')
BACKUP_DIR = DEFAULTS.get('backup_dir', '/var/lib/lxc_autoscale/backups')
RESERVE_CPU_PERCENT = DEFAULTS.get('reserve_cpu_percent', 10)
RESERVE_MEMORY_MB = DEFAULTS.get('reserve_memory_mb', 2048)
OFF_PEAK_START = DEFAULTS.get('off_peak_start', 22)
OFF_PEAK_END = DEFAULTS.get('off_peak_end', 6)
IGNORE_LXC = set(map(str, DEFAULTS.get('ignore_lxc', [])))  # Ensuring all ignore IDs are strings
BEHAVIOUR = DEFAULTS.get('behaviour', 'normal').lower()
PROXMOX_HOSTNAME = gethostname()

# Set up logging
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

# Ensure use_remote_proxmox is being loaded correctly
use_remote_proxmox = config.get('DEFAULT', {}).get('use_remote_proxmox', False)
logging.debug(f"use_remote_proxmox is set to: {use_remote_proxmox}")


# Lock for thread-safe operations
lock = Lock()

# Track last scale out operations for horizontal scaling groups
scale_last_action = {}

# Abstract Notification Proxy
class NotificationProxy(ABC):
    @abstractmethod
    def send_notification(self, title: str, message: str, priority: int = 5):
        pass

# Gotify Notification
class GotifyNotification(NotificationProxy):
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token

    def send_notification(self, title: str, message: str, priority: int = 5):
        payload = {
            'title': title,
            'message': message,
            'priority': priority
        }
        headers = {
            'X-Gotify-Key': self.token
        }

        try:
            response = requests.post(f"{self.url}/message", data=payload, headers=headers)
            response.raise_for_status()  # Raises an exception for HTTP errors
            logging.info(f"Gotify notification sent: {title} - {message}")
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"Gotify notification failed: HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Gotify notification failed: Request exception: {req_err}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")


# Email Notification
class EmailNotification(NotificationProxy):
    def __init__(self, smtp_server: str, port: int, username: str, password: str, from_addr: str, to_addrs: list):
        self.smtp_server = smtp_server
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    def send_notification(self, title: str, message: str, priority: int = 5):
        msg = MIMEText(message)
        msg['Subject'] = title
        msg['From'] = self.from_addr
        msg['To'] = ', '.join(self.to_addrs)

        try:
            with smtplib.SMTP(self.smtp_server, self.port) as server:
                server.starttls()  # Upgrades the connection to TLS
                server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            logging.info(f"Email sent: {title} - {message}")
        except Exception as e:
            logging.error(f"Failed to send email: {e}")


# Uptime Kuma Notification
class UptimeKumaNotification(NotificationProxy):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_notification(self, priority: int = 5):
        try:
            response = requests.get(self.webhook_url)
            if response.status_code == 200:
                logging.info("Uptime Kuma notification sent successfully")
            else:
                logging.error(f"Failed to send Uptime Kuma notification: {response.status_code}")
        except Exception as e:
            logging.error(f"Error sending Uptime Kuma notification: {e}")

# Initialize Notifiers
notifiers = []
email_notifier = None
gotify_notifier = None
uptime_kuma_notifier = None

# Email Notifier
if DEFAULTS.get('smtp_server') and DEFAULTS.get('smtp_username') and DEFAULTS.get('smtp_password'):
    try:
        email_notifier = EmailNotification(
            smtp_server=DEFAULTS['smtp_server'],
            port=DEFAULTS.get('smtp_port', 587),
            username=DEFAULTS['smtp_username'],
            password=DEFAULTS['smtp_password'],
            from_addr=DEFAULTS['smtp_from'],
            to_addrs=DEFAULTS['smtp_to']
        )
        notifiers.append(email_notifier)
        logging.debug("Email notifier initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Email notifier: {e}")

# Gotify Notifier
if DEFAULTS.get('gotify_url') and DEFAULTS.get('gotify_token'):
    try:
        gotify_notifier = GotifyNotification(DEFAULTS['gotify_url'], DEFAULTS['gotify_token'])
        notifiers.append(gotify_notifier)
        logging.debug("Gotify notifier initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Gotify notifier: {e}")

# Uptime Kuma Notifier (if used)
if DEFAULTS.get('uptime_kuma_webhook_url'):
    try:
        uptime_kuma_notifier = UptimeKumaNotification(DEFAULTS['uptime_kuma_webhook_url'])
        notifiers.append(uptime_kuma_notifier)
        logging.debug("Uptime Kuma notifier initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Uptime Kuma notifier: {e}")

# Debugging output
logging.debug(f"Initialized notifiers: {notifiers}")

# Add Email Notifier first if you want it prioritized
if email_notifier:
    notification_proxy = email_notifier
elif gotify_notifier:
    notification_proxy = gotify_notifier
elif uptime_kuma_notifier:
    notification_proxy = uptime_kuma_notifier
else:
    notification_proxy = None


# Singleton enforcement
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

# Signal handler for graceful shutdown
def handle_signal(signum, frame):
    global running
    logging.info(f"Received signal {signum}. Shutting down gracefully...")
    running = False
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGHUP, handle_signal)

def run_command(cmd, timeout=30):
    use_remote_proxmox = config.get('DEFAULT', {}).get('use_remote_proxmox', False)
    logging.debug(f"Inside run_command: use_remote_proxmox = {use_remote_proxmox}")
    
    if use_remote_proxmox:
        logging.debug("Executing command remotely.")
        return run_remote_command(cmd, timeout)
    else:
        logging.debug("Executing command locally.")
        return run_local_command(cmd, timeout)


def run_local_command(cmd, timeout=30):
    try:
        result = subprocess.check_output(cmd, shell=True, timeout=timeout, stderr=subprocess.STDOUT).decode('utf-8').strip()
        logging.debug(f"Command '{cmd}' executed successfully. Output: {result}")
        return result
    except subprocess.TimeoutExpired:
        logging.error(f"Command '{cmd}' timed out after {timeout} seconds.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Command '{cmd}' failed with error: {e.output.decode('utf-8')}")
    except Exception as e:
        logging.error(f"Unexpected error during command execution '{cmd}': {e}")
    return None


def run_remote_command(cmd, timeout=30):
    logging.debug(f"Running remote command: {cmd}")
    ssh = None
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        logging.debug("Attempting to connect to Proxmox host via SSH...")
        ssh.connect(
            hostname=config.get('DEFAULT', {}).get('proxmox_host'),
            port=config.get('DEFAULT', {}).get('ssh_port', 22),
            username=config.get('DEFAULT', {}).get('ssh_user'),
            password=config.get('DEFAULT', {}).get('ssh_password'),
            key_filename=config.get('DEFAULT', {}).get('ssh_key_path')
        )
        logging.debug("SSH connection established successfully.")

        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        output = stdout.read().decode('utf-8').strip()
        logging.debug(f"Remote command '{cmd}' executed successfully. Output: {output}")
        return output

    except paramiko.SSHException as e:
        logging.error(f"SSH command execution failed: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during SSH command execution '{cmd}': {e}")
    finally:
        if ssh:
            ssh.close()
    return None





# Helper function to execute shell commands
#def run_command(cmd, timeout=30):
#    try:
#        result = subprocess.check_output(cmd, shell=True, timeout=timeout, stderr=subprocess.STDOUT).decode('utf-8').strip()
#        logging.debug(f"Command '{cmd}' executed successfully. Output: {result}")
#        return result
#    except subprocess.TimeoutExpired:
#        logging.error(f"Command '{cmd}' timed out after {timeout} seconds.")
#    except subprocess.CalledProcessError as e:
#        logging.error(f"Command '{cmd}' failed with error: {e.output.decode('utf-8')}")
#    except Exception as e:
#        logging.error(f"Unexpected error during command execution '{cmd}': {e}")
#    return None

# Load tier configurations and associate LXC IDs with them
LXC_TIER_ASSOCIATIONS = {}
for section, tier_config in config.items():
    if section.startswith('TIER_'):
        nodes = tier_config.get('lxc_containers', [])
        for ctid in nodes:
            LXC_TIER_ASSOCIATIONS[str(ctid)] = tier_config

# Load horizontal scaling groups
HORIZONTAL_SCALING_GROUPS = {}
for section, group_config in config.items():
    if section.startswith('HORIZONTAL_SCALING_GROUP_'):
        if group_config.get('lxc_containers'):
            group_config['lxc_containers'] = set(map(str, group_config.get('lxc_containers', [])))
            HORIZONTAL_SCALING_GROUPS[section] = group_config

# CLI Argument Parsing
parser = argparse.ArgumentParser(description="LXC Resource Management Daemon")
parser.add_argument("--poll_interval", type=int, default=DEFAULTS.get('poll_interval', 300), help="Polling interval in seconds")
parser.add_argument("--energy_mode", action="store_true", default=DEFAULTS.get('energy_mode', False), help="Enable energy efficiency mode during off-peak hours")
parser.add_argument("--rollback", action="store_true", help="Rollback to previous container configurations")
args = parser.parse_args()

running = True

# Get all containers
def get_containers():
    containers = run_command("pct list | awk 'NR>1 {print $1}'")
    return [ctid for ctid in containers.splitlines() if ctid not in IGNORE_LXC]

# Check if a container is running
def is_container_running(ctid):
    if str(ctid) in IGNORE_LXC:  # Convert ctid to string to ensure comparison is correct
        logging.info(f"Container {ctid} is in the ignore list. Skipping...")
        return False
    
    status = run_command(f"pct status {ctid}")
    if status and "status: running" in status.lower():
        return True
    logging.info(f"Container {ctid} is not running. Skipping adjustments.")
    return False

# Backup container settings
def backup_container_settings(ctid, settings):
    if str(ctid) in IGNORE_LXC:
        return
    
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
    if str(ctid) in IGNORE_LXC:
        return None
    
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
    if str(ctid) in IGNORE_LXC:
        return
    
    settings = load_backup_settings(ctid)
    if settings:
        logging.info(f"Rolling back container {ctid} to backup settings")
        run_command(f"pct set {ctid} -cores {settings['cores']}")
        run_command(f"pct set {ctid} -memory {settings['memory']}")
        send_notification(
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

# Helper function to check if container is in the ignore list
def is_ignored(ctid):
    return str(ctid) in IGNORE_LXC

# Function to get container data
def get_container_data(ctid):
    if is_ignored(ctid):  # Ensure ignored containers are skipped
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
    with ThreadPoolExecutor(max_workers=2) as executor:
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

def generate_unique_snapshot_name(base_name):
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{base_name}-{timestamp}"

def generate_cloned_hostname(base_name, clone_number):
    return f"{base_name}-cloned-{clone_number}"

def scale_out(group_name, group_config):
    current_instances = sorted(map(int, group_config['lxc_containers']))
    starting_clone_id = group_config['starting_clone_id']
    max_instances = group_config['max_instances']

    if len(current_instances) >= max_instances:
        logging.info(f"Max instances reached for {group_name}. No scale out performed.")
        return

    # Determine the next available clone ID
    new_ctid = starting_clone_id + len([ctid for ctid in current_instances if int(ctid) >= starting_clone_id])
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
        if run_command(clone_cmd, timeout=300):  # Extended timeout to 300 seconds
            # Network setup
            if group_config['clone_network_type'] == "dhcp":
                run_command(f"pct set {new_ctid} -net0 name=eth0,bridge=vmbr0,ip=dhcp")
            elif group_config['clone_network_type'] == "static":
                static_ip_range = group_config.get('static_ip_range', [])
                if static_ip_range:
                    available_ips = [ip for ip in static_ip_range if ip not in current_instances]
                    if available_ips:
                        ip_address = available_ips[0]
                        run_command(f"pct set {new_ctid} -net0 name=eth0,bridge=vmbr0,ip={ip_address}/24")
                    else:
                        logging.warning("No available IPs in the specified range for static IP assignment.")

            # Start the new container
            run_command(f"pct start {new_ctid}")
            current_instances.append(new_ctid)

            # Update the configuration
            group_config['lxc_containers'] = set(map(str, current_instances))
            scale_last_action[group_name] = datetime.now()

            logging.info(f"Container {new_ctid} started successfully as part of {group_name}.")
            send_notification(f"Scale Out: {group_name}", f"New container {new_ctid} with hostname {clone_hostname} started.")

            # Log the scale-out event to JSON
            log_json_event(new_ctid, "Scale Out", f"Container {base_snapshot} cloned to {new_ctid}. {new_ctid} started.")

        else:
            logging.error(f"Failed to clone container {base_snapshot} using snapshot {unique_snapshot_name}.")
    else:
        logging.error(f"Failed to create snapshot {unique_snapshot_name} of container {base_snapshot}.")

# Adjust resources based on priority and available resources
def adjust_resources(containers):
    if not containers:
        logging.info("No containers to adjust.")
        return

    # Open the TCP port 54547 before starting the adjustment process
    # global open_port
    # open_port = True
    # sock, connection_thread = open_tcp_port(54547)

    total_cores = get_total_cores()
    total_memory = get_total_memory()

    reserved_cores = max(1, int(total_cores * RESERVE_CPU_PERCENT / 100))
    reserved_memory = RESERVE_MEMORY_MB

    available_cores = total_cores - reserved_cores
    available_memory = total_memory - reserved_memory

    logging.info(f"Initial resources before adjustments: {available_cores} cores, {available_memory} MB memory")


    for ctid, usage in containers.items():
        if is_ignored(ctid):
            logging.info(f"Container {ctid} is ignored. Skipping resource adjustment.")
            continue

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
                send_notification(
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
                send_notification(
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
                send_notification(
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
                send_notification(
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
                send_notification(
                    f"CPU Reduced for Container {ctid}",
                    f"CPU cores reduced to {min_cores} for energy efficiency."
                )
            if current_memory > min_memory:
                logging.info(f"Reducing memory for energy efficiency during off-peak hours for container {ctid}...")
                run_command(f"pct set {ctid} -memory {min_memory}")
                available_memory += (current_memory - min_memory)
                log_json_event(ctid, "Reduce Memory (Off-Peak)", f"{current_memory - min_memory}MB")
                send_notification(
                    f"Memory Reduced for Container {ctid}",
                    f"Memory reduced to {min_memory}MB for energy efficiency."
                )

    logging.info(f"Final resources after adjustments: {available_cores} cores, {available_memory} MB memory")




def manage_horizontal_scaling(containers):
    for group_name, group_config in HORIZONTAL_SCALING_GROUPS.items():
        current_time = datetime.now()
        last_action_time = scale_last_action.get(group_name, current_time - timedelta(hours=1))

        # Calculate average CPU and memory usage for the group
        total_cpu_usage = sum(containers[ctid]['cpu'] for ctid in group_config['lxc_containers'] if ctid in containers)
        total_mem_usage = sum(containers[ctid]['mem'] for ctid in group_config['lxc_containers'] if ctid in containers)
        num_containers = len(group_config['lxc_containers'])
        
        if num_containers > 0:
            avg_cpu_usage = total_cpu_usage / num_containers
            avg_mem_usage = total_mem_usage / num_containers
        else:
            avg_cpu_usage = 0
            avg_mem_usage = 0

        logging.debug(f"Group: {group_name} | Average CPU Usage: {avg_cpu_usage}% | Average Memory Usage: {avg_mem_usage}%")

        # Check if scaling out is needed based on thresholds
        if (avg_cpu_usage > group_config['horiz_cpu_upper_threshold'] or 
            avg_mem_usage > group_config['horiz_memory_upper_threshold']):
            logging.debug(f"Thresholds exceeded for {group_name}. Evaluating scale-out conditions.")
            
            # Ensure enough time has passed since the last scaling action
            if current_time - last_action_time >= timedelta(seconds=group_config.get('scale_out_grace_period', 300)):
                scale_out(group_name, group_config)
        else:
            logging.debug(f"No scaling needed for {group_name}. Average usage below thresholds.")

def is_off_peak():
    if args.energy_mode:
        current_hour = datetime.now().hour
        return OFF_PEAK_START <= current_hour or current_hour < OFF_PEAK_END
    return False

# Define the send_notification function
def send_notification(title, message, priority=5):
    if notifiers:
        for notifier in notifiers:
            try:
                notifier.send_notification(title, message, priority)
            except Exception as e:
                logging.error(f"Failed to send notification using {notifier.__class__.__name__}: {e}")
    else:
        logging.warning("No notification system configured.")


def main_loop():
    while running:
        logging.info("Starting resource allocation process...")

        try:
            containers = collect_container_data()
            priorities = prioritize_containers(containers)
            if isinstance(priorities, list) and all(isinstance(i, tuple) for i in priorities):
                adjust_resources(dict(priorities))
                manage_horizontal_scaling(containers)

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
