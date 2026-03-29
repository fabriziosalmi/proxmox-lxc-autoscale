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
| `--rollback` | Restore all containers to their last backed-up settings. |
| `--debug` | Enable debug-level logging. |
