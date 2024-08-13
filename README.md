# Proxmox LXC AutoScale

**LXC AutoScale** is a Python-based daemon designed to dynamically manage and optimize resources (CPU, memory, and storage) for LXC containers on a Proxmox host. By continuously monitoring container usage, it ensures that resources are allocated efficiently, potentially reducing energy consumption and improving system performance.

> [!WARNING]  
> Storage stuff is still not tested. Use at your own risk.

## Features

- **Automatic Resource Adjustment**: Adjust CPU cores, memory, and storage based on container usage thresholds.
- **Backup and Rollback**: Automatically backs up container configurations before making changes and allows easy rollback to previous settings.
- **Daemon Mode**: Runs continuously as a background service, checking and adjusting resources at regular intervals.
- **Energy Efficiency Mode**: Optionally reduce resources during off-peak hours to save energy.
- **Gotify Notifications**: Send real-time notifications of significant events (e.g., resource adjustments, rollbacks) via Gotify.
- **Granular Control of Resource Allocation**: Customize thresholds and increments for specific containers or groups of containers.
- **Detailed Logging**: Logs all actions, making it easy to monitor and debug the resource management process.

## Installation

### Prerequisites

- **Python 3.x**: Ensure Python 3 is installed on your Proxmox host.

### Installation Steps

1. **Download the Script**:
   ```bash
   wget https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/usr/local/bin/lxc_autoscale.py -O /usr/local/bin/lxc_autoscale.py
   chmod +x /usr/local/bin/lxc_autoscale.py
   ```

2. **Set Up Directories for Logs and Backups**:
   ```bash
   sudo mkdir -p /var/log/
   sudo mkdir -p /var/lib/lxc_autoscale/backups/
   ```

3. **Ensure Proper Permissions**:
   ```bash
   sudo chown root:root /var/log/lxc_autoscale.log
   sudo chown -R root:root /var/lib/lxc_autoscale/
   sudo chmod 755 /var/lib/lxc_autoscale/
   sudo chmod 644 /var/log/lxc_autoscale.log
   ```

4. **Create a Systemd Service**:
   Create a service file to run LXC AutoScale as a daemon.

   ```bash
   sudo nano /etc/systemd/system/lxc_autoscale.service
   ```

   Add the following content:

   ```ini
   [Unit]
   Description=LXC AutoScale - LXC Resource Management Daemon
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 /usr/local/bin/lxc_autoscale.py --poll_interval 300
   Restart=always
   User=root

   [Install]
   WantedBy=multi-user.target
   ```

5. **Enable and Start the Service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable lxc_autoscale.service
   sudo systemctl start lxc_autoscale.service
   ```

## Usage

### Running the Script Manually

You can run the script manually with default settings or custom parameters:

- **Default Settings**:
  ```bash
  python3 /usr/local/bin/lxc_autoscale.py
  ```

- **Run with Energy Efficiency Mode and Gotify Notifications**:
  ```bash
  python3 /usr/local/bin/lxc_autoscale.py --energy_mode --gotify_url https://gotify.example.com --gotify_token YOUR_TOKEN
  ```

- **Rollback to Previous Configuration**:
  ```bash
  python3 /usr/local/bin/lxc_autoscale.py --rollback
  ```

### Monitoring the Service

Check the status and logs of the service:

```bash
sudo systemctl status lxc_autoscale.service
sudo journalctl -u lxc_autoscale.service -f
```

## Configuration Options

- **--poll_interval**: Set the polling interval in seconds (default: 300).
- **--cpu_upper**: CPU usage upper threshold to trigger core addition (default: 80).
- **--cpu_lower**: CPU usage lower threshold to trigger core reduction (default: 20).
- **--mem_upper**: Memory usage upper threshold to trigger memory addition (default: 80).
- **--mem_lower**: Memory usage lower threshold to trigger memory reduction (default: 20).
- **--storage_upper**: Storage usage upper threshold to trigger storage addition (default: 80).
- **--core_min**: Minimum number of cores to add or remove (default: 1).
- **--core_max**: Maximum number of cores to add or remove (default: 4).
- **--mem_min**: Minimum amount of memory to add or remove in MB (default: 512).
- **--storage_inc**: Storage increment in MB (default: 10240).
- **--min_cores**: Minimum number of cores per container (default: 1).
- **--max_cores**: Maximum number of cores per container (default: 8).
- **--min_mem**: Minimum memory per container in MB (default: 512).
- **--min_decrease_chunk**: Minimum memory decrease chunk in MB (default: 512).
- **--gotify_url**: Gotify server URL for notifications.
- **--gotify_token**: Gotify server token for authentication.
- **--energy_mode**: Enable energy efficiency mode during off-peak hours.
- **--rollback**: Rollback to the previous container configurations.

## Demo

![demo](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/static/proxmox-lxc-autoscale-gotify.png?raw=true)

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue if you find any bugs or have suggestions for improvements.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
