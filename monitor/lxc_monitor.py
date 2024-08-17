import asyncio
import json
import logging
import os
import yaml
import psutil
from logging.handlers import TimedRotatingFileHandler
from subprocess import check_output, CalledProcessError
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Load configuration from YAML file
with open("/etc/lxc_monitor.yaml", 'r') as config_file:
    config = yaml.safe_load(config_file)

# Set up logging configuration
LOG_FILE = config['logging']['log_file']
LOG_MAX_BYTES = config['logging']['log_max_bytes']
LOG_BACKUP_COUNT = config['logging']['log_backup_count']
LOG_LEVEL = getattr(logging, config['logging']['log_level'].upper(), logging.INFO)

# Configure structured logging with time-based rotation and retention
logger = logging.getLogger("LXCMonitor")
logger.setLevel(LOG_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Timed rotating file handler with log retention
file_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", interval=1, backupCount=LOG_BACKUP_COUNT)
file_handler.setFormatter(formatter)
file_handler.suffix = "%Y-%m-%d"  # Filename will be suffixed with the date

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Monitoring configuration
EXPORT_FILE = config['monitoring']['export_file']
CHECK_INTERVAL = config['monitoring']['check_interval']
ENABLE_SWAP = config['monitoring']['enable_swap']
ENABLE_NETWORK = config['monitoring']['enable_network']
ENABLE_FILESYSTEM = config['monitoring']['enable_filesystem']
PARALLEL_PROCESSING = config['monitoring']['parallel_processing']
MAX_WORKERS = config['monitoring']['max_workers']
EXCLUDED_DEVICES = config['monitoring']['excluded_devices']
RETRY_LIMIT = config['monitoring'].get('retry_limit', 3)  # Maximum retry attempts
RETRY_DELAY = config['monitoring'].get('retry_delay', 2)  # Delay between retries in seconds

def get_running_lxc_containers():
    """Retrieve a list of running LXC containers."""
    try:
        pct_output = check_output(['pct', 'list'], text=True).splitlines()
        running_containers = [line.split()[0] for line in pct_output if 'running' in line]
        return running_containers
    except CalledProcessError as e:
        logger.error(f"Error retrieving LXC containers: {e}")
        return []

def run_command(command):
    """Run a shell command in a thread pool."""
    try:
        return check_output(command, text=True)
    except CalledProcessError as e:
        logger.error(f"Command failed: {command}, error: {e}")
        return None

async def retry_on_failure(func, *args, **kwargs):
    """Retry logic wrapper for transient failures."""
    for attempt in range(RETRY_LIMIT):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed for {func.__name__} with error: {e}")
            if attempt < RETRY_LIMIT - 1:
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"All {RETRY_LIMIT} attempts failed for {func.__name__}.")
                raise

async def get_container_cpu_usage(container_id, executor):
    """Use pct exec to retrieve CPU usage inside the container."""
    command = ['pct', 'exec', container_id, '--', 'grep', 'cpu ', '/proc/stat']
    result = await asyncio.get_event_loop().run_in_executor(executor, run_command, command)
    if result:
        fields = result.split()
        if len(fields) < 5:
            logger.warning(f"Unexpected CPU stat format for container {container_id}: {fields}")
            return 0.0
        idle_time = int(fields[4])
        total_time = sum(int(field) for field in fields[1:])
        cpu_usage = 100 * (1 - (idle_time / total_time))
        return cpu_usage
    return 0.0

async def get_container_memory_usage(container_id, executor):
    """Use pct exec to retrieve memory and swap usage inside the container."""
    try:
        command = ['pct', 'exec', container_id, '--', 'grep', 'MemTotal', '/proc/meminfo']
        result = await asyncio.get_event_loop().run_in_executor(executor, run_command, command)
        mem_total_kb = int(result.split()[1])

        command = ['pct', 'exec', container_id, '--', 'grep', 'MemAvailable', '/proc/meminfo']
        result = await asyncio.get_event_loop().run_in_executor(executor, run_command, command)
        mem_available_kb = int(result.split()[1])

        mem_used_kb = mem_total_kb - mem_available_kb

        swap_used_kb = swap_total_kb = 0
        if ENABLE_SWAP:
            command = ['pct', 'exec', container_id, '--', 'grep', 'SwapTotal', '/proc/meminfo']
            result = await asyncio.get_event_loop().run_in_executor(executor, run_command, command)
            swap_total_kb = int(result.split()[1])

            command = ['pct', 'exec', container_id, '--', 'grep', 'SwapFree', '/proc/meminfo']
            result = await asyncio.get_event_loop().run_in_executor(executor, run_command, command)
            swap_free_kb = int(result.split()[1])
            swap_used_kb = swap_total_kb - swap_free_kb

        return {
            "memory_usage_mb": mem_used_kb / 1024,  # Convert to MB
            "swap_usage_mb": swap_used_kb / 1024,  # Convert to MB
            "swap_total_mb": swap_total_kb / 1024  # Convert to MB
        }
    except (CalledProcessError, ValueError) as e:
        logger.warning(f"Failed to get memory/swap usage for container {container_id}: {e}")
        return {"memory_usage_mb": 0.0, "swap_usage_mb": 0.0, "swap_total_mb": 0.0}

async def get_container_io_stats(container_id, executor):
    """Use pct exec to retrieve I/O statistics inside the container."""
    command = ['pct', 'exec', container_id, '--', 'grep', '', '/proc/diskstats']
    result = await asyncio.get_event_loop().run_in_executor(executor, run_command, command)
    if result:
        io_stats_lines = result.splitlines()
        io_stats = {"reads": 0, "writes": 0}
        for line in io_stats_lines:
            fields = line.split()
            if len(fields) < 10:
                logger.warning(f"Unexpected disk stats format for container {container_id}: {fields}")
                continue
            device = fields[2]
            if any(device.startswith(exclude) for exclude in EXCLUDED_DEVICES):
                continue
            reads = int(fields[5])
            writes = int(fields[9])
            io_stats["reads"] += reads
            io_stats["writes"] += writes
        return io_stats
    return {}

async def get_container_network_usage(container_id, executor):
    """Use pct exec to retrieve network usage inside the container."""
    if not ENABLE_NETWORK:
        return {"rx_bytes": 0, "tx_bytes": 0}

    command = ['pct', 'exec', container_id, '--', 'cat', '/proc/net/dev']
    result = await asyncio.get_event_loop().run_in_executor(executor, run_command, command)
    if result:
        net_stats_lines = result.splitlines()[2:]  # Skip headers
        rx_bytes, tx_bytes = 0, 0
        for line in net_stats_lines:
            fields = line.split()
            if len(fields) < 10:
                logger.warning(f"Unexpected network stats format for container {container_id}: {fields}")
                continue
            iface = fields[0].split(':')[0]
            if iface != 'lo':  # Ignore loopback interface
                rx_bytes += int(fields[1])
                tx_bytes += int(fields[9])
        return {"rx_bytes": rx_bytes, "tx_bytes": tx_bytes}
    return {"rx_bytes": 0, "tx_bytes": 0}

async def get_container_filesystem_usage(container_id, executor):
    """Use pct exec to retrieve filesystem usage inside the container."""
    if not ENABLE_FILESYSTEM:
        return {"filesystem_usage_gb": 0, "filesystem_total_gb": 0, "filesystem_free_gb": 0}

    try:
        command = ['pct', 'exec', container_id, '--', 'df', '-m', '/']
        result = await asyncio.get_event_loop().run_in_executor(executor, run_command, command)
        if not result:
            command = ['pct', 'exec', container_id, '--', 'df', '-BM', '/']
            result = await asyncio.get_event_loop().run_in_executor(executor, run_command, command)

        lines = result.splitlines()
        if len(lines) < 2:
            logger.warning(f"Unexpected filesystem stats format for container {container_id}: {lines}")
            return {"filesystem_usage_gb": 0, "filesystem_total_gb": 0, "filesystem_free_gb": 0}

        filesystem_stats = lines[1].split()
        if len(filesystem_stats) < 4:
            logger.warning(f"Incomplete filesystem stats for container {container_id}: {filesystem_stats}")
            return {"filesystem_usage_gb": 0, "filesystem_total_gb": 0, "filesystem_free_gb": 0}

        filesystem_total_gb = int(filesystem_stats[1]) / 1024  # Convert MB to GB
        filesystem_usage_gb = int(filesystem_stats[2]) / 1024  # Convert MB to GB
        filesystem_free_gb = int(filesystem_stats[3]) / 1024   # Convert MB to GB

        return {
            "filesystem_usage_gb": filesystem_usage_gb,
            "filesystem_total_gb": filesystem_total_gb,
            "filesystem_free_gb": filesystem_free_gb
        }
    except CalledProcessError as e:
        logger.warning(f"Failed to get filesystem usage for container {container_id}: {e}")
        return {"filesystem_usage_gb": 0, "filesystem_total_gb": 0, "filesystem_free_gb": 0}

async def get_container_process_count(container_id, executor):
    """Use pct exec to retrieve the number of processes running inside the container."""
    command = ['pct', 'exec', container_id, '--', 'ps', '-e']
    result = await asyncio.get_event_loop().run_in_executor(executor, run_command, command)
    if result:
        lines = result.splitlines()
        # Check if the first line contains a header (e.g., "PID TTY TIME CMD") and remove it
        if lines and any(header in lines[0] for header in ["PID", "TTY", "TIME", "CMD"]):
            lines = lines[1:]
        return len(lines)
    return 0

async def collect_metrics_for_container(container_id, executor):
    logger.info(f"Collecting metrics for container: {container_id}")

    cpu_usage = await retry_on_failure(get_container_cpu_usage, container_id, executor)
    memory_swap_usage = await retry_on_failure(get_container_memory_usage, container_id, executor)
    io_stats = await retry_on_failure(get_container_io_stats, container_id, executor)
    network_usage = await retry_on_failure(get_container_network_usage, container_id, executor)
    filesystem_usage = await retry_on_failure(get_container_filesystem_usage, container_id, executor)
    process_count = await retry_on_failure(get_container_process_count, container_id, executor)

    container_metrics = {
        "timestamp": datetime.now().isoformat(),
        "cpu_usage_percent": cpu_usage,
        "memory_usage_mb": memory_swap_usage["memory_usage_mb"],
        "swap_usage_mb": memory_swap_usage["swap_usage_mb"],
        "swap_total_mb": memory_swap_usage["swap_total_mb"],
        "process_count": process_count,
        "io_stats": io_stats,
        "network_usage": network_usage,
        "filesystem_usage_gb": filesystem_usage["filesystem_usage_gb"],
        "filesystem_total_gb": filesystem_usage["filesystem_total_gb"],
        "filesystem_free_gb": filesystem_usage["filesystem_free_gb"]
    }

    logger.info(f"Metrics for {container_id}: "
                 f"CPU: {cpu_usage:.2f}%, Memory: {memory_swap_usage['memory_usage_mb']:.2f} MB, "
                 f"Swap Used: {memory_swap_usage['swap_usage_mb']:.2f} MB, Processes: {process_count}, "
                 f"Network: {network_usage}, Filesystem Used: {filesystem_usage['filesystem_usage_gb']} GB, "
                 f"Filesystem Free: {filesystem_usage['filesystem_free_gb']} GB, I/O: {io_stats}")

    return container_id, container_metrics

async def collect_and_export_metrics():
    start_time = datetime.now()
    metrics = {}
    containers = get_running_lxc_containers()

    if not containers:
        logger.info("No running LXC containers found.")
        return

    logger.debug(f"Found {len(containers)} running containers.")

    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    if PARALLEL_PROCESSING:
        tasks = [collect_metrics_for_container(container_id, executor) for container_id in containers]
        results = await asyncio.gather(*tasks)
    else:
        results = []
        for container_id in containers:
            result = await collect_metrics_for_container(container_id, executor)
            results.append(result)

    # Ensure results are processed correctly
    for container_id, container_metrics in results:
        metrics[container_id] = container_metrics

    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    # Add summary to the JSON output
    summary = {
        "collection_start_time": start_time.isoformat(),
        "collection_end_time": end_time.isoformat(),
        "total_containers": len(containers),
        "total_duration_seconds": total_duration,
        "monitor_cpu_percent": psutil.cpu_percent(),
        "monitor_memory_usage_mb": psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    }
    metrics["summary"] = summary

    # Load existing data if the file exists
    existing_data = []
    if os.path.exists(EXPORT_FILE):
        try:
            with open(EXPORT_FILE, "r") as json_file:
                existing_data = json.load(json_file)
                if not isinstance(existing_data, list):
                    logger.error(f"Data in {EXPORT_FILE} is not a list. Resetting data to an empty list.")
                    existing_data = []
            logger.debug(f"Loaded existing metrics from {EXPORT_FILE}.")
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to read existing data from {EXPORT_FILE}: {e}")
            existing_data = []

    # Append the new metrics
    existing_data.append(metrics)

    logger.debug(f"Appending new metrics: {metrics}")

    # Write the updated data to a temporary file first
    temp_file = f"{EXPORT_FILE}.tmp"
    try:
        with open(temp_file, "w") as json_file:
            json.dump(existing_data, json_file, indent=4)
        # Rename the temp file to the original file, ensuring atomic operation
        os.replace(temp_file, EXPORT_FILE)
        logger.info(f"Metrics successfully exported to {EXPORT_FILE}")
    except IOError as e:
        logger.error(f"Failed to write metrics to {EXPORT_FILE}: {e}")
        # If there's an error, remove the temporary file to avoid partial writes
        if os.path.exists(temp_file):
            os.remove(temp_file)

async def monitor_and_export():
    try:
        while True:
            logger.info("Starting new metrics collection cycle.")
            await collect_and_export_metrics()
            logger.info(f"Waiting for {CHECK_INTERVAL} seconds before next cycle.")
            await asyncio.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Shutting down metrics collector due to KeyboardInterrupt.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(monitor_and_export())
