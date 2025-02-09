# LXC AutoScale Documentation

**LXC AutoScale** is a dynamic scaling solution designed to automatically adjust CPU and memory resources for LXC containers based on real-time usage metrics. This service ensures that your containers always have the appropriate amount of resources allocated, optimizing performance and efficiency in both homelab and self-hosting environments.

## Summary

- **[Introduction](#lxc-autoscale)**: Overview of LXC AutoScale's functionality.
- **[Docker](#docker)**: Setup and run LXC AutoScale via Docker and Docker Compose.
- **[Installation (no Docker)](#installation)**: One-click install LXC AutoScale on your Proxmox server.
- **[Configuration](#configuration)**: Detailed guide to setting up and customizing LXC AutoScale.
  - [Configuration File Location](#configuration-file-location)
  - [Important Parameters](#important-parameters)
  - [Tiers (Optional)](#tiers-optional)
  - [Horizontal Scaling Group (Optional)](#horizontal-scaling-group-optional)
- **[Service Management](#service-management)**: Commands to start, stop, and manage the LXC AutoScale service.
- **[Logging](#logging)**: Instructions for accessing and interpreting LXC AutoScale logs.
- **[Notifications](#notifications)**: How to configure the notifications for endpoints like e-mail, Gotify or Uptime Kuma.
- **[Uninstallation](#uninstallation)**: Steps to remove LXC AutoScale from your system.
- **[Use Cases](#use-cases)**: Examples of how LXC AutoScale can be used in homelab and self-hosting environments.
- **[Examples](examples/README.md)**: TIER defined snippets for 40 popular self-hosted applications.
- **[Best Practices and Tips](#best-practices-and-tips)**: Recommendations for optimal configuration and usage.

---

## LXC AutoScale

**LXC AutoScale** is a powerful tool that automates the dynamic scaling of CPU and memory resources for LXC containers. Designed with both performance optimization and resource efficiency in mind, it continuously monitors container resource usage and adjusts allocations based on pre-configured thresholds. This ensures that each container has just the right amount of resources, minimizing waste and maximizing performance. LXC AutoScale can operate both locally or by remotely connecting via SSH to your Proxmox hosts.

---

## Docker

### Step 1: Clone the Repository

```bash
git clone https://github.com/fabriziosalmi/proxmox-lxc-autoscale.git
```

### Step 2: Navigate to the Application Directory

```bash
cd proxmox-lxc-autoscale/lxc_autoscale
```

### Step 3: Build the Docker Image

```bash
docker build -t lxc-autoscale .
```

### Step 4: Edit the YAML Configuration

Modify the YAML configuration file (e.g., `lxc_autoscale.yaml`) with the Proxmox hosts SSH parameters and the required `use_remote_proxmox` option to make the app execute commands to remote hosts:

```
  use_remote_proxmox: true
  ssh_user: "your-ssh-username"
  ssh_password: "your-ssh-password"
  proxmox_host: "your-proxmox-host-ip-or-hostname"
```
  
### Step 5: Run the Docker Container

- **Using the Default Configuration:**

```bash
docker run -d --name lxc_autoscale lxc-autoscale
```

### Step 6: Check Docker Logs

```bash
docker logs lxc_autoscale
```


---

## Installation

Getting started with LXC AutoScale is quick and simple. The easiest way to install (or update) the service is by using the following `curl` command:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

Once installed, the service should be up and running. You can verify this by executing:

```bash
systemctl status lxc_autoscale.service
```

If the conditions set in the configuration are met, you will quickly observe scaling operations in action:

```
root@proxmox:~# systemctl status lxc_autoscale.service
● lxc_autoscale.service - LXC AutoScale Daemon
     Loaded: loaded (/etc/systemd/system/lxc_autoscale.service; enabled; preset: enabled)
     Active: active (running) since Mon 2024-08-19 01:38:07 CEST; 7s ago
       Docs: https://github.com/fabriziosalmi/proxmox-lxc-autoscale
   Main PID: 40462 (python3)
      Tasks: 1 (limit: 18849)
     Memory: 9.1M
        CPU: 5.766s
     CGroup: /system.slice/lxc_autoscale.service
             └─40462 /usr/bin/python3 /usr/local/bin/lxc_autoscale/lxc_autoscale.py

Aug 19 01:38:07 proxmox systemd[1]: Started lxc_autoscale.service - LXC AutoScale Daemon.
Aug 19 01:38:07 proxmox python3[40462]: 2024-08-19 01:38:07 - Starting resource allocation process...
Aug 19 01:38:09 proxmox python3[40462]: 2024-08-19 01:38:09 - Container 1006 is not running. Skipping adjustments.
Aug 19 01:38:12 proxmox python3[40462]: 2024-08-19 01:38:12 - Initial resources before adjustments: 2 cores, 11678 MB>
Aug 19 01:38:12 proxmox python3[40462]: 2024-08-19 01:38:12 - Decreasing cores for container 104 by 2...
Aug 19 01:38:13 proxmox python3[40462]: 2024-08-19 01:38:13 - Final resources after adjustments: 4 cores, 11678 MB me>
Aug 19 01:38:13 proxmox python3[40462]: 2024-08-19 01:38:13 - Resource allocation process completed. Next run in 300
```

---

## Configuration

The core of **LXC AutoScale** lies in its configuration file, where you can fine-tune the behavior of the scaling daemon to suit your specific needs. This section provides an in-depth look at how to configure LXC AutoScale, including a breakdown of key parameters, optional tiers, and horizontal scaling.

### Configuration File Location

The main configuration file for LXC AutoScale is located at:

```bash
/etc/lxc_autoscale/lxc_autoscale.yaml
```

This file contains all the settings that control how the daemon manages resource scaling. Before making any changes, it’s recommended to back up the existing configuration file to avoid losing your settings:

```bash
cp /etc/lxc_autoscale/lxc_autoscale.yaml /etc/lxc_autoscale/lxc_autoscale.yaml.backup
```

### Important Parameters

The configuration file uses a YAML format to define various settings. Below is a detailed explanation of the default parameters and how they influence the scaling behavior.

```yaml
# Default configuration values
DEFAULTS:
  # Log file path
  log_file: /var/log/lxc_autoscale.log
  # Lock file path
  lock_file: /var/lock/lxc_autoscale.lock
  # Backup directory path
  backup_dir: /var/lib/lxc_autoscale/backups
  # Percentage of CPU cores to reserve (e.g., 10%)
  reserve_cpu_percent: 10
  # Amount of memory (in MB) to reserve (e.g., 2048 MB)
  reserve_memory_mb: 2048
  # Start hour for off-peak energy-saving mode (e.g., 10 PM)
  off_peak_start: 22
  # End hour for off-peak energy-saving mode (e.g., 6 AM)
  off_peak_end: 6
  # Behaviour mode (e.g., 'normal', 'conservative', 'aggressive')
  behaviour: normal
  # Default CPU upper threshold (%)
  cpu_upper_threshold: 80
  # Default CPU lower threshold (%)
  cpu_lower_threshold: 20
  # Default Memory upper threshold (%)
  memory_upper_threshold: 70
  # Default Memory lower threshold (%)
  memory_lower_threshold: 20
  # Default minimum number of CPU cores
  min_cores: 1
  # Default maximum number of CPU cores
  max_cores: 4
  # Default minimum memory (MB)
  min_memory: 256
  # Default core increment
  core_min_increment: 1
  # Default core max increment: 2
  core_max_increment: 2
  # Default memory increment (MB)
  memory_min_increment: 256
  # Default memory decrement (MB)
  min_decrease_chunk: 256
  ignore_lxc: 
    - "104"  # Update to string format for consistency
  
# Tier configurations
TIER_webservers:
  lxc_containers:
    - "102"  # Update to string format
  cpu_upper_threshold: 70
  cpu_lower_threshold: 20
  memory_upper_threshold: 80
  memory_lower_threshold: 20
  min_cores: 1
  max_cores: 4
  min_memory: 4096
  core_min_increment: 1
  core_max_increment: 2
  memory_min_increment: 1024
  min_decrease_chunk: 1024

TIER_other:
  lxc_containers:
    - "103"  # Update to string format
  cpu_upper_threshold: 60
  cpu_lower_threshold: 20
  memory_upper_threshold: 50
  memory_lower_threshold: 20
  min_cores: 1
  max_cores: 2
  min_memory: 256
  core_min_increment: 1
  core_max_increment: 1
  memory_min_increment: 128
  min_decrease_chunk: 64
```

#### Poll Interval (`poll_interval`)
Sets the frequency (in seconds) at which LXC AutoScale polls container metrics.
> [!NOTE]
> A shorter interval means more frequent checks, which can lead to quicker scaling responses but may increase the load on the host. For high-traffic environments, a lower poll interval (e.g., 60 seconds) may be beneficial, whereas for stable environments, the default of 300 seconds may suffice.

#### CPU Thresholds (`cpu_upper_threshold` and `cpu_lower_threshold`)
Define the CPU usage percentages that trigger scaling actions.
> [!NOTE]
> If a container’s CPU usage exceeds `cpu_upper_threshold`, additional CPU cores are allocated. If usage falls below `cpu_lower_threshold`, cores are deallocated. Adjust these thresholds based on the performance requirements of your containers. For instance, a CPU-intensive application might require a lower `cpu_upper_threshold` to ensure it has enough resources during peak loads.

#### Memory Thresholds (`memory_upper_threshold` and `memory_lower_threshold`)
Control when memory scaling actions are triggered.
> [!NOTE]
> These settings help prevent out-of-memory (OOM) conditions by scaling up memory when usage is high and scaling down when it’s low. Memory-intensive applications, such as databases, may benefit from a higher `memory_upper_threshold` to avoid performance bottlenecks.

#### Core and Memory Increments (`core_min_increment`, `core_max_increment`, `memory_min_increment`)
Define the minimum and maximum increments for scaling CPU cores and memory.
> [!NOTE]
> Larger increments lead to more significant changes in resource allocation, which can be useful in environments where workloads vary dramatically. Smaller increments allow for finer control, which is ideal for environments where workloads change gradually.

#### Resource Reservation (`reserve_cpu_percent` and `reserve_memory_mb`)
Reserve a portion of the host’s CPU and memory resources.
> [!IMPORTANT]
> This reservation ensures that the host remains responsive even under heavy container loads. It’s particularly important in homelab setups where the host may also be running other critical services.

#### Logging (`log_file`)
Specifies the file path for logging LXC AutoScale’s actions.
> [!WARNING]
> Regularly reviewing these logs helps you understand how the daemon is performing and can aid in troubleshooting any issues.

#### Energy Mode (`energy_mode`)
Activates a mode that reduces resource allocation during off-peak hours.
> [!TIP]
> Useful for saving energy in environments where container usage is predictable, such as a homelab that primarily operates during specific hours.

### Tiers (Optional)

Tiers allow you to apply different scaling rules to groups of containers, enabling more granular control based on the specific needs of each service.

#### Example Configuration:

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

- **Usage Scenario**: You might use a tier like `TIER_TEST` for non-critical containers or testing environments. This tier allows these containers to use more resources when needed but also scales them down aggressively to free up resources for other critical containers.

> [!TIP]
> For more configuration examples check the [TIER collection](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/examples/README.md) with 40   snippets customized to fit minimal and recommended requirements for the most popular self-hosted applications.

### Horizontal Scaling Group (Optional)

Horizontal scaling allows LXC AutoScale to clone containers based on resource demand. This feature is still experimental and is designed for environments that require scaling out services rather than just scaling up resources.

#### Example Configuration:

```yaml
HORIZONTAL_SCALING_GROUP_1:
  base_snapshot_name: "101"
  min_instances: 2
  max_instances: 5
  starting_clone_id: 99000
  clone_network_type: "static"                               # or "dhcp", in that case better to set static_ip_range: []
  static_ip_range: ["192.168.100.195", "192.168.100.200"]    # if you enabled dhcp for clones set static_ip_range: []
  horiz_cpu_upper_threshold: 95
  horiz_memory_upper_threshold: 95
  group_tag: "horiz_scaling_group_1"
  lxc_containers: 
  - 101
```

- **Usage Scenario**: This feature is ideal for homelab users running a web service that experiences fluctuating traffic. When traffic spikes, LXC AutoScale can clone additional instances of the service, ensuring availability without manual intervention.

---

## Service Management

Managing the LXC AutoScale daemon is straightforward with systemd. Here’s how to control the service:

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

To ensure that LXC AutoScale starts automatically at boot, use:

```bash
systemctl enable lxc_autoscale.service
```

This command ensures that the daemon is always running, providing continuous scaling based on container needs.

---

## Logging

LXC AutoScale logs its actions to help you monitor its behavior and troubleshoot any issues.

### Log Files

- **Main Log**: `/var/log/lxc_autoscale.log`
- **JSON Log**: `/var/log/lxc_autoscale.json`

### Monitoring Logs

To view the logs in real-time:

```bash
tail -f /var/log/lxc_autoscale.log
```

For the JSON log install and use `jq` for better readability:

```bash
apt install jq -y
cat /var/log/lxc_autoscale.json | jq .
```

### Log Interpretation

Understanding the logs can help you fine-tune LXC AutoScale’s configuration. For example, if you notice frequent scaling actions, you might need to adjust the thresholds or increments to reduce the load on the host.


### Notifications

Notifications on scaling events can be sent to one or more endpoints like E-Mail, Gotify and Uptime Kuma (push webhook). Change options accordingly with your setup in the `/etc/lxc_autoscale/lxc_autoscale.yaml` configuration file:

```
  gotify_url: 'http://gotify-host'
  gotify_token: 'XXXXXXXXXX'
  smtp_server: 'live.smtp.mailtrap.io'
  smtp_port: 587
  smtp_username: 'api'
  smtp_password: 'XXXXXXXXXXXXXXXXXXXXXX'
  smtp_from: 'mailtrap@yourdomain.com'
  smtp_to:
    - 'fabrizio.salmi@gmail.com'
  uptime_kuma_webhook_url: 'http://uptime-kuma-host:3001/api/push/XXXXXXXXX?status=up&msg=OK&ping='
```


## Uninstallation

If you need to remove LXC AutoScale from your system, the process is straightforward.

### Automated Uninstallation

Use the following `curl` command to automatically uninstall LXC AutoScale:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/uninstall.sh | bash
```

### Manual Uninstallation

To manually remove LXC AutoScale, follow these steps:

```bash
# Disable and stop service
systemctl disable lxc_autoscale.service
systemctl stop lxc_autoscale.service

# Use this to force kill the application if needed:
# kill -9 $(ps aux | grep lxc_autoscale | grep -v grep | awk '{print $2}')

# Make backup of configuration file if needed
# cp -rp /etc/lxc_autoscale/lxc_autoscale.yaml /etc/lxc_autoscale.yaml.backup

# Remove files
rm -f /etc/systemd/system/lxc_autoscale.service
rm -rf /usr/local/bin/lxc_autoscale/
rm -rf /etc/lxc_autoscale/
rm -rf /var/lib/lxc_autoscale/
rm -f /var/log/lxc_autoscale.log
rm -f /var/log/lxc_autoscale.json

# Reload systemd
systemctl daemon-reload
```

This will completely remove the service and all associated files from your system.

---

## Use Cases

### Scenario 1: Media Server

**Use Case**: You’re running a self-hosted media server using Plex or Jellyfin on your homelab. During evenings and weekends, when your family is likely to be streaming content, LXC AutoScale can automatically allocate more CPU cores and memory to your media server container, ensuring smooth playback. During the day, when usage is low, it scales down resources to save energy.

**Configuration Tip**: Set the `cpu_upper_threshold` and `memory_upper_threshold` to slightly lower values (e.g., 75%) to ensure quick scaling during peak times.

### Scenario 2: Development Environment

**Use Case**: You have a homelab where you run multiple development environments in LXC containers. Each environment has different resource needs depending on the projects you’re working on. LXC AutoScale can dynamically adjust resources based on the current workload, allowing you to focus on coding rather than managing resources.

**Configuration Tip**: Create tiers for different projects, assigning higher thresholds to more demanding projects to ensure they get the resources they need without affecting other containers.

### Scenario 3: Personal Web Hosting

**Use Case**: You’re self-hosting a personal website or blog. Occasionally, your site experiences traffic spikes, such as when a blog post gains popularity. LXC AutoScale can clone your web server container to handle the increased load, ensuring that your site remains responsive without manual intervention.

**Configuration Tip**: Enable horizontal scaling with a conservative `horiz_cpu_upper_threshold` to ensure that clones are only created when absolutely necessary, saving resources for other tasks.

---

## Best Practices and Tips

### 1. Regularly Review and Adjust Configuration
As your usage patterns change, revisit the LXC AutoScale configuration to ensure it remains optimal. For example, if you add new services or containers, you may need to adjust thresholds or add new tiers.

### 2. Monitor Logs Frequently
Use the log files to monitor how LXC AutoScale is managing resources. Frequent scaling actions may indicate that your thresholds are too tight, leading to unnecessary scaling.

### 3. Balance Performance and Resource Efficiency
Finding the right balance between performance and resource efficiency is key. For most homelab users, setting slightly conservative thresholds helps avoid over-allocation while still maintaining good performance.

### 4. Test Configuration Changes in a Controlled Environment
Before applying significant changes to the configuration in a production environment, test them in a controlled setting to understand their impact.

### 5. Use Tiers to Group Similar Containers
If you have multiple containers with similar resource needs, grouping them into tiers can simplify management and ensure consistent scaling behavior.
