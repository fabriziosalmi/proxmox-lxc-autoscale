
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

- **poll_interval** `300`  
 <sub> The interval, in seconds, at which the script polls container metrics to determine if scaling actions are required. A shorter interval results in more frequent checks and potential adjustments. </sub>

- **cpu_upper_threshold** `80`  
  <sub> The upper CPU usage threshold, expressed as a percentage, that triggers scaling up (adding more CPU cores) for a container. When a container's CPU usage exceeds this threshold, additional CPU cores may be allocated. </sub>

- **cpu_lower_threshold** `20`  
  <sub> The lower CPU usage threshold, expressed as a percentage, that triggers scaling down (reducing CPU cores) for a container. When a container's CPU usage falls below this threshold, CPU cores may be deallocated to save resources. </sub>

- **memory_upper_threshold** `80`  
  <sub> The upper memory usage threshold, expressed as a percentage, that triggers scaling up (increasing memory) for a container. When a container's memory usage exceeds this threshold, more memory may be allocated. </sub>

- **memory_lower_threshold** `20`  
  <sub> The lower memory usage threshold, expressed as a percentage, that triggers scaling down (decreasing memory) for a container. When a container's memory usage falls below this threshold, memory may be reduced. </sub>

- **core_min_increment** `1`  
  <sub> The minimum number of CPU cores to add to a container during a scaling up operation. This value ensures that scaling adjustments are not too granular, which could lead to excessive adjustments. </sub>

- **core_max_increment** `4`  
  <sub> The maximum number of CPU cores that can be added to a container during a single scaling up operation. This prevents the script from allocating too many cores at once, which could negatively impact other containers or the host. </sub>

- **memory_min_increment** `512`  
  <sub> The minimum amount of memory, in MB, to add to a container during a scaling up operation. This value ensures that scaling adjustments are significant enough to handle increased workloads. </sub>

- **min_cores** `1`  
  <sub> The minimum number of CPU cores that any container should have. This prevents the script from reducing the CPU allocation below a functional minimum. </sub>

- **max_cores** `8`  
  <sub> The maximum number of CPU cores that any container can have. This cap prevents any single container from monopolizing the host's CPU resources. </sub>

- **min_memory** `512`  
  <sub> The minimum amount of memory, in MB, that any container should have. This ensures that no container is allocated too little memory to function properly. </sub>

- **min_decrease_chunk** `512`  
  <sub> The minimum chunk size, in MB, by which memory can be reduced during a scaling down operation. This prevents the script from making overly granular and frequent reductions in memory, which could destabilize the container. </sub>

- **reserve_cpu_percent** `10`  
  <sub> The percentage of the host's total CPU resources that should be reserved and not allocated to containers. This reserved capacity ensures that the host always has sufficient CPU resources for its own operations and for emergency situations. </sub>

- **reserve_memory_mb** `2048`  
  <sub> The amount of memory, in MB, that should be reserved on the host and not allocated to containers. This reserved memory ensures that the host has enough memory for its own operations and for handling unexpected loads. </sub>

- **log_file** `/var/log/lxc_autoscale.log`  
  <sub> The file path where the script writes its log output. This log contains information about the script's operations, including any scaling actions taken. </sub>

- **lock_file** `/var/lock/lxc_autoscale.lock`  
  <sub> The file path for the lock file used by the script to prevent multiple instances from running simultaneously. This ensures that only one instance of the script manages resources at any given time. </sub> 

- **backup_dir** `/var/lib/lxc_autoscale/backups`  
  <sub> The directory where backups of container configurations are stored before any scaling actions are taken. This allows for rollback in case of an issue with the scaling process. </sub>

- **off_peak_start** `22`  
  <sub> The hour (in 24-hour format) at which off-peak energy-saving mode begins. During off-peak hours, the script may reduce resources to save energy if `energy_mode` is enabled. </sub>

- **off_peak_end** `6`  
  <sub> The hour (in 24-hour format) at which off-peak energy-saving mode ends. After this time, containers may be scaled back up to handle peak load. </sub>

- **energy_mode** `False`  
  <sub> A boolean setting that enables or disables energy-saving mode during off-peak hours. When enabled, this mode reduces CPU and memory resources allocated to containers during off-peak hours to save energy. </sub>

- **gotify_url** *Example:* `http://gotify.example.com`  
  <sub> The URL for a Gotify server used for sending notifications about scaling actions or other important events. If left blank, notifications will not be sent. </sub>

- **gotify_token** *Example:* `abcdef1234567890`  
  <sub> The authentication token for accessing the Gotify server. This token is required if `gotify_url` is set and notifications are to be sent. </sub>


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

## Uninstallation

> [!TIP]
> The easiest way to uninstall LXC AutoScale is by using the following `curl` command:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/uninstall.sh | bash
```

If you wish to remove the LXC AutoScale daemon from your system manually, you can disable and stop the service, then delete the associated files:

```bash
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
