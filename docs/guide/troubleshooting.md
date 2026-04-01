# Troubleshooting

## Service won't start

1. **Check YAML syntax:**
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('/etc/lxc_autoscale/lxc_autoscale.yaml'))"
   ```

2. **Check for Pydantic validation errors:** the daemon validates all configuration at startup. Common errors:
   - `cpu_lower_threshold must be < cpu_upper_threshold` -- thresholds are inverted or equal.
   - `min_cores must be <= max_cores` -- core limits are inverted.
   - `Input should be 'normal', 'conservative' or 'aggressive'` -- invalid `behaviour` value.
   - `Input should be 'cli' or 'api'` -- invalid `backend` value.

   These errors are printed to stderr and the daemon exits. Fix the YAML values and restart.

3. **Verify Python dependencies:**
   ```bash
   pip3 install -r /usr/local/bin/lxc_autoscale/requirements.txt
   ```

4. **Check service logs:**
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

4. **First cycle returns 0% CPU:** this is expected. The cgroup measurement stores a raw sample on the first cycle and computes the delta on the second cycle. Scaling begins on the second poll interval.

5. **Review the log** for messages like "already at max cores" or "not enough available cores on host".

## High CPU usage by the daemon

1. **Increase the poll interval** (e.g. `poll_interval: 600`).

2. **Reduce monitored containers** by adding non-critical ones to `ignore_lxc`.

::: tip
CPU and memory measurement uses host-side cgroup reads instead of `pct exec`, which dramatically reduces daemon overhead compared to v1.x.
:::

## Permission errors

1. **Verify the service runs as root:** check `/etc/systemd/system/lxc_autoscale.service`.

2. **Check file permissions:**
   ```bash
   ls -la /etc/lxc_autoscale/
   ls -la /var/log/lxc_autoscale.log
   ```

3. **Config file permission warning:** if the daemon logs "Config file is readable by group/others", run:
   ```bash
   chmod 600 /etc/lxc_autoscale/lxc_autoscale.yaml
   ```

## Config changes not taking effect

Restart the service after editing the YAML file:

```bash
systemctl restart lxc_autoscale.service
```

## Remote SSH execution issues

1. **Test SSH connectivity:**
   ```bash
   ssh -p <port> <user>@<proxmox_host> "pct list"
   ```

2. **Host key verification failure:** if you see `Server host key not found in known_hosts`, add the host key:
   ```bash
   ssh-keyscan -H <proxmox_host> >> ~/.ssh/known_hosts
   ```

3. **Verify credentials:** check `ssh_user`, `ssh_password` (or `ssh_key_path`), and `proxmox_host` in the config.

4. **Ensure `use_remote_proxmox: true`** is set.

5. **SSH policy:** if `ssh_host_key_policy` is set to `reject` (the default), connections to hosts not in `known_hosts` will be refused. This is the correct behavior. Do not set it to `auto` in production.

## REST API backend issues

1. **proxmoxer not installed:**
   ```
   RuntimeError: proxmoxer is required for the REST API backend.
   ```
   Fix: `pip install proxmoxer`

2. **Missing API host:**
   ```
   ValueError: proxmox_api.host is required when backend=api
   ```
   Fix: add `proxmox_api.host` to the configuration.

3. **Authentication failure:** verify `token_name` and `token_value` match the API token created in the Proxmox UI. Ensure the token has the required permissions (`VM.Audit`, `VM.Config.CPU`, `VM.Config.Memory`).

4. **SSL verification failure:** if the Proxmox host uses a self-signed certificate, set `proxmox_api.verify_ssl: false`. For production, use a valid certificate.

5. **No nodes found:**
   ```
   RuntimeError: No Proxmox nodes found via API
   ```
   The API token may lack permissions to list nodes, or the Proxmox host is unreachable.

## Notification issues

1. **Notifications not arriving:** check the log for errors like "Gotify notification failed" or "Failed to send email".

2. **Notifications backed off:** if a channel fails 3 times consecutively, it is suppressed for 10 cycles. Look for "consecutive failures, backing off" in the log. The channel retries automatically after the backoff period.

3. **SMTP timeouts:** verify the SMTP server is reachable and the port is correct. Notifications are sent asynchronously, so SMTP delays do not block scaling.
