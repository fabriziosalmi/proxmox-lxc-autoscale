# Proxmox LXC AutoScale

**LXC AutoScale** is a Python-based daemon designed to dynamically manage and optimize resources (CPU, memory, and storage) for LXC containers on a Proxmox host. By continuously monitoring container usage, it ensures that resources are allocated efficiently, potentially reducing energy consumption and improving system performance.

## Features

- **Automatic Resource Adjustment**: Adjust CPU cores, memory, and storage based on container usage thresholds.
- **Backup and Rollback**: Automatically backs up container configurations before making changes and allows easy rollback to previous settings.
- **Daemon Mode**: Runs continuously as a background service, checking and adjusting resources at regular intervals.
- **Customizable via CLI**: Configure thresholds, increments, and other parameters via command-line arguments.
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
   sudo mkdir -p /var/backups/
   ```

3. **Ensure Proper Permissions**:
   ```bash
   sudo chown root:root /var/log/lxc_auto_scale.log
   sudo chown -R root:root /var/lib/lxc_auto_scale/
   sudo chmod 755 /var/lib/lxc_auto_scale/
   sudo chmod 644 /var/log/lxc_auto_scale.log
   ```

4. **Create a Systemd Service**:
   Create a service file to run LXC AutoScale as a daemon.

   ```bash
   sudo nano /etc/systemd/system/lxc_autoscale.service
   ```

   Add the following content:

   ```ini
   [Unit]
   Description=Proxmox LXC AutoScale
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 /usr/local/bin/lxc_autoscale.py --poll_interval 60
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

- **Custom Poll Interval and CPU Thresholds**:
  ```bash
  python3 /usr/local/bin/lxc_autoscale.py --poll_interval 60 --cpu_upper 85 --cpu_lower 15
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
- **--rollback**: Rollback to the previous container configurations.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue if you find any bugs or have suggestions for improvements.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
