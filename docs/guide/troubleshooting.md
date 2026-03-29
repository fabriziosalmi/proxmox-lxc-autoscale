# Troubleshooting

## Service won't start

1. **Check YAML syntax:**
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('/etc/lxc_autoscale/lxc_autoscale.yaml'))"
   ```

2. **Verify Python dependencies:**
   ```bash
   pip3 install -r /usr/local/bin/lxc_autoscale/requirements.txt
   ```

3. **Check service logs:**
   ```bash
   journalctl -u lxc_autoscale.service -n 50
   ```

## Scaling not working

1. **Verify containers are running:**
   ```bash
   pct list
   ```

2. **Check if containers are in the ignore list:** review `ignore_lxc` in the config file.

3. **Check thresholds:** ensure the gap between upper and lower thresholds is not too narrow.

4. **Review the log** for messages like "already at max cores" or "not enough available cores on host".

## High CPU usage by the daemon

1. **Increase the poll interval** (e.g. `poll_interval: 600`).

2. **Reduce monitored containers** by adding non-critical ones to `ignore_lxc`.

::: tip
Since v1.2.0, CPU measurement uses host-side cgroup reads instead of `pct exec`, which dramatically reduces daemon overhead.
:::

## Permission errors

1. **Verify the service runs as root:** check `/etc/systemd/system/lxc_autoscale.service`.

2. **Check file permissions:**
   ```bash
   ls -la /etc/lxc_autoscale/
   ls -la /var/log/lxc_autoscale.log
   ```

## Config changes not taking effect

Restart the service after editing the YAML file:

```bash
systemctl restart lxc_autoscale.service
```

## Remote execution issues

1. **Test SSH connectivity:**
   ```bash
   ssh -p <port> <user>@<proxmox_host> "pct list"
   ```

2. **Verify credentials:** check `ssh_user`, `ssh_password` (or `ssh_key_path`), and `proxmox_host` in the config.

3. **Ensure `use_remote_proxmox: true`** is set.
