# LXC AutoScale Documentation

**LXC AutoScale** is a resource management daemon that automatically adjusts CPU and memory for LXC containers based on real-time usage metrics. It can operate locally on the Proxmox host or connect remotely via SSH.

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
- **[Notifications](#notifications)**: How to configure notifications for endpoints like email, Gotify, or Uptime Kuma.
- **[Uninstallation](#uninstallation)**: Steps to remove LXC AutoScale from your system.
- **[Troubleshooting](#troubleshooting)**: Common issues and their solutions.
- **[Use Cases](#use-cases)**: Examples of how LXC AutoScale can be used in homelab and self-hosting environments.
- **[Examples](examples/README.md)**: TIER defined snippets for 40 popular self-hosted applications.
- **[Best Practices and Tips](#best-practices-and-tips)**: Recommendations for optimal configuration and usage.

---

## LXC AutoScale

**LXC AutoScale** monitors container resource usage and adjusts CPU and memory allocations based on pre-configured thresholds. It can run locally on the Proxmox host or connect remotely via SSH.

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

### Step 3: Configure Environment Variables (Optional)

If you're using environment variables instead of YAML configuration, copy the example file and configure it:

```bash
cp .env.example .env
nano .env  # Edit with your settings
```

> [!WARNING]
> Never commit `.env` files containing passwords or sensitive information to version control.

### Step 4: Build the Docker Image

```bash
docker build -t lxc-autoscale .
```

### Step 5: Edit the YAML Configuration

Modify the YAML configuration file (`lxc_autoscale.yaml`) with the Proxmox host SSH parameters and the required `use_remote_proxmox` option to make the application execute commands on remote hosts:

```yaml
use_remote_proxmox: true
ssh_user: "your-ssh-username"
ssh_password: "your-ssh-password"
proxmox_host: "your-proxmox-host-ip-or-hostname"
ssh_port: 22
```

> [!TIP]
> For better security, use SSH keys instead of passwords by setting `ssh_key_path` and leaving `ssh_password` empty.
  
### Step 6: Run the Docker Container

**Using the Default Configuration:**

```bash
docker run -d --name lxc_autoscale lxc-autoscale
```

**Using a Custom Configuration File:**

```bash
docker run -d --name lxc_autoscale \
  -v /path/to/your/lxc_autoscale.yaml:/app/lxc_autoscale.yaml \
  lxc-autoscale
```

### Step 7: Check Docker Logs

```bash
docker logs lxc_autoscale
```


---

## Installation

The easiest way to install (or update) the service:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

Verify the service is running:

```bash
systemctl status lxc_autoscale.service
```

Example output when the service is running and performing scaling:

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

The core of **LXC AutoScale** is the configuration file, which controls scaling behaviour. This section explains the key parameters.

### Configuration File Location

The main configuration file is located at:

```bash
/etc/lxc_autoscale/lxc_autoscale.yaml
```

Back up the file before making changes:

```bash
cp /etc/lxc_autoscale/lxc_autoscale.yaml /etc/lxc_autoscale/lxc_autoscale.yaml.backup
```

### Important Parameters

The configuration file uses YAML format. Below is an explanation of the default parameters.

```yaml
# Default configuration values
DEFAULT:
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
How often (in seconds) the daemon polls container metrics. Default: 300. Shorter intervals respond faster but increase host overhead.

#### CPU Thresholds (`cpu_upper_threshold` and `cpu_lower_threshold`)
When CPU usage exceeds `cpu_upper_threshold`, cores are added. When it falls below `cpu_lower_threshold`, cores are removed.

#### Memory Thresholds (`memory_upper_threshold` and `memory_lower_threshold`)
When memory usage exceeds `memory_upper_threshold`, memory is increased. When it falls below `memory_lower_threshold`, memory is reduced.

#### Core and Memory Increments (`core_min_increment`, `core_max_increment`, `memory_min_increment`)
Control the size of each scaling step for CPU cores and memory.

#### Resource Reservation (`reserve_cpu_percent` and `reserve_memory_mb`)
Reserves a percentage of host CPU and a fixed amount of memory that cannot be allocated to containers.

#### Logging (`log_file`)
Path to the log file. Review logs to monitor behaviour and troubleshoot issues.

#### Energy Mode (`energy_mode`)
When enabled, reduces container resources to their configured minimums during off-peak hours (defined by `off_peak_start` and `off_peak_end`).

### Tiers (Optional)

Tiers allow you to apply different scaling rules to groups of containers.

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

- **Example**: `TIER_TEST` can be used for non-critical or test containers, allowing wider resource ranges while still freeing resources when usage is low.

> [!TIP]
> For more configuration examples check the [TIER collection](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/examples/README.md) with 40 snippets customized to fit minimal and recommended requirements for the most popular self-hosted applications.

### Horizontal Scaling Group (Optional)

Horizontal scaling clones containers when group-level resource usage exceeds thresholds. This feature is experimental.

#### Example Configuration:

```yaml
HORIZONTAL_SCALING_GROUP_1:
  base_snapshot_name: "101"
  min_instances: 2
  max_instances: 5
  starting_clone_id: 99000
  clone_network_type: "static"  # Options: "static" or "dhcp"
  static_ip_range: ["192.168.100.195", "192.168.100.200"]  # Leave empty [] if using DHCP
  horiz_cpu_upper_threshold: 95
  horiz_memory_upper_threshold: 95
  group_tag: "horiz_scaling_group_1"
  lxc_containers: 
    - 101
```

> [!WARNING]
> Horizontal scaling is an experimental feature. Test it thoroughly in a non-production environment before using it in production.

> [!NOTE]
> If using DHCP for network configuration, set `clone_network_type: "dhcp"` and `static_ip_range: []`.

- **Example**: When a web service container group exceeds CPU or memory thresholds, LXC AutoScale can clone an additional instance to distribute load.

---

## Service Management

Use systemd to manage the LXC AutoScale daemon:

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

---

## Logging

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

Frequent scaling actions may indicate that thresholds are too tight. Adjust `cpu_upper_threshold`, `memory_upper_threshold`, or increment values to reduce unnecessary scaling.


### Notifications

Notifications on scaling events can be sent to one or more endpoints like Email, Gotify, and Uptime Kuma (push webhook). Configure these options in your `/etc/lxc_autoscale/lxc_autoscale.yaml` configuration file:

```yaml
# Gotify Configuration
gotify_url: 'http://gotify-host'
gotify_token: 'YOUR_GOTIFY_TOKEN'

# Email (SMTP) Configuration
smtp_server: 'smtp.example.com'
smtp_port: 587
smtp_username: 'your-username'
smtp_password: 'your-password'
smtp_from: 'lxc-autoscale@yourdomain.com'
smtp_to:
  - 'admin@yourdomain.com'
  - 'alerts@yourdomain.com'

# Uptime Kuma Webhook Configuration
uptime_kuma_webhook_url: 'http://uptime-kuma-host:3001/api/push/YOUR_PUSH_ID?status=up&msg=OK&ping='
```

> [!TIP]
> You can enable one, multiple, or all notification methods. Leave the configuration empty or remove it if you don't want to use a specific notification method.

## Uninstallation

### Automated Uninstallation

To automatically uninstall LXC AutoScale:

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

---

## Troubleshooting

### Service Won't Start

If the service fails to start:

1. **Check the configuration file syntax**:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('/etc/lxc_autoscale/lxc_autoscale.yaml'))"
   ```
   If there's a YAML syntax error, it will be displayed.

2. **Verify Python dependencies**:
   ```bash
   pip3 install -r /usr/local/bin/lxc_autoscale/requirements.txt
   ```

3. **Check the service logs**:
   ```bash
   journalctl -u lxc_autoscale.service -n 50
   ```

### Scaling Operations Not Working

If containers are not being scaled:

1. **Verify containers are running**:
   ```bash
   pct list
   ```

2. **Check if containers are in the ignore list**: Review the `ignore_lxc` setting in `/etc/lxc_autoscale/lxc_autoscale.yaml`

3. **Verify LXCFS is configured correctly**: See the LXCFS configuration section in the main README

4. **Check resource thresholds**: Ensure thresholds are set appropriately in your configuration

### High CPU Usage by LXC AutoScale

If LXC AutoScale is consuming too many resources:

1. **Increase the poll interval**: Set a higher value for `poll_interval` in the configuration (e.g., 600 seconds instead of 300)

2. **Reduce the number of monitored containers**: Add less critical containers to the `ignore_lxc` list

### Permission Errors

If you see permission denied errors:

1. **Verify the service is running as root**: Check the service file at `/etc/systemd/system/lxc_autoscale.service`

2. **Check file permissions**:
   ```bash
   ls -la /etc/lxc_autoscale/
   ls -la /var/log/lxc_autoscale.log
   ```

### Configuration Changes Not Taking Effect

After modifying the configuration:

1. **Restart the service**:
   ```bash
   systemctl restart lxc_autoscale.service
   ```

2. **Verify the service reloaded successfully**:
   ```bash
   systemctl status lxc_autoscale.service
   ```

### Remote Execution Issues

If using remote execution via SSH:

1. **Verify SSH connectivity**:
   ```bash
   ssh -p <port> <user>@<proxmox_host> "pct list"
   ```

2. **Check SSH credentials**: Ensure `ssh_user`, `ssh_password` (or `ssh_key_path`), and `proxmox_host` are correctly set in the configuration

3. **Verify `use_remote_proxmox` is set to true** in the configuration file

---

## Use Cases

### Media Server

A media server container (e.g., Plex or Jellyfin) can have more CPU and memory allocated during peak usage hours. Set `cpu_upper_threshold` and `memory_upper_threshold` lower (e.g., 75%) for faster scale-up response.

### Multiple Development Environments

When running multiple LXC containers for development, assign different tiers with appropriate thresholds and core limits to keep containers from competing for resources.

### Web Server with Variable Traffic

For a web server container that experiences traffic spikes, horizontal scaling can clone the container automatically. Set a conservative `horiz_cpu_upper_threshold` to avoid unnecessary clones.

---

## Best Practices and Tips

### 1. Regularly Review Configuration
Revisit thresholds and tier settings when adding new containers or when workloads change.

### 2. Monitor Logs
Review log files to understand scaling behaviour. Frequent actions may indicate overly tight thresholds.

### 3. Balance Thresholds
Conservative thresholds reduce over-allocation; aggressive thresholds allow faster scaling. Tune based on your workload.

### 4. Test Changes Before Production
Test configuration changes on non-critical containers before applying to production.

### 5. Use Tiers for Similar Containers
Grouping containers with similar requirements into tiers simplifies management and ensures consistent scaling.
