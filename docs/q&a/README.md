# LXC AutoScale: Questions & Answers

## Summary of Questions

1. [What is LXC AutoScale?](#what-is-lxc-autoscale)
2. [Who should use LXC AutoScale?](#who-should-use-lxc-autoscale)
3. [What are the prerequisites?](#what-are-the-prerequisites)
4. [How do I install LXC AutoScale?](#how-do-i-install-lxc-autoscale)
5. [Can LXC AutoScale be reconfigured after installation?](#can-lxc-autoscale-be-reconfigured-after-installation)
6. [What environments are supported?](#what-environments-are-supported)
7. [How does LXC AutoScale scale resources?](#how-does-lxc-autoscale-scale-resources)
8. [What are the default settings?](#what-are-the-default-settings)
9. [Can the scaling thresholds be customized?](#can-the-scaling-thresholds-be-customized)
10. [How does energy efficiency mode work?](#how-does-energy-efficiency-mode-work)
11. [Does LXC AutoScale support container cloning?](#does-lxc-autoscale-support-container-cloning)
12. [Can LXC AutoScale manage multiple containers simultaneously?](#can-lxc-autoscale-manage-multiple-containers-simultaneously)
13. [How does LXC AutoScale ensure critical containers have resources?](#how-does-lxc-autoscale-ensure-critical-containers-have-resources)
14. [What types of notifications are available?](#what-types-of-notifications-are-available)
15. [Is there a way to monitor resource usage?](#is-there-a-way-to-monitor-resource-usage)
16. [How do I update LXC AutoScale?](#how-do-i-update-lxc-autoscale)
17. [What is the difference between LXC AutoScale and LXC AutoScale ML?](#what-is-the-difference-between-lxc-autoscale-and-lxc-autoscale-ml)
18. [Where can I find detailed documentation?](#where-can-i-find-detailed-documentation)

## Questions & Answers

### What is LXC AutoScale?
LXC AutoScale is a resource management daemon for Proxmox hosts. It monitors LXC container CPU and memory usage and adjusts allocations based on configured thresholds. It can also clone containers (horizontal scaling, experimental) when resource demands exceed what vertical scaling can address. It runs as a systemd service, either locally on the Proxmox host or remotely via SSH.

### Who should use LXC AutoScale?
LXC AutoScale is suited for Proxmox users who want automatic CPU and memory scaling for LXC containers without manual intervention. It is configured through a YAML file and runs as a daemon, making it appropriate for both homelab and small production Proxmox deployments. Users with highly variable workloads or who want to conserve resources during off-peak hours will benefit most.

### What are the prerequisites?
- A running Proxmox VE host (tested with 8.3.3)
- Python 3.6+
- Root access to the Proxmox host
- LXC containers already created and configured
- LXCFS configured with the `-l` flag (required for accurate load average readings inside containers)

### How do I install LXC AutoScale?
Run the installation script on the Proxmox host:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

Then verify the service is running:

```bash
systemctl status lxc_autoscale.service
```

See the [documentation](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/README.md) for Docker setup and remote execution configuration.

### Can LXC AutoScale be reconfigured after installation?
Yes. Edit `/etc/lxc_autoscale/lxc_autoscale.yaml` and restart the service:

```bash
systemctl restart lxc_autoscale.service
```

No reinstallation is required.

### What environments are supported?
LXC AutoScale works with Proxmox VE and manages LXC containers. It does not support KVM virtual machines or non-Proxmox hypervisors. It can run locally on the Proxmox host or on a remote machine that connects via SSH to the Proxmox host.

### How does LXC AutoScale scale resources?
Each polling cycle (default: every 300 seconds), the daemon reads CPU and memory usage for each container. If usage exceeds the configured upper threshold, it increases allocated cores or memory. If usage falls below the lower threshold, it decreases them. Scaling steps are controlled by `core_min_increment`, `core_max_increment`, `memory_min_increment`, and `min_decrease_chunk`. Changes are applied using `pct set`.

### What are the default settings?
Key defaults (from `config.py`):

| Parameter | Default |
|-----------|---------|
| `poll_interval` | 300 s |
| `cpu_upper_threshold` | 80% |
| `cpu_lower_threshold` | 20% |
| `memory_upper_threshold` | 80% |
| `memory_lower_threshold` | 20% |
| `min_cores` | 1 |
| `max_cores` | 4 |
| `min_memory` | 512 MB |
| `core_min_increment` | 1 |
| `core_max_increment` | 2 |
| `memory_min_increment` | 256 MB |
| `reserve_cpu_percent` | 10% |
| `reserve_memory_mb` | 2048 MB |

All defaults can be overridden in the `DEFAULT` section of the configuration file.

### Can the scaling thresholds be customized?
Yes. Set `cpu_upper_threshold`, `cpu_lower_threshold`, `memory_upper_threshold`, and `memory_lower_threshold` in the `DEFAULT` section for global defaults, or in a `TIER_` section for specific containers.

### How does energy efficiency mode work?
When `energy_mode` is enabled (via `--energy_mode` flag or configuration), the daemon reduces container CPU and memory to their configured minimums during off-peak hours (`off_peak_start` to `off_peak_end`). Resources are scaled normally outside of off-peak hours.

### Does LXC AutoScale support container cloning?
Yes, via horizontal scaling groups (experimental). When average CPU or memory usage in a group exceeds a threshold, the daemon clones the base container to a new ID. The clone can be configured with DHCP or a static IP. The number of instances is bounded by `min_instances` and `max_instances`. Scale-in (removing clones) is also supported when usage drops. This feature should be tested in a non-production environment before use.

### Can LXC AutoScale manage multiple containers simultaneously?
Yes. All running, non-ignored containers are evaluated each polling cycle. Each container is scaled independently based on its own tier configuration (if defined) or the global defaults.

### How does LXC AutoScale ensure critical containers have resources?
Two mechanisms apply:
- **Host reservation**: `reserve_cpu_percent` and `reserve_memory_mb` ensure a minimum amount of host resources is never allocated to containers.
- **Tier configuration**: Critical containers can be assigned a `TIER_` block with higher `max_cores` and `max_memory`, ensuring they can scale up further than default limits.

### What types of notifications are available?
LXC AutoScale can send notifications for scaling events via:
- **Email (SMTP)**: configure `smtp_server`, `smtp_port`, `smtp_username`, `smtp_password`, `smtp_from`, `smtp_to`
- **Gotify**: configure `gotify_url` and `gotify_token`
- **Uptime Kuma**: configure `uptime_kuma_webhook_url`

Configure one or more in the `DEFAULT` section of the YAML file. Unconfigured notifiers are skipped.

### Is there a way to monitor resource usage?
LXC AutoScale writes scaling events and resource metrics to two log files:
- `/var/log/lxc_autoscale.log` — plain-text log
- `/var/log/lxc_autoscale.json` — JSON log for machine-readable metrics

A simple web UI for viewing logs is also available: [LXC AutoScale UI](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/tree/main/lxc_autoscale/ui).

### How do I update LXC AutoScale?
Re-run the installation script:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

Back up your configuration file first to avoid overwriting customizations.

### What is the difference between LXC AutoScale and LXC AutoScale ML?
LXC AutoScale (this project) uses threshold-based rules defined in the configuration file. [LXC AutoScale ML](https://github.com/fabriziosalmi/proxmox-lxc-autoscale-ml) is a separate project that adds machine learning-based prediction for scaling decisions. The ML variant is maintained in its own repository.

### Where can I find detailed documentation?
- [Main documentation](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/README.md) — installation, configuration, service management, troubleshooting
- [TIER snippets](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/examples/README.md) — example tier configurations for common self-hosted applications
- [LXC AutoScale UI](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/tree/main/lxc_autoscale/ui) — simple web UI for viewing logs
