# Getting Started

## Prerequisites

- **Proxmox VE 7.x or 8.x** (tested with 8.3.3)
- **Python 3.9+**
- **Root access** to the Proxmox host
- **LXC containers** already created and configured

## Installation

Run the install script on the Proxmox host:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

Verify the service is running:

```bash
systemctl status lxc_autoscale.service
```

Example output:

```
root@proxmox:~# systemctl status lxc_autoscale.service
● lxc_autoscale.service - LXC AutoScale Daemon
     Loaded: loaded (/etc/systemd/system/lxc_autoscale.service; enabled)
     Active: active (running) since Mon 2024-08-19 01:38:07 CEST; 7s ago
   Main PID: 40462 (python3)
     Memory: 9.1M
     CGroup: /system.slice/lxc_autoscale.service
             └─40462 /usr/bin/python3 /usr/local/bin/lxc_autoscale/lxc_autoscale.py
```

## How it works

Each polling cycle (default: 300 seconds):

1. **Collect** — CPU and memory usage is read for each running container via host-side cgroup accounting.
2. **Evaluate** — Usage is compared against the container's tier thresholds (or global defaults).
3. **Scale** — If usage exceeds the upper threshold, cores/memory are added. If below the lower threshold, they are reduced.
4. **Pin** — If `cpu_pinning` is configured, the container is pinned to the specified CPU cores.
5. **Log** — All scaling events are logged (plain text and JSON) and optionally sent as notifications.

## CPU measurement

Starting with v1.2.0, CPU usage is measured via **host-side cgroup accounting** (cgroup v2/v1). This reads the kernel's own CPU time tracking directly from the Proxmox host, without executing commands inside containers.

Benefits:
- Accurate measurements matching the Proxmox web UI
- No dependency on LXCFS
- Minimal overhead (file reads instead of `pct exec`)
- Correct results on low-core hosts with many containers

If cgroup accounting is unavailable, the daemon falls back to `/proc/stat` (requires LXCFS) and then to load average estimation.

## Next steps

- [Configuration](/guide/configuration) — YAML settings reference
- [Tiers](/guide/tiers) — per-container scaling rules
- [CPU Core Pinning](/guide/cpu-pinning) — Intel Big.LITTLE support
- [Docker](/guide/docker) — run the daemon in a container
