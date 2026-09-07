# Service Management

LXC AutoScale runs as a systemd service.

## Commands

```bash
# Start
systemctl start lxc_autoscale.service

# Stop
systemctl stop lxc_autoscale.service

# Restart (required after config changes)
systemctl restart lxc_autoscale.service

# Check status
systemctl status lxc_autoscale.service

# Enable at boot
systemctl enable lxc_autoscale.service

# Disable at boot
systemctl disable lxc_autoscale.service
```

## Command-line options

The daemon accepts the following arguments:

| Flag | Description |
|------|-------------|
| `--poll_interval <seconds>` | Override the polling interval from config. |
| `--energy_mode` | Enable energy efficiency mode (reduce resources during off-peak). |
| `--rollback` | **Removed in 2.0.5.** It never restored anything: no backup was ever written, so it reported success over an empty directory. The flag still exists and exits with an explanation rather than an argparse error ([#88](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/88)). |
| `--debug` | Enable debug-level logging. |
