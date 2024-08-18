# LXC Monitor

## Overview

The LXC Monitor Service is a Python-based service designed to monitor LXC containers on a Linux system. It periodically collects metrics from running containers, including CPU usage, memory usage, I/O statistics, network usage, filesystem usage, and the number of running processes. The collected metrics are exported to a JSON file for further analysis.

## Features

- **CPU Monitoring**: Tracks CPU usage within each LXC container.
- **Memory and Swap Monitoring**: Monitors memory and swap usage within containers.
- **I/O Statistics**: Collects input/output statistics for each container's storage devices.
- **Network Usage**: Measures network activity, including received and transmitted bytes.
- **Filesystem Monitoring**: Tracks filesystem usage, including total, used, and free space.
- **Process Count**: Reports the number of processes running within each container.
- **Parallel Processing**: Supports concurrent metric collection across multiple containers for efficiency.
- **Configurable Logging**: Logs detailed information about the service operation and container metrics.

## Installation and Setup

### 1. Prerequisites

- **Python 3.7+**: Ensure Python is installed on your system.
- **LXC**: LXC (Linux Containers) must be installed and configured on your server.
- **YAML Configuration**: A YAML configuration file is required for setting up the monitoring and logging preferences.

### 2. Configuration

Create the configuration file at `/etc/lxc_autoscale/lxc_monitor.yaml` with the following content:

```yaml
logging:
  log_file: "/var/log/lxc_monitor.log"
  log_max_bytes: 5242880  # 5 MB
  log_backup_count: 7
  log_level: "INFO"

monitoring:
  export_file: "/var/log/lxc_metrics.json"
  check_interval: 60  # seconds
  enable_swap: true
  enable_network: true
  enable_filesystem: true
  parallel_processing: true
  max_workers: 8
  excluded_devices: ['loop', 'dm-']
```

### 3. Service Configuration

Create a systemd service file at `/etc/systemd/system/lxc_monitor.service`:

```ini
[Unit]
Description=LXC Monitor Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/lxc_monitor.py
WorkingDirectory=/usr/local/bin/
StandardOutput=inherit
StandardError=inherit
Restart=on-failure
User=root

# Logging configuration
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/etc/lxc_monitor.yaml

[Install]
WantedBy=multi-user.target
```

### 4. Installation

1. **Place the Python script** (`lxc_monitor.py`) in `/usr/local/bin/`.
2. **Reload systemd** to recognize the new service:
   ```bash
   sudo systemctl daemon-reload
   ```
3. **Enable and start the service**:
   ```bash
   sudo systemctl enable lxc_monitor.service
   sudo systemctl start lxc_monitor.service
   ```

## Usage

### Starting the Service

The LXC Monitor Service starts automatically after installation. You can also manage it manually using systemd:

- **Start the service**: `sudo systemctl start lxc_monitor.service`
- **Stop the service**: `sudo systemctl stop lxc_monitor.service`
- **Restart the service**: `sudo systemctl restart lxc_monitor.service`
- **Check the service status**: `sudo systemctl status lxc_monitor.service`

### Monitoring and Logs

- **Logs**: The service logs its activity in `/var/log/lxc_monitor.log`. The log file rotates daily with a maximum of 7 backup files.
- **Metrics**: The collected metrics are stored in `/var/log/lxc_metrics.json`. The file contains an array of metrics data collected over time.

## Configuration Options

### Logging Configuration

- **log_file**: Path to the log file.
- **log_max_bytes**: Maximum size of the log file before rotation (in bytes).
- **log_backup_count**: Number of backup log files to keep.
- **log_level**: Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL).

### Monitoring Configuration

- **export_file**: Path to the JSON file where metrics are exported.
- **check_interval**: Time interval (in seconds) between monitoring cycles.
- **enable_swap**: Enable/disable swap memory monitoring.
- **enable_network**: Enable/disable network usage monitoring.
- **enable_filesystem**: Enable/disable filesystem usage monitoring.
- **parallel_processing**: Enable/disable parallel processing of metrics collection.
- **max_workers**: Maximum number of parallel workers if parallel processing is enabled.
- **excluded_devices**: List of device types to exclude from I/O statistics.

## Code Structure

- **get_running_lxc_containers()**: Retrieves a list of running LXC containers.
- **run_command(command)**: Executes a shell command.
- **retry_on_failure(func, *args, **kwargs)**: Retries a function on failure with a delay.
- **get_container_cpu_usage(container_id, executor)**: Retrieves CPU usage for a container.
- **get_container_memory_usage(container_id, executor)**: Retrieves memory and swap usage for a container.
- **get_container_io_stats(container_id, executor)**: Retrieves I/O statistics for a container.
- **get_container_network_usage(container_id, executor)**: Retrieves network usage for a container.
- **get_container_filesystem_usage(container_id, executor)**: Retrieves filesystem usage for a container.
- **get_container_process_count(container_id, executor)**: Retrieves the process count for a container.
- **collect_metrics_for_container(container_id, executor)**: Collects all metrics for a container.
- **collect_and_export_metrics()**: Collects metrics for all containers and exports them to a JSON file.
- **monitor_and_export()**: Main loop that continuously collects and exports metrics.

## Error Handling

The service includes error handling and retry logic for command execution. If a command fails, it retries up to 3 times before logging an error.
