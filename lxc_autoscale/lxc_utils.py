import json
import logging
import os
import re
import shlex
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

# Dedicated lock for the shared JSON event log
_log_lock = Lock()

# Per-container locks — created on demand so concurrent threads for
# *different* containers no longer block each other.
_container_locks: Dict[str, Lock] = {}
_locks_mutex = Lock()


def _get_container_lock(ctid: str) -> Lock:
    """Return a per-container lock, creating one on first access."""
    with _locks_mutex:
        if ctid not in _container_locks:
            _container_locks[ctid] = Lock()
        return _container_locks[ctid]

_CTID_RE = re.compile(r'^[0-9]+$')

def validate_container_id(ctid: str) -> None:
    """Validate that a container ID consists only of digits.

    Args:
        ctid: The container ID to validate.

    Raises:
        ValueError: If the container ID is not a valid numeric string.
    """
    if not _CTID_RE.match(ctid):
        raise ValueError(f"Invalid container ID: {ctid!r}")

# Global variable to hold the SSH client
ssh_client: Optional[paramiko.SSHClient] = None

def get_ssh_client() -> Optional['paramiko.SSHClient']:
    """Get or create SSH client with better error handling."""
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
            logging.error(f"Failed to create SSH client: {e}")
            return None
    return ssh_client

def close_ssh_client() -> None:
    """Close the SSH client connection."""
    global ssh_client
    if ssh_client:
        logging.debug("Closing SSH connection...")
        ssh_client.close()
        logging.info("SSH connection closed.")
        ssh_client = None

def run_command(cmd: Union[str, List[str]], timeout: int = 30) -> Optional[str]:
    """Execute a command locally or remotely based on configuration.

    Args:
        cmd: The command to execute. Use a list for shell=False local execution.
        timeout: Timeout in seconds for the command execution.

    Returns:
        The command output or None if the command failed.
    """
    use_remote_proxmox = config.get('DEFAULT', {}).get('use_remote_proxmox', False)
    logging.debug("Inside run_command: use_remote_proxmox = %s", use_remote_proxmox)
    logging.debug(f"Running command: {cmd} (timeout: {timeout}s)")
    return (run_remote_command if use_remote_proxmox else run_local_command)(cmd, timeout)


def run_local_command(cmd: Union[str, List[str]], timeout: int = 30) -> Optional[str]:
    """Execute a command locally with timeout.

    Always uses ``shell=False`` to prevent shell-injection attacks.
    String commands are split via :func:`shlex.split`.

    Args:
        cmd: The command to execute (list preferred; strings are split safely).
        timeout: Timeout in seconds for the command execution.

    Returns:
        The command output or None if the command failed.
    """
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    try:
        result = subprocess.check_output(
            cmd, shell=False, timeout=timeout, stderr=subprocess.STDOUT,
        ).decode('utf-8').strip()
        logging.debug(f"Command '{cmd}' executed successfully. Output: {result}")
        return result
    except subprocess.TimeoutExpired:
        logging.error("Command '%s' timed out after %d seconds", cmd, timeout)
    except subprocess.CalledProcessError as e:
        logging.error("Command '%s' failed: %s", cmd, e.output.decode('utf-8'))
    except Exception as e:  # pylint: disable=broad-except
        logging.error("Unexpected error executing '%s': %s", cmd, str(e))
    return None


def run_remote_command(cmd: Union[str, List[str]], timeout: int = 30) -> Optional[str]:
    """Execute a command on a remote Proxmox host via SSH.

    Args:
        cmd: The command to execute. A list is joined into a quoted shell
             command string before being sent to the remote host.
        timeout: Timeout in seconds for the command execution.

    Returns:
        The command output or None if the command failed.
    """
    if isinstance(cmd, list):
        cmd = shlex.join(cmd)
    logging.debug("Running remote command: %s", cmd)
    ssh = get_ssh_client()
    if not ssh:
        return None
    try:
        _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
        output = stdout.read().decode('utf-8').strip()
        logging.debug(f"Remote command '{cmd}' executed successfully: {output}")
        return output
    except paramiko.SSHException as e:
        logging.error("SSH execution failed: %s", str(e))
    except Exception as e:  # pylint: disable=broad-except
        logging.error("Unexpected SSH error executing '%s': %s", cmd, str(e))
    return None


def get_containers() -> List[str]:
    """Return list of container IDs, excluding ignored ones."""
    output = run_command(["pct", "list"])
    if not output:
        return []

    container_list = []
    for line in output.splitlines()[1:]:  # skip header row
        parts = line.split()
        if not parts:
            continue
        ctid = parts[0]
        try:
            validate_container_id(ctid)
            container_list.append(ctid)
        except ValueError:
            logging.warning("Skipping container with invalid ID from pct list: %r", ctid)

    # Filter out ignored containers
    filtered_containers = [
        ctid for ctid in container_list
        if ctid and not is_ignored(ctid)
    ]
    logging.debug(f"Found containers: {filtered_containers}, ignored: {IGNORE_LXC}")
    return filtered_containers

def is_ignored(ctid: str) -> bool:
    """Check if container should be ignored."""
    ignored = str(ctid) in IGNORE_LXC
    logging.debug(f"Container {ctid} is ignored: {ignored}")
    return ignored

def is_container_running(ctid: str) -> bool:
    """Check if a container is running.

    Args:
        ctid: The container ID.

    Returns:
        True if the container is running, False otherwise.
    """
    validate_container_id(ctid)
    status = run_command(["pct", "status", ctid])
    running = bool(status and "status: running" in status.lower())
    logging.debug(f"Container {ctid} running status: {running}")
    return running


def backup_container_settings(ctid: str, settings: Dict[str, Any]) -> None:
    """Backup container configuration to JSON file.

    Args:
        ctid: The container ID.
        settings: The container settings to backup.
    """
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
        with _get_container_lock(ctid):
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
            with _get_container_lock(ctid):
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
        validate_container_id(ctid)
        run_command(["pct", "set", ctid, "-cores", str(settings['cores'])])
        run_command(["pct", "set", ctid, "-memory", str(settings['memory'])])


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
    with _log_lock:
        with open(LOG_FILE.replace('.log', '.json'), 'a', encoding='utf-8') as json_log_file:
            json_log_file.write(json.dumps(log_data) + '\n')
    logging.info("Logged event for container %s: %s - %s", ctid, action, resource_change)


def get_total_cores() -> int:
    """Calculate available CPU cores after reserving percentage.

    Returns:
        The available number of CPU cores.
    """
    total_cores = int(run_command(["nproc"]) or 0)
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
        output = run_command(["free", "-m"])
        total_memory = 0
        if output:
            for line in output.splitlines():
                if line.startswith("Mem:"):
                    total_memory = int(line.split()[1])
                    break
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


## ---------------------------------------------------------------------------
## CPU measurement helpers (module-level for caching across poll cycles)
## ---------------------------------------------------------------------------

# Cache: ctid -> cgroup file path that worked last time
_cgroup_path_cache: Dict[str, str] = {}

# Cache: ctid -> (usage_usec, monotonic_timestamp) from previous poll cycle.
# Allows delta calculation without sleeping on subsequent runs.
_prev_cpu_readings: Dict[str, Tuple[float, float]] = {}


def _get_num_cpus(ctid: str) -> int:
    """Parse core count from ``pct config`` output."""
    validate_container_id(ctid)
    config_output = run_command(["pct", "config", ctid])
    if config_output:
        for line in config_output.splitlines():
            if line.startswith("cores:"):
                return int(line.split()[1])
    return 1


def _read_cgroup_cpu_usec(ctid: str) -> Optional[float]:
    """Read cumulative CPU usage in microseconds from host-side cgroup.

    Tries cgroup v2 paths first, then cgroup v1.  The working path is
    cached so subsequent calls for the same container are a single ``cat``.
    """
    validate_container_id(ctid)

    # Fast path: use cached path
    cached = _cgroup_path_cache.get(ctid)
    if cached:
        val = _parse_cgroup_file(cached)
        if val is not None:
            return val
        # Cached path stopped working (container restarted?), rediscover.
        del _cgroup_path_cache[ctid]

    # cgroup v2 candidates (Proxmox VE 7+/8+)
    v2_paths = [
        f"/sys/fs/cgroup/lxc.payload.{ctid}/cpu.stat",
        f"/sys/fs/cgroup/lxc/{ctid}/cpu.stat",
    ]
    for path in v2_paths:
        val = _parse_cgroup_v2(path)
        if val is not None:
            _cgroup_path_cache[ctid] = path
            return val

    # cgroup v1 fallback
    v1_path = f"/sys/fs/cgroup/cpuacct/lxc/{ctid}/cpuacct.usage"
    val = _parse_cgroup_v1(v1_path)
    if val is not None:
        _cgroup_path_cache[ctid] = v1_path
        return val

    return None


def _parse_cgroup_file(path: str) -> Optional[float]:
    """Dispatch to v1 or v2 parser based on the file path."""
    if path.endswith("cpu.stat"):
        return _parse_cgroup_v2(path)
    return _parse_cgroup_v1(path)


def _parse_cgroup_v2(path: str) -> Optional[float]:
    """Extract ``usage_usec`` from a cgroup v2 ``cpu.stat`` file."""
    output = run_command(["cat", path])
    if not output:
        return None
    for line in output.splitlines():
        if line.startswith("usage_usec"):
            try:
                return float(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


def _parse_cgroup_v1(path: str) -> Optional[float]:
    """Read cgroup v1 ``cpuacct.usage`` (nanoseconds) and return microseconds."""
    output = run_command(["cat", path])
    if not output:
        return None
    try:
        return float(output.strip()) / 1000.0
    except ValueError:
        return None


def _cgroup_method(ctid: str) -> float:
    """Calculate CPU usage from host-side cgroup accounting.

    On the first call for a container there is no previous sample, so we
    sleep briefly and take two readings.  On subsequent poll cycles the
    cached previous reading is used, giving an accurate measurement over
    the full poll interval with zero extra overhead.
    """
    usage_usec = _read_cgroup_cpu_usec(ctid)
    if usage_usec is None:
        raise RuntimeError("cgroup CPU path not found")

    now = time.monotonic()
    prev = _prev_cpu_readings.get(ctid)

    if prev is None:
        # First reading — take a second sample after a short sleep.
        _prev_cpu_readings[ctid] = (usage_usec, now)
        time.sleep(2)
        usage_usec_2 = _read_cgroup_cpu_usec(ctid)
        if usage_usec_2 is None:
            raise RuntimeError("Failed to read second cgroup CPU sample")
        now_2 = time.monotonic()
        _prev_cpu_readings[ctid] = (usage_usec_2, now_2)
        delta_usec = usage_usec_2 - usage_usec
        delta_sec = now_2 - now
    else:
        prev_usec, prev_ts = prev
        _prev_cpu_readings[ctid] = (usage_usec, now)
        delta_usec = usage_usec - prev_usec
        delta_sec = now - prev_ts

    # Guard against counter resets (container restart) or clock issues
    if delta_sec <= 0 or delta_usec < 0:
        # Stale/reset reading — clear cache, return 0 this cycle
        _prev_cpu_readings.pop(ctid, None)
        return 0.0

    num_cpus = _get_num_cpus(ctid)
    # usage_usec accumulates across all CPUs; normalise by core count.
    cpu_pct = (delta_usec / (delta_sec * 1_000_000 * num_cpus)) * 100
    return round(max(min(cpu_pct, 100.0), 0.0), 2)


def _proc_stat_method(ctid: str) -> float:
    """Calculate CPU usage via /proc/stat inside the container.

    This is a fallback method — it requires LXCFS to be installed in
    the container for correct results.  Without LXCFS the container
    sees the *host* /proc/stat, giving wildly inaccurate readings.
    """
    validate_container_id(ctid)

    def _get_cpu_line() -> str:
        stat_output = run_command(["pct", "exec", ctid, "--", "cat", "/proc/stat"])
        if not stat_output:
            raise RuntimeError("Failed to read /proc/stat")
        for line in stat_output.splitlines():
            if line.startswith("cpu "):
                return line
        raise RuntimeError("/proc/stat has no aggregate cpu line")

    initial = _get_cpu_line()
    initial_values = list(map(int, initial.split()[1:]))
    initial_idle = initial_values[3] + initial_values[4]  # idle + iowait
    initial_total = sum(initial_values)

    time.sleep(2)

    current = _get_cpu_line()
    current_values = list(map(int, current.split()[1:]))
    current_idle = current_values[3] + current_values[4]
    current_total = sum(current_values)

    delta_idle = current_idle - initial_idle
    delta_total = current_total - initial_total

    if delta_total <= 0:
        return 0.0

    cpu_usage = ((delta_total - delta_idle) / delta_total) * 100
    return round(max(min(cpu_usage, 100.0), 0.0), 2)


def _loadavg_method(ctid: str) -> float:
    """Estimate CPU usage from load average inside the container."""
    validate_container_id(ctid)
    loadavg_output = run_command(["pct", "exec", ctid, "--", "cat", "/proc/loadavg"])
    if not loadavg_output:
        raise RuntimeError("Failed to read /proc/loadavg")

    loadavg = float(loadavg_output.split()[0])
    num_cpus = _get_num_cpus(ctid)
    return round(min((loadavg / num_cpus) * 100, 100.0), 2)


def get_cpu_usage(ctid: str) -> float:
    """Get container CPU usage using multiple fallback methods.

    Method priority:
      1. **cgroup** — reads host-side cgroup accounting (most accurate,
         no ``pct exec`` overhead, works without LXCFS).
      2. **proc_stat** — reads /proc/stat inside the container (requires
         LXCFS for correct results).
      3. **loadavg** — rough estimate from /proc/loadavg.

    Args:
        ctid: The container ID.

    Returns:
        CPU usage as a percentage (0.0–100.0).
    """
    validate_container_id(ctid)

    methods = [
        ("cgroup", _cgroup_method),
        ("proc_stat", _proc_stat_method),
        ("loadavg", _loadavg_method),
    ]

    for method_name, method in methods:
        try:
            cpu = method(ctid)
            if cpu is not None and cpu >= 0.0:
                logging.info("CPU usage for %s using %s: %.2f%%", ctid, method_name, cpu)
                return cpu
        except Exception as e:
            logging.debug("%s method failed for %s: %s", method_name, ctid, str(e))

    logging.error("All CPU usage methods failed for container %s, returning 0.0", ctid)
    return 0.0


def get_memory_usage(ctid: str) -> float:
    """Get container memory usage percentage.

    Args:
        ctid: The container ID.

    Returns:
        The memory usage as a float percentage (0.0 - 100.0).
    """
    validate_container_id(ctid)
    meminfo_output = run_command(["pct", "exec", ctid, "--", "cat", "/proc/meminfo"])
    if meminfo_output:
        try:
            total = used_calc = 0
            mem_available = None
            for line in meminfo_output.splitlines():
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_available = int(line.split()[1])
            if total and mem_available is not None:
                used_calc = total - mem_available
                mem_usage = (used_calc * 100) / total
                logging.info("Memory usage for %s: %.2f%%", ctid, mem_usage)
                return mem_usage
        except (ValueError, IndexError):
            logging.error("Failed to parse memory info for %s", ctid)
    logging.error("Failed to get memory usage for %s", ctid)
    return 0.0


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
        config_output = run_command(["pct", "config", ctid])
        cores = memory = 0
        if config_output:
            for line in config_output.splitlines():
                if line.startswith("cores:"):
                    cores = int(line.split()[1])
                elif line.startswith("memory:"):
                    memory = int(line.split()[1])
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
    """Get container tier configuration, falling back to DEFAULTS.

    Args:
        ctid: The container ID.

    Returns:
        The container's tier configuration.
    """
    from config import DEFAULTS
    tier = LXC_TIER_ASSOCIATIONS.get(ctid, DEFAULTS)
    logging.debug("Configuration for container %s: %s", ctid, tier)
    return tier


def generate_unique_snapshot_name(base_name: str) -> str:
    """Generate timestamped snapshot name.

    Args:
        base_name: Base name for the snapshot.

    Returns:
        A unique snapshot name.
    """
    snapshot_name = f"{base_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    logging.debug("Generated unique snapshot name: %s", snapshot_name)
    return snapshot_name


def generate_cloned_hostname(base_name: str, clone_number: int) -> str:
    """Generate unique hostname for cloned container.

    Strips non-RFC-1123 characters from *base_name* to prevent injection
    through hostnames.  Falls back to ``'container'`` when the sanitised
    name is empty.

    Args:
        base_name: Base name for the cloned container.
        clone_number: The clone number.

    Returns:
        A unique hostname for the cloned container.
    """
    sanitised = re.sub(r'[^a-zA-Z0-9-]', '-', str(base_name)).strip('-')
    if not sanitised:
        sanitised = 'container'
    hostname = f"{sanitised}-cloned-{clone_number}"
    logging.debug("Generated cloned hostname: %s", hostname)
    return hostname

import atexit
atexit.register(close_ssh_client)

