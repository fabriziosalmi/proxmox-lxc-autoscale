# FAQ

## What is LXC AutoScale?

A resource management daemon for Proxmox hosts. It monitors LXC container CPU and memory usage and adjusts allocations based on configured thresholds. It supports vertical scaling, horizontal scaling (experimental), tier-based configuration, CPU core pinning for hybrid Intel CPUs, and dual CLI/API backend.

## Who should use it?

Proxmox users who want automatic CPU and memory scaling for LXC containers without manual intervention. Suited for homelabs and small production deployments with variable workloads.

## What are the prerequisites?

- Proxmox VE 7.x or 8.x
- Python 3.9+
- Root access to the Proxmox host (for CLI backend) or an API token (for REST API backend)
- LXC containers already created

## How does scaling work?

Each polling cycle (default: 300 seconds), the daemon reads CPU and memory usage for each container via host-side cgroup accounting. If usage exceeds the upper threshold, resources are added. If it drops below the lower threshold, resources are reduced. Changes are applied using `pct set` (CLI backend) or the Proxmox REST API.

The first polling cycle stores a raw CPU sample without scaling. Actual scaling decisions begin on the second cycle, when a time delta is available for accurate percentage calculation.

## Is LXCFS required?

No. CPU and memory measurement uses host-side cgroup accounting, which works without LXCFS. LXCFS is only needed if the cgroup method is unavailable and the daemon falls back to reading `/proc/stat` or `/proc/meminfo` inside containers.

## Can I run this remotely?

Yes. Two options:

- **SSH backend**: set `use_remote_proxmox: true` and provide SSH credentials. Host key verification is enforced by default.
- **REST API backend**: set `backend: api` and configure `proxmox_api` with API tokens. No SSH required.

## Can I use the Proxmox REST API instead of SSH?

Yes. Set `backend: api` in the YAML config and configure `proxmox_api` with host, user, token name, and token value. This avoids shell access entirely and uses scoped API tokens. Requires `pip install proxmoxer`.

## Does it support virtual machines (VMs)?

No. LXC AutoScale manages LXC containers only. For VM autoscaling, see [proxmox-vm-autoscale](https://github.com/fabriziosalmi/proxmox-vm-autoscale).

## Can I exclude containers?

Yes. Add container IDs to the `ignore_lxc` list in the configuration file.

## Are my passwords safe in the config file?

Passwords and tokens stored in the YAML file are readable by anyone with access to the file. Mitigations:

- Set file permissions to `chmod 600` (the daemon warns if the file is world-readable).
- Use `${ENV_VAR}` syntax to reference environment variables instead of storing secrets in plaintext.
- Use the direct environment variable overrides (`LXC_AUTOSCALE_SSH_PASSWORD`, etc.).
- All log output is filtered to redact strings matching secret patterns before writing to disk.

## How do I update?

Re-run the installation script. Back up your configuration file first.

```bash
cp /etc/lxc_autoscale/lxc_autoscale.yaml ~/lxc_autoscale.yaml.backup
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

Existing YAML configuration files are backward-compatible with v2.0. New fields are optional and have safe defaults.

## What is LXC AutoScale ML?

A separate project that uses machine learning-based prediction for scaling decisions. Maintained at [proxmox-lxc-autoscale-ml](https://github.com/fabriziosalmi/proxmox-lxc-autoscale-ml).
