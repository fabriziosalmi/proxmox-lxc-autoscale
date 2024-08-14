
# Proxmox LXC AutoScale

> [!CAUTION]
> Initial version can be bugged, use at your own risk. I am not responsible for any damage on your lovely stuff by using this tool.

## Overview

LXC AutoScale is a resource management daemon designed to automatically adjust the CPU and memory allocations of LXC containers based on their current usage and pre-defined thresholds. It helps in optimizing resource utilization, ensuring that critical containers have the necessary resources while also saving energy during off-peak hours.

## Features

- **Automatic Resource Scaling:** Dynamically adjust CPU and memory based on usage thresholds.
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

The default configuration file contains the following sections and settings:

```ini
[DEFAULT]
poll_interval = 300             # Polling interval in seconds (how often to check and adjust container resources).
cpu_upper_threshold = 80         # Upper CPU usage threshold (percentage) before scaling up.
cpu_lower_threshold = 20         # Lower CPU usage threshold (percentage) before scaling down.
memory_upper_threshold = 80      # Upper memory usage threshold (percentage) before scaling up.
memory_lower_threshold = 20      # Lower memory usage threshold (percentage) before scaling down.
core_min_increment = 1           # Minimum number of CPU cores to add when scaling up.
core_max_increment = 4           # Maximum number of CPU cores to add when scaling up.
memory_min_increment = 512       # Minimum amount of memory (MB) to add when scaling up.
min_cores = 1                    # Minimum number of CPU cores per container.
max_cores = 8                    # Maximum number of CPU cores per container.
min_memory = 512                 # Minimum memory (MB) per container.
min_decrease_chunk = 512         # Minimum chunk size (MB) to reduce memory when scaling down.
reserve_cpu_percent = 10         # Reserved CPU percentage for the host (not allocated to containers).
reserve_memory_mb = 2048         # Reserved memory (MB) for the host (not allocated to containers).
reserve_storage_mb = 10240       # Reserved storage (MB) for the host (not allocated to containers).
log_file = /var/log/lxc_autoscale.log    # Path to the log file for the script's output.
lock_file = /var/lock/lxc_autoscale.lock # Path to the lock file to prevent multiple instances from running.
backup_dir = /var/lib/lxc_autoscale/backups  # Directory where container configuration backups are stored.
off_peak_start = 22              # Start hour for off-peak energy-saving mode (24-hour format).
off_peak_end = 6                 # End hour for off-peak energy-saving mode (24-hour format).
energy_mode = False              # Enable or disable energy-saving mode during off-peak hours.
gotify_url =                     # URL for Gotify server (used for notifications).
gotify_token =                   # Authentication token for Gotify server.

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

## Contributing

If you would like to contribute to the development of LXC AutoScale, feel free to submit a pull request or open an issue on the [GitHub repository](https://github.com/fabriziosalmi/proxmox-lxc-autoscale).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
