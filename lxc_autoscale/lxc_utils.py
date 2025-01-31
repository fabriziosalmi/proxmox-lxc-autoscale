import json
import logging
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import paramiko
except ImportError:
    logging.error("Paramiko package not installed. SSH functionality disabled.")

from config import (BACKUP_DIR,  IGNORE_LXC, LOG_FILE,
                    LXC_TIER_ASSOCIATIONS, PROXMOX_HOSTNAME, config, get_config_value)

lock = Lock()

# Global variable to hold the SSH client
ssh_client: Optional[paramiko.SSHClient] = None

def get_ssh_client() -> Optional[paramiko.SSHClient]:
    """Get or create a new SSH client connection."""
    global ssh_client
    if ssh_client is None:
        logging.debug("Creating a new SSH connection...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                hostname=config.get('DEFAULT', {}).get('proxmox_host'),
                port=config.get('DEFAULT', {}).get('ssh_port', 22),
                username=config.get('DEFAULT', {}).get('ssh_user'),
                password=config.get('DEFAULT', {}).get('ssh_password'),
                key_filename=config.get('DEFAULT', {}).get('ssh_key_path'),
                timeout=10
            )
            logging.info("SSH connection established successfully.")
            ssh_client = ssh
        except paramiko.SSHException as e:
            logging.error("SSH connection failed: %s", str(e))
            return None
        except Exception as e:
            logging.error("Unexpected error establishing SSH connection: %s", str(e))
            return None
    return ssh_client

def close_ssh_client() -> None:
    """Close the SSH client connection."""
    global ssh_client
    if ssh_client:
        logging.debug("Closing SSH connection...")
        ssh_client.close()
        ssh_client = None

def run_command(cmd: str, timeout: int = 30) -> Optional[str]:
    """Execute a command locally or remotely based on configuration.

    Args:
        cmd: The command to execute.
        timeout: Timeout in seconds for the command execution.

    Returns:
        The command output or None if the command failed.
    """
    use_remote_proxmox = config.get('DEFAULT', {}).get('use_remote_proxmox', False)
    logging.debug("Inside run_command: use_remote_proxmox = %s", use_remote_proxmox)
    return (run_remote_command if use_remote_proxmox else run_local_command)(cmd, timeout)


def run_local_command(cmd: str, timeout: int = 30) -> Optional[str]:
    """Execute a command locally with timeout.

    Args:
        cmd: The command to execute.
        timeout: Timeout in seconds for the command execution.

    Returns:
        The command output or None if the command failed.
    """
    try:
        result = subprocess.check_output(
            cmd, shell=True, timeout=timeout, stderr=subprocess.STDOUT,
        ).decode('utf-8').strip()
        logging.debug("Command '%s' executed successfully. Output: %s", cmd, result)
        return result
    except subprocess.TimeoutExpired:
        logging.error("Command '%s' timed out after %d seconds", cmd, timeout)
    except subprocess.CalledProcessError as e:
        logging.error("Command '%s' failed: %s", cmd, e.output.decode('utf-8'))
    except Exception as e:  # pylint: disable=broad-except
        logging.error("Unexpected error executing '%s': %s", cmd, str(e))
    return None


def run_remote_command(cmd: str, timeout: int = 30) -> Optional[str]:
    """Execute a command on a remote Proxmox host via SSH.

    Args:
        cmd: The command to execute.
        timeout: Timeout in seconds for the command execution.

    Returns:
        The command output or None if the command failed.
    """
    logging.debug("Running remote command: %s", cmd)
    ssh = get_ssh_client()
    if not ssh:
        return None
    try:
        _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
        output = stdout.read().decode('utf-8').strip()
        logging.debug("Remote command '%s' executed successfully: %s", cmd, output)
        return output
    except paramiko.SSHException as e:
        logging.error("SSH execution failed: %s", str(e))
    except Exception as e:  # pylint: disable=broad-except
        logging.error("Unexpected SSH error executing '%s': %s", cmd, str(e))
    return None


def get_containers() -> List[str]:
    """Return list of container IDs, excluding ignored ones."""
    containers = run_command("pct list | awk 'NR>1 {print $1}'")
    if not containers:
        return []
        
    container_list = containers.splitlines()
    # Filter out ignored containers
    filtered_containers = [
        ctid for ctid in container_list 
        if ctid and not is_ignored(ctid)
    ]
    logging.debug(f"Found containers: {filtered_containers}, ignored: {IGNORE_LXC}")
    return filtered_containers

def is_ignored(ctid: str) -> bool:
    """Check if container should be ignored."""
    return ctid in IGNORE_LXC

def is_container_running(ctid: str) -> bool:
    """Check if a container is running.

    Args:
        ctid: The container ID.

    Returns:
        True if the container is running, False otherwise.
    """
    status = run_command(f"pct status {ctid}")
    return bool(status and "status: running" in status.lower())


def backup_container_settings(ctid: str, settings: Dict[str, Any]) -> None:
    """Backup container configuration to JSON file.

    Args:
        ctid: The container ID.
        settings: The container settings to backup.
    """
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
        with lock:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f)
        logging.debug("Backup saved for container %s: %s", ctid, settings)
    except Exception as e:  # pylint: disable=broad-except
        logging.error("Failed to backup settings for %s: %s", ctid, str(e))


def load_backup_settings(ctid: str) -> Optional[Dict[str, Any]]:
    """Load container configuration from a backup JSON file.

    Args:
        ctid: The container ID.

    Returns:
        The loaded container settings, or None if no backup is found.
    """
    try:
        backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
        if os.path.exists(backup_file):
            with lock:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            logging.debug("Loaded backup for container %s: %s", ctid, settings)
            return settings
        logging.warning("No backup found for container %s", ctid)
        return None
    except Exception as e:  # pylint: disable=broad-except
        logging.error("Failed to load backup for %s: %s", ctid, str(e))
        return None


def rollback_container_settings(ctid: str) -> None:
    """Restore container settings from backup.

    Args:
        ctid: The container ID.
    """
    settings = load_backup_settings(ctid)
    if settings:
        logging.info("Rolling back container %s to backup settings", ctid)
        run_command(f"pct set {ctid} -cores {settings['cores']}")
        run_command(f"pct set {ctid} -memory {settings['memory']}")


def log_json_event(ctid: str, action: str, resource_change: str) -> None:
    """Log container change events in JSON format.

    Args:
        ctid: The container ID.
        action: The action that was performed.
        resource_change: Details of the resource change.
    """
    log_data = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "proxmox_host": PROXMOX_HOSTNAME,
        "container_id": ctid,
        "action": action,
        "change": resource_change,
    }
    with lock:
        with open(LOG_FILE.replace('.log', '.json'), 'a', encoding='utf-8') as json_log_file:
            json_log_file.write(json.dumps(log_data) + '\n')


def get_total_cores() -> int:
    """Calculate available CPU cores after reserving percentage.

    Returns:
        The available number of CPU cores.
    """
    total_cores = int(run_command("nproc") or 0)
    reserved_cores = max(1, int(total_cores * int(get_config_value('DEFAULT', 'reserve_cpu_percent', 10)) / 100))
    available_cores = total_cores - reserved_cores
    logging.debug(
        "Total cores: %d, Reserved: %d, Available: %d",
        total_cores,
        reserved_cores,
        available_cores,
    )
    return available_cores


def get_total_memory() -> int:
    """Calculate available memory after reserving a fixed amount.

    Returns:
        The available memory in MB.
    """
    try:
        command_output = run_command("free -m | awk '/^Mem:/ {print $2}'")
        total_memory = int(command_output.strip()) if command_output else 0
    except (ValueError, subprocess.CalledProcessError) as e:
        logging.error("Failed to get total memory: %s", str(e))
        total_memory = 0

    available_memory = max(0, total_memory - int(get_config_value('DEFAULT', 'reserve_memory_mb', 2048)))
    logging.debug(
        "Total memory: %dMB, Reserved: %dMB, Available: %dMB",
        total_memory,
        int(get_config_value('DEFAULT', 'reserve_memory_mb', 2048)),
        available_memory,
    )
    return available_memory


def get_cpu_usage(ctid: str) -> float:
    """Get container CPU usage using multiple fallback methods.

    Args:
        ctid: The container ID.

    Returns:
        The CPU usage as a float percentage (0.0 - 100.0).
    """
    def loadavg_method(ctid: str) -> float:
        """Calculate CPU usage using load average from within the container."""
        try:
            # Use pct exec to run commands inside the container
            loadavg_output = run_command(f"pct exec {ctid} -- cat /proc/loadavg")
            if not loadavg_output:
                raise RuntimeError("Failed to get loadavg")
                
            loadavg = float(loadavg_output.split()[0])
            # Get number of CPUs allocated to the container
            num_cpus = int(run_command(f"pct config {ctid} | grep cores | awk '{{print $2}}'") or 1)
            
            return round(min((loadavg / num_cpus) * 100, 100.0), 2)
        except Exception as e:
            raise RuntimeError(f"Loadavg method failed: {str(e)}") from e

    def proc_stat_method(ctid: str) -> float:
        """Calculate CPU usage using /proc/stat from within the container."""
        try:
            # Get initial CPU stats from within container
            cmd1 = f"pct exec {ctid} -- cat /proc/stat | grep '^cpu '"
            initial = run_command(cmd1)
            if not initial:
                raise RuntimeError("Failed to get initial CPU stats")
                
            initial_values = list(map(int, initial.split()[1:]))
            initial_idle = initial_values[3]
            initial_total = sum(initial_values)

            # Wait a second
            time.sleep(1)

            # Get CPU stats again
            cmd2 = f"pct exec {ctid} -- cat /proc/stat | grep '^cpu '"
            current = run_command(cmd2)
            if not current:
                raise RuntimeError("Failed to get current CPU stats")
                
            current_values = list(map(int, current.split()[1:]))
            current_idle = current_values[3]
            current_total = sum(current_values)

            # Calculate usage
            total_diff = current_total - initial_total
            idle_diff = current_idle - initial_idle

            if total_diff == 0:
                return 0.0

            usage = ((total_diff - idle_diff) / total_diff) * 100
            return round(max(min(usage, 100.0), 0.0), 2)
        except Exception as e:
            raise RuntimeError(f"Proc stat method failed: {str(e)}") from e

    # Try each method in order
    methods = [
        ("Proc Stat", proc_stat_method),
        ("Load Average", loadavg_method)
    ]

    for method_name, method in methods:
        try:
            cpu = method(ctid)
            if cpu is not None and cpu >= 0.0:
                logging.info("CPU usage for %s using %s: %.2f%%", ctid, method_name, cpu)
                return cpu
        except Exception as e:
            logging.warning("%s failed for %s: %s", method_name, ctid, str(e))

    logging.error("All CPU usage methods failed for %s. Using 0.0", ctid)
    return 0.0


def get_memory_usage(ctid: str) -> float:
    """Get container memory usage percentage.

    Args:
        ctid: The container ID.

    Returns:
        The memory usage as a float percentage (0.0 - 100.0).
    """
    mem_info = run_command(
        f"pct exec {ctid} -- awk '/MemTotal/ {{t=$2}} /MemAvailable/ {{a=$2}} "
        f"END {{print t, t-a}}' /proc/meminfo"
    )
    if mem_info:
        try:
            total, used = map(int, mem_info.split())
            return (used * 100) / total
        except ValueError:
            logging.error("Failed to parse memory info for %s: '%s'", ctid, mem_info)
    logging.error("Failed to get memory usage for %s", ctid)
    return 0.0


def is_ignored(ctid: str) -> bool:
    """Check if a container is in the ignore list.

    Args:
        ctid: The container ID.

    Returns:
        True if the container is in the ignore list, False otherwise.
    """
    return str(ctid) in IGNORE_LXC


def get_container_data(ctid: str) -> Optional[Dict[str, Any]]:
    """Collect container resource usage data.

    Args:
        ctid: The container ID.

    Returns:
        A dictionary containing container resource data or None if not available.
    """
    if is_ignored(ctid) or not is_container_running(ctid):
        return None

    logging.debug("Collecting data for container %s", ctid)
    try:
        cores = int(run_command(f"pct config {ctid} | grep cores | awk '{{print $2}}'") or 0)
        memory = int(run_command(f"pct config {ctid} | grep memory | awk '{{print $2}}'") or 0)
        settings = {"cores": cores, "memory": memory}
        backup_container_settings(ctid, settings)
        return {
            "cpu": get_cpu_usage(ctid),
            "mem": get_memory_usage(ctid),
            "initial_cores": cores,
            "initial_memory": memory,
        }
    except Exception as e:  # pylint: disable=broad-except
        logging.error("Error collecting data for %s: %s", ctid, str(e))
        return None


def collect_container_data() -> Dict[str, Dict[str, Any]]:
    """Collect resource usage data for all containers."""
    containers: Dict[str, Dict[str, Any]] = {}
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(collect_data_for_container, ctid): ctid
            for ctid in lxc_utils.get_containers()
            if not lxc_utils.is_ignored(ctid)  # Double check ignore list
        }
        
        for future in as_completed(futures):
            ctid = futures[future]
            try:
                result = future.result()
                if result:
                    containers.update(result)
                    # Apply tier settings if container is in a tier
                    if ctid in LXC_TIER_ASSOCIATIONS:
                        tier_config = LXC_TIER_ASSOCIATIONS[ctid]
                        containers[ctid].update({
                            'cpu_upper_threshold': tier_config.get('cpu_upper_threshold'),
                            'cpu_lower_threshold': tier_config.get('cpu_lower_threshold'),
                            'memory_upper_threshold': tier_config.get('memory_upper_threshold'),
                            'memory_lower_threshold': tier_config.get('memory_lower_threshold'),
                            'min_cores': tier_config.get('min_cores'),
                            'max_cores': tier_config.get('max_cores'),
                            'min_memory': tier_config.get('min_memory'),
                            'core_min_increment': tier_config.get('core_min_increment'),
                            'core_max_increment': tier_config.get('core_max_increment'),
                            'memory_min_increment': tier_config.get('memory_min_increment'),
                            'min_decrease_chunk': tier_config.get('min_decrease_chunk')
                        })
                        logging.debug(f"Applied tier settings for container {ctid}")
            except Exception as e:
                logging.error(f"Error collecting data for container {ctid}: {e}")
    
    logging.info(f"Collected data for containers: {list(containers.keys())}")
    return containers


def prioritize_containers(containers: Dict[str, Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    """Sort containers by resource usage priority.

    Args:
        containers: A dictionary of container resource data.

    Returns:
        A sorted list of container IDs and their data.
    """
    if not containers:
        logging.info("No containers to prioritize.")
        return []

    try:
        priorities = sorted(
            containers.items(),
            key=lambda item: (item[1]['cpu'], item[1]['mem']),
            reverse=True,
        )
        logging.debug("Container priorities: %s", priorities)
        return priorities
    except Exception as e:  # pylint: disable=broad-except
        logging.error("Error prioritizing containers: %s", str(e))
        return []


def get_container_config(ctid: str) -> Dict[str, Any]:
    """Get container tier configuration.

    Args:
        ctid: The container ID.

    Returns:
        The container's tier configuration.
    """
    return LXC_TIER_ASSOCIATIONS.get(ctid, config)


def generate_unique_snapshot_name(base_name: str) -> str:
    """Generate timestamped snapshot name.

    Args:
        base_name: Base name for the snapshot.

    Returns:
        A unique snapshot name.
    """
    return f"{base_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def generate_cloned_hostname(base_name: str, clone_number: int) -> str:
    """Generate unique hostname for cloned container.

    Args:
        base_name: Base name for the cloned container.
        clone_number: The clone number.

    Returns:
        A unique hostname for the cloned container.
    """
    return f"{base_name}-cloned-{clone_number}"

import atexit
atexit.register(close_ssh_client)