# LXC AutoScale 

**LXC AutoScale** is a powerful resource management daemon designed to automatically adjust CPU and memory allocations, as well as clone LXC containers on Proxmox hosts based on current usage and predefined thresholds. It optimizes resource utilization, manages spikes in demand, and ensures that critical containers have the necessary resources. Additionally, it can (optionally) help save energy during off-peak hours. The autoscaling logic is highly customizable, offering a wide range of granular options to fit seamlessly into existing setups and meet specific requirements.

### _LXC AutoScale, with or without AI ?_

- **LXC AutoScale** is the ideal choice for new users. It's straightforward: install, run, and let it handle the rest by automatically scaling the resources of your Proxmox LXC containers. You can easily reconfigure it to fit your setup at any time or use it as a one-time solution when needed.

- **LXC AutoScale ML** is a more advanced option, designed for large automated environments or custom integrations. This solution comprises three services: LXC AutoScale API, LXC Monitor, and LXC AutoScale ML. It is intended for scenarios where more sophisticated, machine learning-driven autoscaling is required. The LXC Monitor logs resource usage data, which is then used by a machine learning model pipeline to train and suggest scaling decisions. These decisions can optionally be sent to the API for automated application. As with any ML-based system, the more data it gathers, the more accurate its predictions become. Users also have access to several customizable options to tailor the solution to their needs.

✅ Tested on `Proxmox 8.2.4`

## Features

- ⚙️ **Automatic Resource Scaling:** Dynamically adjust CPU and memory based on usage thresholds.
- ⚖️ **Automatic Horizontal Scaling:** Dynamically clone your LXC containers based on usage thresholds.
- 📊 **Tier Defined Thresholds:** Set specific thresholds for one or more LXC containers.
- 🛡️ **Host Resource Reservation:** Ensure that the host system remains stable and responsive.
- 🔒 **Ignore Scaling Option:** Ensure that one or more LXC containers are not affected by the scaling process.
- 🌱 **Energy Efficiency Mode:** Reduce resource allocation during off-peak hours to save energy.
- 🚦 **Container Prioritization:** Prioritize resource allocation based on resource type.
- 📦 **Automatic Backups:** Backup and rollback container configurations.
- 🔔 **Gotify Notifications:** Optional integration with Gotify for real-time notifications.
- 📈 **JSON metrics:** Collect all resources changes across your autoscaling fleet. 

## Installation

The easiest way to install (and update) LXC AutoScale is by using the following `curl` command:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

This script will:

1. Download the latest version of the LXC AutoScale Python script.
2. Download and install the systemd service file.
3. Set up the necessary directories and configuration files.
4. Ask the user to keep or overwrite the existing configuration, if present.
5. Back up any existing configuration files before updating them.
6. Enable and start the LXC AutoScale systemd service.

Now the service should be running. You can check it by executing `systemctl status lxc_autoscale.service`:

```
root@proxmox:~# systemctl status lxc_autoscale.service
● lxc_autoscale.service - LXC AutoScale Daemon
     Loaded: loaded (/etc/systemd/system/lxc_autoscale.service; enabled; preset: enabled)
     Active: active (running) since Sat 2024-08-17 00:42:04 CEST; 17h ago
       Docs: https://github.com/fabriziosalmi/proxmox-lxc-autoscale
   Main PID: 3973877 (python3)
      Tasks: 1 (limit: 154535)
     Memory: 13.3M
        CPU: 3h 50min 24.891s
     CGroup: /system.slice/lxc_autoscale.service
             └─3973877 /usr/bin/python3 /usr/local/bin/lxc_autoscale.py

Aug 17 17:45:30 dell python3[3973877]: 2024-08-17 17:45:30 - Starting resource allocation process...
Aug 17 17:45:33 dell python3[3973877]: 2024-08-17 17:45:33 - Container 102 is not running. Skipping adjustments.
Aug 17 17:45:33 dell python3[3973877]: 2024-08-17 17:45:33 - Container 100 is not running. Skipping adjustments.
Aug 17 17:45:50 dell python3[3973877]: 2024-08-17 17:45:50 - Initial resources before adjustments: 40 cores, 124750 MB m>
Aug 17 17:45:50 dell python3[3973877]: 2024-08-17 17:45:50 - Final resources after adjustments: 40 cores, 124750 MB memo>
Aug 17 17:45:50 dell python3[3973877]: 2024-08-17 17:45:50 - Resource allocation process completed. Next run in 300 seco>
lines 1-21/21 (END)
```

### Configuration

Jump to the [Configuration section](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/README.md#configuration) to understand how to customize your LXC AutoScale experience.

---

## ✨ Proxmox + AutoScale + AI

_In the meanwhile I added to the project everything needed to make scaling decisions improved by a machine learning model._

To make this happen I released [a simple HTTP API interface](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/tree/main/api) to Proxmox commands, an [LXC monitor](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/tree/main/monitor) to get LXC monitoring data and [a lightweight ML model](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/tree/main/ai) to parse monitoring logs and take decisions. 

> You are welcome to play, improve and get fun togheter.

### API
> [!TIP]
> If You want to have **full control**, **precise thresholds** and consider the **integration with your existing setup** please check the **[LXC AutoScale API](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/api/README.md)**. LXC AutoScale API is an API HTTP interface to perform all common scaling operations with just few, simple, `curl` requests.

**Install AutoScale API**
```
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/api/install.sh | bash
```

### Monitor
In the `monitor` folder you will find all files needed to run a lightweight LXC monitor service to generate the needed data to train the machine learning model.

### AutoScale ML
In the `ai` folder you will find all files needed to run the machine learning model. It will take decision against using the AutoScale API. The model is updated every cycle and  can be run in dry-run mode (--dry-run) to check its decisions before to change real-world resources.

I will add accurate documentation in then next days.

## Configuration

The **LXC AutoScale** script manages the dynamic scaling of LXC containers and/or CPU and memory resources for LXC containers based on their resource usage. The configuration file at `/etc/lxc_autoscale/lxc_autoscale.yaml` defines thresholds, settings, and behaviors for the daemon. Below is the updated documentation reflecting the latest integrations and features.

### Configuration File
> [!IMPORTANT]  
> The main configuration file is located at `/etc/lxc_autoscale/lxc_autoscale.yaml`. This file defines various thresholds and settings for the daemon. If you need to customize the behavior of the daemon, you can edit this file.

### Configuration Backup
> [!NOTE]  
> Before any update, the installation script automatically backs up the existing configuration file to `/etc/lxc_autoscale/lxc_autoscale.yaml.YYYYMMDD-HHMMSS.backup`. It will migrate your existing `/etc/lxc_autoscale/lxc_autoscale.conf` configuration into the new YAML format, if any.

### Default Configuration Parameters

```yaml
DEFAULT:
  poll_interval: 300
  cpu_upper_threshold: 80
  cpu_lower_threshold: 20
  memory_upper_threshold: 80
  memory_lower_threshold: 20
  core_min_increment: 1
  core_max_increment: 4
  memory_min_increment: 512
  min_cores: 1
  max_cores: 8
  min_memory: 512
  min_decrease_chunk: 512
  reserve_cpu_percent: 10
  reserve_memory_mb: 2048
  log_file: /var/log/lxc_autoscale.log
  lock_file: /var/lock/lxc_autoscale.lock
  backup_dir: /var/lib/lxc_autoscale/backups
  off_peak_start: 22
  off_peak_end: 6
  energy_mode: False
  gotify_url: ''
  gotify_token: ''
  ignore_lxc: []
  behaviour: normal
```

The configuration file contains settings that control how the script manages scaling for CPU and memory resources. Below are the default parameters and their descriptions:

| Parameter                 | Default Value         | Description                                                                                                                                                           |
|---------------------------|-----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **poll_interval**          | 300                   | The interval, in seconds, at which the script polls container metrics to determine if scaling actions are required.                                                   |
| **cpu_upper_threshold**    | 80                    | The CPU usage percentage that triggers scaling up (adding more CPU cores) for a container.                                                                            |
| **cpu_lower_threshold**    | 20                    | The CPU usage percentage that triggers scaling down (reducing CPU cores) for a container.                                                                             |
| **memory_upper_threshold** | 80                    | The memory usage percentage that triggers scaling up (increasing memory) for a container.                                                                             |
| **memory_lower_threshold** | 20                    | The memory usage percentage that triggers scaling down (decreasing memory) for a container.                                                                           |
| **core_min_increment**     | 1                     | The minimum number of CPU cores to add during a scaling-up operation.                                                                                                 |
| **core_max_increment**     | 4                     | The maximum number of CPU cores to add during a single scaling-up operation.                                                                                          |
| **memory_min_increment**   | 512                   | The minimum amount of memory (in MB) to add during a scaling-up operation.                                                                                            |
| **min_cores**              | 1                     | The minimum number of CPU cores any container should have.                                                                                                            |
| **max_cores**              | 8                     | The maximum number of CPU cores any container can have.                                                                                                               |
| **min_memory**             | 512                   | The minimum amount of memory (in MB) that any container should have.                                                                                                  |
| **min_decrease_chunk**     | 512                   | The minimum chunk size (in MB) by which memory can be reduced during a scaling-down operation.                                                                        |
| **reserve_cpu_percent**    | 10                    | The percentage of the host's total CPU resources reserved and not allocated to containers.                                                                            |
| **reserve_memory_mb**      | 2048                  | The amount of memory (in MB) reserved on the host and not allocated to containers.                                                                                    |
| **log_file**               | `/var/log/lxc_autoscale.log` | The file path where the script writes its log output.                                                                                                                 |
| **lock_file**              | `/var/lock/lxc_autoscale.lock` | The file path for the lock file used by the script to prevent multiple instances from running simultaneously.                                                         |
| **backup_dir**             | `/var/lib/lxc_autoscale/backups` | The directory where backups of container configurations are stored before scaling actions are taken.                                                                  |
| **off_peak_start**         | 22                    | The hour (in 24-hour format) at which off-peak energy-saving mode begins.                                                                                             |
| **off_peak_end**           | 6                     | The hour (in 24-hour format) at which off-peak energy-saving mode ends.                                                                                               |
| **energy_mode**            | False                 | A boolean setting that enables or disables energy-saving mode during off-peak hours.                                                                                  |
| **gotify_url**             | ''                    | The URL for a Gotify server used for sending notifications about scaling actions or other important events.                                                           |
| **gotify_token**           | ''                    | The authentication token for accessing the Gotify server.                                                                                                             |
| **ignore_lxc**             | []                    | Add one or more LXC containers to the ignore list. Containers in this list are not affected by the autoscaling process.                                               |
| **behaviour**              | `normal`              | The behavior acts as a multiplier for autoscaling resources thresholds. Options are `normal`, `conservative`, or `aggressive`.                                        |

### Tiers (Optional)

You can assign LXC containers to different tiers for specific threshold assignments. Each tier must be prefixed with `TIER_` (e.g., `TIER_TEST`). Adjust the tier options in the `/etc/lxc_autoscale/lxc_autoscale.yaml` configuration file and restart the service by running `systemctl restart lxc_autoscale`.

```yaml
TIER_TEST:
  cpu_upper_threshold: 90
  cpu_lower_threshold: 10
  memory_upper_threshold: 90
  memory_lower_threshold: 10
  min_cores: 2
  max_cores: 12
  min_memory: 1024
  lxc_containers: 
  - 100
  - 101
```

### Horizontal Scaling Group  (optional)

The script also supports horizontal scaling where containers are cloned based on specific criteria.

> [!WARNING]  
> This feature is experimental and support scale-out only. If You really need to scale-in please check the [LXC AutoScale API](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/api/README.md).

The horizontal scaling group is defined as follows:

#### Example Configuration:

```yaml
HORIZONTAL_SCALING_GROUP_1:
  base_snapshot_name: "101"    
  min_instances: 2
  max_instances: 5
  starting_clone_id: 99000  # Starting ID for clones
  clone_network_type: "static"  # or "dhcp"
  static_ip_range: ["192.168.100.195", "192.168.100.200"]
  horiz_cpu_upper_threshold: 95  # Upper CPU threshold for triggering horizontal scaling
  horiz_memory_upper_threshold: 95  # Upper Memory threshold for triggering horizontal scaling
  group_tag: "horiz_scaling_group_1"  # Optional tag for identifying clones of this group
  lxc_containers: 
  - 101
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
> [!IMPORTANT]
> Logs for the LXC AutoScale daemon are stored in `/var/log/lxc_autoscale.log` and `/var/log/lxc_autoscale.json` (resources changes only). You can check and monitor log files to observe the daemon's operations and troubleshoot any issues or to implement additional scaling logic.

```
root@proxmox:~# tail /var/log/lxc_autoscale.log 
2024-08-14 22:04:27 - INFO - Starting resource allocation process...
2024-08-14 22:04:45 - INFO - Initial resources before adjustments: 40 cores, 124750 MB memory
2024-08-14 22:04:45 - INFO - Decreasing cores for container 114 by 2...
2024-08-14 22:04:47 - INFO - Decreasing cores for container 102 by 2...
2024-08-14 22:04:48 - INFO - Decreasing memory for container 102 by 6656MB...
2024-08-14 22:04:50 - INFO - Final resources after adjustments: 44 cores, 131406 MB memory
2024-08-14 22:04:50 - INFO - Resource allocation process completed. Next run in 300 seconds.
```

> [!TIP]
> You can easily check JSON logs by installing and using `jq` like this:

```
root@proxmox:~# cat /var/log/lxc_autoscale.json | jq .
{
  "timestamp": "2024-08-14 22:04:45",
  "proxmox_host": "proxmox",
  "container_id": "114",
  "action": "Decrease Cores",
  "change": "2"
}
{
  "timestamp": "2024-08-14 22:04:47",
  "proxmox_host": "proxmox",
  "container_id": "102",
  "action": "Decrease Cores",
  "change": "2"
}
{
  "timestamp": "2024-08-14 22:04:48",
  "proxmox_host": "proxmox",
  "container_id": "102",
  "action": "Decrease Memory",
  "change": "6656MB"
}
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

## Disclaimer

> [!CAUTION]
> Initial version can be bugged, use at your own risk. I am not responsible for any damage to your lovely stuff by using this tool.

## Contributing

If you would like to contribute to the development of LXC AutoScale, feel free to submit a pull request or [open an issue](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/new/choose) on the [GitHub repository](https://github.com/fabriziosalmi/proxmox-lxc-autoscale).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
