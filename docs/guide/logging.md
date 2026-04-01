# Logging & Monitoring

## Log files

| File | Format | Rotation | Description |
|------|--------|----------|-------------|
| `/var/log/lxc_autoscale.log` | Plain text | 10 MB, 5 backups | Human-readable scaling events and daemon status. |
| `/var/log/lxc_autoscale.json` | JSON | 10 MB, 3 backups | Machine-readable events for parsing and dashboards. |

Both files rotate automatically when they exceed 10 MB. Rotated files are named `.log.1`, `.log.2`, etc.

## Real-time monitoring

Watch the plain-text log:

```bash
tail -f /var/log/lxc_autoscale.log
```

Parse the JSON log with `jq`:

```bash
cat /var/log/lxc_autoscale.json | jq .
```

Filter scaling events for a specific container:

```bash
cat /var/log/lxc_autoscale.json | jq 'select(.container_id == "102")'
```

## Log interpretation

Each scaling cycle logs:
- Container CPU and memory usage percentages
- Tier assignment and threshold boundaries
- Scaling actions taken (cores/memory added or removed)
- Warnings when resources cannot be allocated
- Timestamps in the configured timezone (default: UTC)

::: tip
Frequent scaling actions may indicate that thresholds are too tight. Increase the gap between `cpu_lower_threshold` and `cpu_upper_threshold` to reduce scaling churn.
:::

## Secret masking

All log output is processed by a masking filter before being written to any destination (console, file, JSON). The filter redacts values that match common secret patterns:

- Key-value pairs containing `password`, `token`, `secret`, or `api_key`
- Bearer authorization headers
- Strings passed to `sshpass -p`
- Long hex or base64 strings (32+ characters)

Redacted values are replaced with `***REDACTED***`. This is always active and requires no configuration.

## Debug mode

Enable debug logging with the `--debug` flag:

```bash
python lxc_autoscale.py --debug
```

Or via systemd:

```bash
# Edit the service file to add --debug
systemctl edit lxc_autoscale.service
systemctl restart lxc_autoscale.service
```

Debug mode logs all command executions, cgroup reads, tier evaluations, and scaling decisions. It generates significantly more output and should be used for troubleshooting only.

## Web UI

A simple web UI for viewing logs is available at [`lxc_autoscale/ui`](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/tree/main/lxc_autoscale/ui).
