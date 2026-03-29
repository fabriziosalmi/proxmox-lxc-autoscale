# Logging & Monitoring

## Log files

| File | Format | Description |
|------|--------|-------------|
| `/var/log/lxc_autoscale.log` | Plain text | Human-readable scaling events and daemon status. |
| `/var/log/lxc_autoscale.json` | JSON | Machine-readable events for parsing and dashboards. |

## Real-time monitoring

Watch the plain-text log:

```bash
tail -f /var/log/lxc_autoscale.log
```

Parse the JSON log with `jq`:

```bash
apt install jq -y
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

::: tip
Frequent scaling actions may indicate that thresholds are too tight. Increase the gap between `cpu_lower_threshold` and `cpu_upper_threshold` to reduce scaling churn.
:::

## Web UI

A simple web UI for viewing logs is available at [`lxc_autoscale/ui`](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/tree/main/lxc_autoscale/ui).
