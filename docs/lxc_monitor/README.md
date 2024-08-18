# LXC Monitor Documentation

**LXC Monitor** is a Python-based service designed to monitor LXC containers on a Linux system, such as Proxmox. It periodically collects a wide range of metrics from running containers, including CPU usage, memory usage, I/O statistics, network usage, filesystem usage, and the number of running processes. These collected metrics are then exported to a JSON file, allowing for detailed analysis and monitoring.

## Summary

- **[Overview](#overview)**: Introduction to LXC Monitor and its core functionality.
- **[Features](#features)**: A detailed list of what LXC Monitor tracks and monitors.
- **[Installation and Setup](#installation-and-setup)**: Step-by-step guide to installing and configuring LXC Monitor.
  - [Prerequisites](#1-prerequisites)
  - [Configuration](#2-configuration)
  - [Service Configuration](#3-service-configuration)
  - [Installation](#4-installation)
- **[Usage](#usage)**: Instructions on how to start, stop, and manage the LXC Monitor service.
- **[Monitoring and Logs](#monitoring-and-logs)**: Information on where to find and how to use logs and exported metrics.
- **[Configuration Options](#configuration-options)**: Detailed descriptions of available logging and monitoring options.
- **[Code Structure](#code-structure)**: Explanation of the key functions and their roles in the LXC Monitor.
- **[Error Handling](#error-handling)**: Description of the error handling and retry logic implemented in the service.
- **[Best Practices and Tips](#best-practices-and-tips)**: Recommendations for optimizing your use of LXC Monitor.

---

## Overview

The **LXC Monitor** service is a lightweight but powerful tool that provides comprehensive monitoring of LXC containers on Linux-based systems. Designed with efficiency in mind, it gathers essential metrics from your containers, enabling you to keep a close eye on their performance and resource usage. Whether you're running a homelab, self-hosted services, or managing a larger scale environment, LXC Monitor ensures that you have the necessary insights to maintain optimal container performance.

---

## Features

LXC Monitor offers a robust set of features that cover all critical aspects of container performance:

- **CPU Monitoring**: Tracks CPU usage within each LXC container, helping you identify resource-intensive containers that may require attention.
- **Memory and Swap Monitoring**: Monitors both RAM and swap usage, ensuring you can detect and address potential memory bottlenecks or inefficiencies.
- **I/O Statistics**: Collects detailed input/output statistics for each container's storage devices, which is crucial for monitoring disk performance and spotting potential issues.
- **Network Usage**: Measures network activity, including bytes received and transmitted, enabling you to monitor network load and detect unusual traffic patterns.
- **Filesystem Monitoring**: Tracks filesystem usage, including total, used, and free space, to prevent storage-related issues.
- **Process Count**: Reports the number of processes running within each container, providing insights into container activity and potential process-related issues.
- **Parallel Processing**: Supports concurrent metric collection across multiple containers for efficiency, reducing the time required to gather data.
- **Configurable Logging**: Logs detailed information about the service's operation and container metrics, with customizable logging levels and rotation settings.

---

## Installation and Setup

Setting up LXC Monitor involves ensuring that your system meets the prerequisites, configuring the service, and installing it. Below is a detailed guide to help you get started.

### 1. Prerequisites

Before installing LXC Monitor, make sure your system meets the following requirements:

- **Python 3.7+**: Ensure that Python is installed on your system. You can verify the installed version by running:
  ```bash
  python3 --version
  ```
- **LXC**: LXC (Linux Containers) must be installed and properly configured on your server. This includes having your containers up and running.
- **YAML Configuration**: LXC Monitor uses a YAML file for its configuration. Ensure that you are familiar with YAML syntax and structure.

### 2. Configuration

Create the main configuration file at `/etc/lxc_monitor/lxc_monitor.yaml`. This file will define how the monitoring service operates, including where to log information and how often to check for metrics.

#### Example Configuration:

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

#### Explanation of Configuration Options:

- **Logging Section**:
  - **log_file**: Specifies where the service logs its activity.
  - **log_max_bytes**: Sets the maximum size of the log file before it is rotated. This helps manage disk space usage.
  - **log_backup_count**: Determines how many rotated log files to keep. This ensures you have access to historical logs without consuming too much storage.
  - **log_level**: Sets the verbosity of logs. Common settings include `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.

- **Monitoring Section**:
  - **export_file**: Path to the JSON file where collected metrics are exported.
  - **check_interval**: Time interval between each metrics collection cycle. A shorter interval provides more frequent updates but may increase system load.
  - **enable_swap**: Enables or disables monitoring of swap memory usage.
  - **enable_network**: Controls whether network statistics are collected.
  - **enable_filesystem**: Toggles the monitoring of filesystem usage.
  - **parallel_processing**: If enabled, the service will collect metrics concurrently across containers, speeding up the monitoring process.
  - **max_workers**: Sets the maximum number of parallel workers used for metrics collection.
  - **excluded_devices**: Lists device types to exclude from I/O statistics (e.g., loop devices or device mapper paths).

### 3. Service Configuration

To run LXC Monitor as a systemd service, you'll need to create a service configuration file. This file tells systemd how to manage the LXC Monitor service.

#### Example Service Configuration:

Create the file `/etc/systemd/system/lxc_monitor.service` with the following content:

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

- **Description**: Describes the service for systemd.
- **ExecStart**: Specifies the command to start the service, pointing to the Python script that runs LXC Monitor.
- **WorkingDirectory**: Sets the working directory for the service.
- **StandardOutput** and **StandardError**: Ensure that output and errors are handled correctly by systemd.
- **Restart**: Configures the service to restart automatically on failure.
- **EnvironmentFile**: Points to the configuration file for environment variables.

### 4. Installation

To install LXC Monitor, follow these steps:

1. **Place the Python Script**: Move the `lxc_monitor.py` script to `/usr/local/bin/`:
   ```bash
   sudo cp lxc_monitor.py /usr/local/bin/
   ```

2. **Reload systemd**: Reload systemd to recognize the new service:
   ```bash
   sudo systemctl daemon-reload
   ```

3. **Enable and Start the Service**: Enable the service to start at boot and start it immediately:
   ```bash
   sudo systemctl enable lxc_monitor.service
   sudo systemctl start lxc_monitor.service
   ```

This completes the installation process, and the service should now be running and monitoring your LXC containers.

---

## Usage

LXC Monitor runs as a background service, continuously collecting metrics based on the configured interval. Below are some common commands to manage the service.

### Starting the Service

The LXC Monitor service should start automatically after installation. However, you can manually control the service using systemd commands:

- **Start the service**:
  ```bash
  sudo systemctl start lxc_monitor.service
  ```

- **Stop the service**:
  ```bash
  sudo systemctl stop lxc_monitor.service
  ```

- **Restart the service**:
  ```bash
  sudo systemctl restart lxc_monitor.service
  ```

- **Check the service status**:
  ```bash
  sudo systemctl status lxc_monitor.service
  ```

These commands allow you to manage the service as needed, such as restarting it after making configuration changes.

---

## Monitoring and Logs

### Logs

LXC Monitor logs its operations to a file specified in the configuration. The log file is crucial for tracking the service’s behavior and diagnosing any issues.

- **Log File**: `/var/log/lxc_monitor.log`
- **Log Rotation**: The log file rotates daily, with a maximum of 7 backup files kept by default. This rotation prevents the log from consuming too much disk space.

You can view the logs in real-time using the `tail` command:



```bash
tail -f /var/log/lxc_monitor.log
```

### Metrics

The metrics collected by LXC Monitor are exported to a JSON file:

- **Metrics File**: `/var/log/lxc_metrics.json`
- **File Structure**: The JSON file contains an array of objects, each representing the metrics collected from a container at a specific time. This structure is suitable for importing into monitoring tools or for custom analysis.

Example JSON output:

```json
[
  {
    "container_id": "100",
    "timestamp": "2024-08-14T22:04:45Z",
    "cpu_usage": 15.6,
    "memory_usage": 512,
    "swap_usage": 0,
    "io_read_bytes": 102400,
    "io_write_bytes": 204800,
    "network_received_bytes": 12345678,
    "network_transmitted_bytes": 87654321,
    "filesystem_usage": {
      "total": 10485760,
      "used": 5242880,
      "free": 5242880
    },
    "process_count": 25
  }
]
```

---

## Configuration Options

LXC Monitor’s behavior can be finely tuned through its configuration file. Below are the detailed options available:

### Logging Configuration

- **log_file**: The full path to the log file.
- **log_max_bytes**: The maximum size of the log file in bytes before it’s rotated. Set this based on available disk space and expected log verbosity.
- **log_backup_count**: The number of rotated log files to retain. Increasing this value allows for more historical log data but requires more storage.
- **log_level**: Controls the verbosity of the log output. Use `DEBUG` for detailed information during development or troubleshooting, and `INFO` or higher for regular operation.

### Monitoring Configuration

- **export_file**: Path to the JSON file where the collected metrics are stored. Ensure this location has sufficient space for the metrics data.
- **check_interval**: Defines how frequently (in seconds) metrics are collected. Shorter intervals provide more up-to-date data but can increase system load.
- **enable_swap**: Enables or disables the monitoring of swap memory usage. Disable this if swap usage is not a concern.
- **enable_network**: Toggles network usage monitoring. Disable if network metrics are unnecessary to reduce overhead.
- **enable_filesystem**: Controls whether filesystem usage is tracked. This can be disabled for containers where disk usage is not relevant.
- **parallel_processing**: Enables concurrent metric collection across containers, reducing the time required to gather data. Particularly useful on systems with many containers.
- **max_workers**: Sets the number of parallel workers used when `parallel_processing` is enabled. Increase this value on systems with many CPU cores to speed up data collection.
- **excluded_devices**: A list of device types to exclude from I/O statistics. This is useful for ignoring irrelevant or non-critical devices.

---

## Code Structure

LXC Monitor is built using a modular Python codebase. Here’s a breakdown of its key functions:

- **get_running_lxc_containers()**: Retrieves a list of all currently running LXC containers. This is the first step in collecting metrics.
- **run_command(command)**: Executes a shell command and returns the output. This function is used throughout the service to interact with the system and gather data.
- **retry_on_failure(func, *args, **kwargs)**: Retries a function up to 3 times in case of failure, with a delay between attempts. This is used to improve reliability, particularly for commands that might occasionally fail.
- **get_container_cpu_usage(container_id, executor)**: Collects CPU usage metrics for a specific container. CPU usage is a key performance indicator for most containers.
- **get_container_memory_usage(container_id, executor)**: Gathers memory and swap usage data. This function ensures that you have a clear view of each container’s memory footprint.
- **get_container_io_stats(container_id, executor)**: Retrieves I/O statistics for storage devices associated with a container, helping you monitor disk performance.
- **get_container_network_usage(container_id, executor)**: Collects data on network usage, tracking both received and transmitted bytes.
- **get_container_filesystem_usage(container_id, executor)**: Monitors the filesystem usage, including total, used, and free space. This is crucial for avoiding disk space issues.
- **get_container_process_count(container_id, executor)**: Counts the number of processes running within a container, which can indicate the container’s activity level.
- **collect_metrics_for_container(container_id, executor)**: Collects all relevant metrics for a specific container by calling the individual metric functions.
- **collect_and_export_metrics()**: Gathers metrics from all containers and exports them to the JSON file. This function is the core of the monitoring loop.
- **monitor_and_export()**: The main loop of the service, continuously collecting and exporting metrics based on the configured interval.

---

## Error Handling

LXC Monitor includes robust error handling to ensure reliable operation even in the face of occasional issues. The service uses a retry mechanism for critical commands, attempting up to 3 retries before logging an error. This helps mitigate temporary issues, such as momentary network disruptions or transient system errors.

### Example:

If a command to gather CPU usage fails, `retry_on_failure` will attempt the command again after a short delay. If all retries fail, the issue is logged, but the service continues monitoring other containers. This approach ensures that a single failure does not disrupt the entire monitoring process.

---

## Best Practices and Tips

### 1. Regularly Review Logs
Monitoring logs provide valuable insights into the service's performance and any potential issues. Regularly reviewing these logs can help you catch and resolve problems early.

### 2. Optimize Configuration for Your Environment
Tailor the configuration file to your specific needs. For instance, if network metrics are not essential, disabling them can reduce the overhead on your system. Similarly, adjust `check_interval` based on how frequently you need updated metrics.

### 3. Monitor Disk Space
Ensure that the system has sufficient disk space for both logs and the metrics JSON file. Consider setting up log rotation and monitoring the size of the metrics file to avoid storage issues.

### 4. Test Configuration Changes
Before applying significant changes to the monitoring configuration, test them in a non-production environment. This can help you understand the impact of the changes and avoid disrupting critical services.

### 5. Use Parallel Processing Wisely
If your system has multiple containers, enabling parallel processing can significantly speed up metrics collection. However, ensure that your system has enough CPU resources to handle the additional load from multiple workers.
