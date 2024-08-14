
# Proxmox LXC AutoScale

## Overview

LXC AutoScale is a resource management daemon designed to **automatically adjust the CPU and memory allocations of LXC containers on Proxmox hosts** based on their current usage and pre-defined thresholds. It helps in optimizing resource utilization, ensuring that critical containers have the necessary resources while also (optionally) saving energy during off-peak hours.

✅ Tested on `Proxmox 8.2.4`

## Features

- **Automatic Resource Scaling:** Dynamically adjust CPU and memory based on usage thresholds.
- **Host Resource Reservation:** Ensure that the host system remains stable and responsive.
- **Energy Efficiency Mode:** Reduce resource allocation during off-peak hours to save energy.
- **Container Prioritization:** Prioritize resource allocation based on container groupings (e.g., critical, non-critical).
- **Automatic Backups:** Backup and rollback container configurations.
- **Gotify Notifications:** Optional integration with Gotify for real-time notifications.

## Installation

The easiest way to install LXC AutoScale is by using the following `curl` command:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

This script will:

1. Download the latest version of the LXC AutoScale Python script.
2. Download and install the systemd service file.
3. Set up the necessary directories and configuration files.
4. Back up any existing configuration files before updating them.
5. Enable and start the LXC AutoScale systemd service.

## Configuration

### Configuration File

The main configuration file is located at `/etc/lxc_autoscale/lxc_autoscale.conf`. This file defines various thresholds and settings for the daemon. If you need to customize the behavior of the daemon, you can edit this file.

**Backup of Configuration:**
Before any update, the installation script automatically backs up the existing configuration file to `/etc/lxc_autoscale/lxc_autoscale.conf.YYYYMMDD-HHMMSS.backup`.

### Default Configuration

These settings control how the script manages the scaling of CPU and memory resources for containers. The default configuration file contains the following sections and settings:

| **Parameter**              | **Default Value**                   | **Description**                                                                                                                                                           |
|----------------------------|-------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `poll_interval`            | 300                                 | The interval, in seconds, at which the script polls container metrics to determine if scaling actions are required. A shorter interval results in more frequent checks and potential adjustments. |
| `cpu_upper_threshold`      | 80                                  | The upper CPU usage threshold, expressed as a percentage, that triggers scaling up (adding more CPU cores) for a container. When a container's CPU usage exceeds this threshold, additional CPU cores may be allocated. |
| `cpu_lower_threshold`      | 20                                  | The lower CPU usage threshold, expressed as a percentage, that triggers scaling down (reducing CPU cores) for a container. When a container's CPU usage falls below this threshold, CPU cores may be deallocated to save resources. |
| `memory_upper_threshold`   | 80                                  | The upper memory usage threshold, expressed as a percentage, that triggers scaling up (increasing memory) for a container. When a container's memory usage exceeds this threshold, more memory may be allocated. |
| `memory_lower_threshold`   | 20                                  | The lower memory usage threshold, expressed as a percentage, that triggers scaling down (decreasing memory) for a container. When a container's memory usage falls below this threshold, memory may be reduced. |
| `core_min_increment`       | 1                                   | The minimum number of CPU cores to add to a container during a scaling up operation. This value ensures that scaling adjustments are not too granular, which could lead to excessive adjustments. |
| `core_max_increment`       | 4                                   | The maximum number of CPU cores that can be added to a container during a single scaling up operation. This prevents the script from allocating too many cores at once, which could negatively impact other containers or the host. |
| `memory_min_increment`     | 512                                 | The minimum amount of memory, in MB, to add to a container during a scaling up operation. This value ensures that scaling adjustments are significant enough to handle increased workloads. |
| `min_cores`                | 1                                   | The minimum number of CPU cores that any container should have. This prevents the script from reducing the CPU allocation below a functional minimum. |
| `max_cores`                | 8                                   | The maximum number of CPU cores that any container can have. This cap prevents any single container from monopolizing the host's CPU resources. |
| `min_memory`               | 512                                 | The minimum amount of memory, in MB, that any container should have. This ensures that no container is allocated too little memory to function properly. |
| `min_decrease_chunk`       | 512                                 | The minimum chunk size, in MB, by which memory can be reduced during a scaling down operation. This prevents the script from making overly granular and frequent reductions in memory, which could destabilize the container. |
| `reserve_cpu_percent`      | 10                                  | The percentage of the host's total CPU resources that should be reserved and not allocated to containers. This reserved capacity ensures that the host always has sufficient CPU resources for its own operations and for emergency situations. |
| `reserve_memory_mb`        | 2048                                | The amount of memory, in MB, that should be reserved on the host and not allocated to containers. This reserved memory ensures that the host has enough memory for its own operations and for handling unexpected loads. |
| `log_file`                 | `/var/log/lxc_autoscale.log`        | The file path where the script writes its log output. This log contains information about the script's operations, including any scaling actions taken. |
| `lock_file`                | `/var/lock/lxc_autoscale.lock`      | The file path for the lock file used by the script to prevent multiple instances from running simultaneously. This ensures that only one instance of the script manages resources at any given time. |
| `backup_dir`               | `/var/lib/lxc_autoscale/backups`    | The directory where backups of container configurations are stored before any scaling actions are taken. This allows for rollback in case of an issue with the scaling process. |
| `off_peak_start`           | 22                                  | The hour (in 24-hour format) at which off-peak energy-saving mode begins. During off-peak hours, the script may reduce resources to save energy if `energy_mode` is enabled. |
| `off_peak_end`             | 6                                   | The hour (in 24-hour format) at which off-peak energy-saving mode ends. After this time, containers may be scaled back up to handle peak load. |
| `energy_mode`              | False                               | A boolean setting that enables or disables energy-saving mode during off-peak hours. When enabled, this mode reduces CPU and memory resources allocated to containers during off-peak hours to save energy. |
| `gotify_url`               | Example: http://gotify.example.com  | The URL for a Gotify server used for sending notifications about scaling actions or other important events. If left blank, notifications will not be sent. |
| `gotify_token`             | Example: abcdef1234567890           | The authentication token for accessing the Gotify server. This token is required if `gotify_url` is set and notifications are to be sent. |

### Tiers

You can assign one or more LXC containers to different TIERS for specific thresholds assignements. You can define up to 3 different TIERS named TIER_1, TIER_2 and TIER_3. Just append and change accordingly with your needs this snippet to the `/etc/lcx_autoscale/lcx_autoscale.conf` configuration file and restart the service by running `systemctl restart lxc_autoscale`:

```
[TIER_1]
cpu_upper_threshold = 90
cpu_lower_threshold = 10
memory_upper_threshold = 90
memory_lower_threshold = 10
min_cores = 2
max_cores = 12
min_memory = 1024
nodes = 100, 101, 102  # Comma-separated list of LXC IDs

[TIER_2]
cpu_upper_threshold = 85
cpu_lower_threshold = 15
memory_upper_threshold = 85
memory_lower_threshold = 15
min_cores = 1
max_cores = 10
min_memory = 768
nodes = 103, 104, 105  # Comma-separated list of LXC IDs

[TIER_3]
cpu_upper_threshold = 80
cpu_lower_threshold = 20
memory_upper_threshold = 80
memory_lower_threshold = 20
min_cores = 1
max_cores = 8
min_memory = 512
nodes = 106, 107, 108  # Comma-separated list of LXC IDs
```

## Service Management

### Starting and Stopping the Service

Once installed, the LXC AutoScale daemon runs as a systemd service. You can manage the service using the following commands:

- **Start the service:**
  ```bash
  systemctl start lxc_autoscale.service
  ```

- **Stop the service:**
  ```bash
  systemctl stop lxc_autoscale.service
  ```

- **Restart the service:**
  ```bash
  systemctl restart lxc_autoscale.service
  ```

- **Check the status of the service:**
  ```bash
  systemctl status lxc_autoscale.service
  ```

### Enabling the Service at Boot

To ensure that the LXC AutoScale daemon starts automatically at boot, use the following command:

```bash
systemctl enable lxc_autoscale.service
```

## Logging

Logs for the LXC AutoScale daemon are stored in `/var/log/lxc_autoscale.log`. You can monitor this log file to observe the daemon's operations and troubleshoot any issues.

```
root@proxmox:~# tail -n50 /var/log/lxc_autoscale.log 
2024-08-14 13:26:56 - INFO - Starting resource allocation process...
2024-08-14 13:26:58 - DEBUG - Command 'pct list | awk 'NR>1 {print $1}'' executed successfully.
2024-08-14 13:26:59 - DEBUG - Command 'pct status 100' executed successfully.
024-08-14 13:26:59 - INFO - Collecting data for container 100...
2024-08-14 13:27:02 - DEBUG - Command 'pct config 100 | grep cores | awk '{print $2}'' executed successfully.
2024-08-14 13:27:04 - DEBUG - Command 'pct config 100 | grep memory | awk '{print $2}'' executed successfully.
2024-08-14 13:27:04 - INFO - Backup saved for container 100: {'cores': 2, 'memory': 2880}
2024-08-14 13:27:05 - DEBUG - Command 'pct exec 100 -- awk -v cores=$(nproc) '{usage+=$1} END {print usage/cores}' /proc/stat' executed successfully.
2024-08-14 13:27:07 - DEBUG - Command 'pct exec 100 -- awk '/MemTotal/ {total=$2} /MemAvailable/ {free=$2} END {print total-free}' /proc/meminfo' executed successfully.
2024-08-14 13:27:09 - DEBUG - Command 'pct exec 100 -- awk '/MemTotal/ {print $2}' /proc/meminfo' executed successfully.
2024-08-14 13:27:09 - DEBUG - Container 100 data: {'cpu': 0.0, 'mem': 13.37619357638889, 'initial_cores': 2, 'initial_memory': 2880}
2024-08-14 13:27:09 - DEBUG - Container priorities: [('100', {'cpu': 0.0, 'mem': 13.37619357638889, 'initial_cores': 2, 'initial_memory': 2880})]
2024-08-14 13:27:09 - DEBUG - Command 'nproc' executed successfully.
2024-08-14 13:27:09 - DEBUG - Total cores: 16, Reserved cores: 1, Available cores: 15
2024-08-14 13:27:09 - DEBUG - Command 'free -m | awk '/Mem:/ {print $2}'' executed successfully.
2024-08-14 13:27:09 - DEBUG - Total memory: 19999MB, Reserved memory: 2048MB, Available memory: 17951MB
2024-08-14 13:27:09 - INFO - Decreasing cores for container 100 by 2...
2024-08-14 13:27:10 - DEBUG - Command 'pct set 100 -cores 1' executed successfully.
2024-08-14 13:27:10 - WARNING - Gotify URL or Token not provided. Notification not sent.
2024-08-14 13:27:10 - INFO - Decreasing memory for container 100 by 2048MB...
2024-08-14 13:27:12 - DEBUG - Command 'pct set 100 -memory 832' executed successfully.
2024-08-14 13:27:12 - WARNING - Gotify URL or Token not provided. Notification not sent.
2024-08-14 13:27:12 - INFO - Final resources: 17 cores, 19999 MB memory
2024-08-14 13:27:12 - INFO - Resource allocation process completed. Next run in 300 seconds.
```

## Uninstallation

> [!TIP]
> The easiest way to uninstall LXC AutoScale is by using the following `curl` command:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/uninstall.sh | bash
```

If you wish to remove the LXC AutoScale daemon from your system manually, you can force to kill, disable and stop the service, then delete the associated files:

```bash
kill -9 $(ps aux | grep lxc_autoscale | grep -v grep | awk '{print $2}')
systemctl disable lxc_autoscale.service
systemctl stop lxc_autoscale.service
rm -f /usr/local/bin/lxc_autoscale.py
rm -f /etc/systemd/system/lxc_autoscale.service
rm -rf /etc/lxc_autoscale/
rm -rf /var/lib/lxc_autoscale/
```

## Application diagram

```
+------------------------------+
|        LXC AutoScale          |
+------------------------------+
              |
              v
+-----------------------------------------+
|             Configuration               |
| (config file: /etc/lxc_autoscale.conf)  |
|                                         |
| - poll_interval                         |
| - cpu_upper_threshold                   |
| - cpu_lower_threshold                   |
| - memory_upper_threshold                |
| - memory_lower_threshold                |
| - core_min_increment                    |
| - core_max_increment                    |
| - memory_min_increment                  |
| - min_cores                             |
| - max_cores                             |
| - min_memory                            |
| - min_decrease_chunk                    |
| - reserve_cpu_percent                   |
| - reserve_memory_mb                     |
| - log_file                              |
| - lock_file                             |
| - backup_dir                            |
| - off_peak_start                        |
| - off_peak_end                          |
| - energy_mode                           |
| - gotify_url                            |
| - gotify_token                          |
+-----------------------------------------+
              |
              v
+-----------------------------------------+
|          Main Script Execution          |
|       (/usr/local/bin/lxc_autoscale.py) |
+-----------------------------------------+
              |
              v
+-------------------------------------------+
|        Script Initialization               |
| - Load configuration from file             |
| - Setup logging                            |
| - Acquire lock to prevent multiple         |
|   instances                                |
| - Setup signal handlers for graceful       |
|   shutdown                                 |
+-------------------------------------------+
              |
              v
+-------------------------------------------+
|         Main Loop                         |
| - Runs indefinitely unless terminated     |
| - Steps:                                  |
|   1. Collect data about all containers    |
|   2. Prioritize containers based on       |
|      resource needs                       |
|   3. Adjust resources (CPU, Memory)       |
|      based on priorities and thresholds   |
|   4. Apply energy efficiency mode during  |
|      off-peak hours if enabled            |
|   5. Sleep for the configured             |
|      poll_interval                        |
+-------------------------------------------+
              |
              v
+-------------------------------------------+
|       Container Data Collection           |
| - Get list of all running containers      |
| - For each container:                     |
|   * Get CPU usage                         |
|   * Get Memory usage                      |
|   * Backup current settings               |
+-------------------------------------------+
              |
              v
+-------------------------------------------+
|        Resource Adjustment                |
| - For each container, based on priority:  |
|   * Increase/Decrease CPU cores if needed |
|   * Increase/Decrease Memory if needed    |
| - Apply energy-saving measures if enabled |
+-------------------------------------------+
              |
              v
+-------------------------------------------+
|        Notifications via Gotify           |
| - Send notifications for significant      |
|   actions taken (e.g., resource changes)  |
| - Only if Gotify URL and Token are        |
|   configured                              |
+-------------------------------------------+
              |
              v
+-------------------------------------------+
|         Shutdown Handling                 |
| - Release lock file                       |
| - Cleanup resources                       |
| - Ensure graceful shutdown                |
+-------------------------------------------+
```

## Disclaimer

> [!CAUTION]
> Initial version can be bugged, use at your own risk. I am not responsible for any damage on your lovely stuff by using this tool.

## Contributing

If you would like to contribute to the development of LXC AutoScale, feel free to submit a pull request or [open an issue](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/new/choose) on the [GitHub repository](https://github.com/fabriziosalmi/proxmox-lxc-autoscale).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
