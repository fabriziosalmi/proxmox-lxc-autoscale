# FAQ

## What is LXC AutoScale?

A resource management daemon for Proxmox hosts. It monitors LXC container CPU and memory usage and adjusts allocations based on configured thresholds. It supports vertical scaling, horizontal scaling (experimental), tier-based configuration, and CPU core pinning for hybrid Intel CPUs.

## Who should use it?

Proxmox users who want automatic CPU and memory scaling for LXC containers without manual intervention. Suited for homelabs and small production deployments with variable workloads.

## What are the prerequisites?

- Proxmox VE 7.x or 8.x
- Python 3.9+
- Root access to the Proxmox host
- LXC containers already created

## How does scaling work?

Each polling cycle (default: 300 seconds), the daemon reads CPU and memory usage for each container via host-side cgroup accounting. If usage exceeds the upper threshold, resources are added. If it drops below the lower threshold, resources are reduced. Changes are applied using `pct set`.

## Is LXCFS required?

No. Since v1.2.0, CPU measurement uses host-side cgroup accounting which works without LXCFS. LXCFS is only needed if the cgroup method is unavailable and the daemon falls back to reading `/proc/stat` inside containers.

## Can I run this remotely?

Yes. Set `use_remote_proxmox: true` in the configuration and provide SSH credentials.

## Does it support VMs?

No. LXC AutoScale manages LXC containers only. For VM autoscaling, see [proxmox-vm-autoscale](https://github.com/fabriziosalmi/proxmox-vm-autoscale).

## Can I exclude containers?

Yes. Add container IDs to the `ignore_lxc` list in the configuration file.

## How do I update?

Re-run the installation script. Back up your configuration file first.

```bash
cp /etc/lxc_autoscale/lxc_autoscale.yaml ~/lxc_autoscale.yaml.backup
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

## What is LXC AutoScale ML?

A separate project that uses machine learning-based prediction for scaling decisions. Maintained at [proxmox-lxc-autoscale-ml](https://github.com/fabriziosalmi/proxmox-lxc-autoscale-ml).
