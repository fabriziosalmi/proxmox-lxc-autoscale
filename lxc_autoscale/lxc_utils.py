from config import config
import subprocess  # For executing shell commands
import logging  # For logging events and errors
import json  # For handling JSON data
import os  # For interacting with the operating system (e.g., file paths)
from datetime import datetime  # For working with dates and times
from config import get_config_value, LOG_FILE, DEFAULTS, BACKUP_DIR, PROXMOX_HOSTNAME, IGNORE_LXC  # Configuration imports
from threading import Lock  # For thread-safe operations
import paramiko
import time 

# Initialize a thread lock for safe concurrent access
lock = Lock()

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


def get_containers():
    """
    Retrieve a list of all LXC container IDs, excluding those in the ignore list.

    Returns:
        list: A list of container IDs as strings.
    """
    containers = run_command("pct list | awk 'NR>1 {print $1}'")
    return [ctid for ctid in containers.splitlines() if ctid not in IGNORE_LXC]

def is_container_running(ctid):
    """
    Check if a specific container is running.

    Args:
        ctid (str): The container ID.

    Returns:
        bool: True if the container is running, otherwise False.
    """
    status = run_command(f"pct status {ctid}")
    return status and "status: running" in status.lower()

def backup_container_settings(ctid, settings):
    """
    Backup the configuration settings of a container to a JSON file.

    Args:
        ctid (str): The container ID.
        settings (dict): The container settings to be backed up.
    """
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
        with lock:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f)
        logging.debug(f"Backup saved for container {ctid}: {settings}")
    except Exception as e:
        logging.error(f"Failed to backup settings for container {ctid}: {e}")

def load_backup_settings(ctid):
    """
    Load the backup configuration settings for a container from a JSON file.

    Args:
        ctid (str): The container ID.

    Returns:
        dict or None: The backup settings if they exist, otherwise None.
    """
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

def rollback_container_settings(ctid):
    """
    Rollback the container settings to the previously backed up configuration.

    Args:
        ctid (str): The container ID.
    """
    settings = load_backup_settings(ctid)
    if settings:
        logging.info(f"Rolling back container {ctid} to backup settings")
        run_command(f"pct set {ctid} -cores {settings['cores']}")
        run_command(f"pct set {ctid} -memory {settings['memory']}")
        send_notification(f"Rollback for Container {ctid}", "Container settings rolled back to previous state.")

def log_json_event(ctid, action, resource_change):
    """
    Log a JSON event for tracking container changes.

    Args:
        ctid (str): The container ID.
        action (str): The action performed (e.g., 'Scale Out').
        resource_change (str): Description of the resource change.
    """
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

def get_total_cores():
    """
    Calculate the total available CPU cores on the host after reserving a percentage.

    Returns:
        int: The number of available CPU cores.
    """
    total_cores = int(run_command("nproc"))
    reserved_cores = max(1, int(total_cores * DEFAULTS['reserve_cpu_percent'] / 100))
    available_cores = total_cores - reserved_cores
    logging.debug(
        f"Total cores: {total_cores}, Reserved cores: {reserved_cores}, "
        f"Available cores: {available_cores}"
    )
    return available_cores

def get_total_memory():
    """
    Calculate the total available memory on the host after reserving a fixed amount.

    Returns:
        int: The amount of available memory in MB.
    """
    total_memory = int(run_command("free -m | awk '/Mem:/ {print $2}'"))
    available_memory = max(0, total_memory - DEFAULTS['reserve_memory_mb'])
    logging.debug(
        f"Total memory: {total_memory}MB, Reserved memory: {DEFAULTS['reserve_memory_mb']}MB, "
        f"Available memory: {available_memory}MB"
    )
    return available_memory


import time
import logging

def get_cpu_usage(ctid):
    """
    Retrieve the CPU usage of a container using multiple methods with fallbacks.
    
    Args:
        ctid (str): The container ID.
    
    Returns:
        float: The CPU usage percentage, or 0.0 if all methods fail.
    """
    def run_command(command):
        """
        Helper to execute a shell command and return its output.
        Args:
            command (str): The command to run.
        Returns:
            str: The output of the command.
        """
        import subprocess
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logging.warning(f"Command failed: {command}, Error: {e}")
            return ""

    def loadavg_method(ctid):
        """Calculate CPU usage based on system's load average."""
        try:
            cmd_loadavg = f"pct exec {ctid} -- cat /proc/loadavg"
            loadavg_output = run_command(cmd_loadavg)
            loadavg = float(loadavg_output.split()[0])

            cmd_nproc = f"pct exec {ctid} -- nproc"
            nproc_output = run_command(cmd_nproc)
            num_cpus = int(nproc_output)

            if num_cpus == 0:
                raise ValueError("Number of CPUs is zero.")
            
            cpu_usage = min((loadavg / num_cpus) * 100, 100.0)
            return round(cpu_usage, 2)
        except Exception as e:
            raise RuntimeError(f"Loadavg method failed: {e}")

    def load_method(ctid):
        """Calculate CPU usage using /proc/stat."""
        try:
            cmd = f"pct exec {ctid} -- cat /proc/stat | grep '^cpu '"
            result = run_command(cmd)
            initial_cpu_times = list(map(float, result.split()[1:]))
            initial_total_time = sum(initial_cpu_times)
            initial_idle_time = initial_cpu_times[3]

            time.sleep(1)

            result = run_command(cmd)
            new_cpu_times = list(map(float, result.split()[1:]))
            new_total_time = sum(new_cpu_times)
            new_idle_time = new_cpu_times[3]

            total_diff = new_total_time - initial_total_time
            idle_diff = new_idle_time - initial_idle_time

            if total_diff == 0:
                raise ValueError("Total CPU time did not change.")

            cpu_usage = 100.0 * (total_diff - idle_diff) / total_diff
            return round(max(min(cpu_usage, 100.0), 0.0), 2)
        except Exception as e:
            raise RuntimeError(f"Load method failed: {e}")

    def cgroup_method(ctid):
        """Retrieve CPU usage from cgroup stats."""
        try:
            cmd = f"pct exec {ctid} -- cat /sys/fs/cgroup/cpu/cpuacct.usage"
            initial_usage = float(run_command(cmd))
            time.sleep(1)
            usage_after = float(run_command(cmd))

            usage_diff = usage_after - initial_usage
            cpu_usage_seconds = usage_diff / 1e9
            cpu_usage = min(cpu_usage_seconds * 100, 100.0)
            return round(cpu_usage, 2)
        except Exception as e:
            raise RuntimeError(f"CGroup method failed: {e}")

    def top_method(ctid):
        """Retrieve CPU usage using the top command."""
        try:
            cmd = f"pct exec {ctid} -- top -bn1 | grep 'Cpu(s)'"
            result = run_command(cmd)
            parts = result.split(',')
            idle_part = next((p for p in parts if 'id' in p), None)
            if idle_part:
                idle = float(idle_part.strip().split('%')[0])
                cpu_usage = 100.0 - idle
                return round(cpu_usage, 2)
            raise ValueError("Idle CPU information not found.")
        except Exception as e:
            raise RuntimeError(f"Top method failed: {e}")

    def ps_method(ctid):
        """Retrieve CPU usage by aggregating CPU usage of processes."""
        try:
            cmd = f"pct exec {ctid} -- ps -eo %cpu --no-headers"
            result = run_command(cmd)
            if not result:
                return 0.0
            cpu_usages = list(map(float, result.split()))
            cpu_usage = min(sum(cpu_usages), 100.0)
            return round(cpu_usage, 2)
        except Exception as e:
            raise RuntimeError(f"PS method failed: {e}")

    # Methods in priority order
    methods = [
        ("Load Average Method", loadavg_method),
        ("Load Method", load_method),
        ("CGroup Method", cgroup_method),
        ("Top Command Method", top_method),
        ("PS Command Method", ps_method),
    ]

    for method_name, method in methods:
        try:
            cpu = method(ctid)
            if cpu is not None and cpu >= 0.0:
                logging.info(f"CPU usage for container {ctid} using {method_name}: {cpu}%")
                return cpu
        except Exception as e:
            logging.warning(f"{method_name} failed for container {ctid}: {e}")

    logging.error(f"All methods failed to retrieve CPU usage for container {ctid}. Returning 0.0.")
    return 0.0




def get_memory_usage(ctid):
    """
    Retrieve the memory usage of a container.

    Args:
        ctid (str): The container ID.

    Returns:
        float: The memory usage percentage, or 0.0 if an error occurs.
    """
    mem_info = run_command(
        f"pct exec {ctid} -- awk '/MemTotal/ {{total=$2}} /MemAvailable/ {{available=$2}} END {{print total, total-available}}' /proc/meminfo"
    )
    if mem_info:
        try:
            total, used = map(int, mem_info.split())
            return (used * 100) / total
        except ValueError:
            logging.error(f"Failed to parse memory info for container {ctid}: '{mem_info}'")
    logging.error(f"Failed to retrieve memory usage for container {ctid}")
    return 0.0

def is_ignored(ctid):
    """
    Check if a container is in the ignore list.

    Args:
        ctid (str): The container ID.

    Returns:
        bool: True if the container is in the ignore list, otherwise False.
    """
    return str(ctid) in IGNORE_LXC

def get_container_data(ctid):
    """
    Collect CPU and memory usage data for a specific container.

    Args:
        ctid (str): The container ID.

    Returns:
        dict or None: A dictionary with CPU and memory usage data, or None if the container is ignored or not running.
    """
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

def collect_container_data():
    """
    Collect data about all containers in parallel using threads.

    Returns:
        dict: A dictionary where the keys are container IDs and the values are their respective data.
    """
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

def prioritize_containers(containers):
    """
    Prioritize containers based on their CPU and memory usage.

    Args:
        containers (dict): A dictionary where the keys are container IDs and the values are their respective data.

    Returns:
        list: A list of container IDs sorted by priority (high to low usage).
    """
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

def get_container_config(ctid):
    """
    Get the configuration for a specific container based on its assigned tier.

    Args:
        ctid (str): The container ID.

    Returns:
        dict: The configuration for the container.
    """
    return LXC_TIER_ASSOCIATIONS.get(ctid, DEFAULTS)

def generate_unique_snapshot_name(base_name):
    """
    Generate a unique name for a snapshot based on the current timestamp.

    Args:
        base_name (str): The base name for the snapshot.

    Returns:
        str: A unique snapshot name.
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{base_name}-{timestamp}"

def generate_cloned_hostname(base_name, clone_number):
    """
    Generate a hostname for a cloned container.

    Args:
        base_name (str): The base name for the container.
        clone_number (int): The clone number to ensure uniqueness.

    Returns:
        str: A unique hostname for the cloned container.
    """
    return f"{base_name}-cloned-{clone_number}"
