---
layout: home

hero:
  name: LXC AutoScale
  text: Automatic scaling for Proxmox LXC containers
  tagline: CPU, memory, and core pinning — managed by a lightweight daemon.
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/fabriziosalmi/proxmox-lxc-autoscale

features:
  - title: Vertical Scaling
    details: Automatically adjusts CPU cores and memory for each container based on real-time usage thresholds.
  - title: Tier System
    details: Group containers by workload profile with per-tier thresholds, limits, and CPU core pinning.
  - title: Hybrid CPU Pinning
    details: Pin containers to P-cores or E-cores on Intel Alder Lake+ for workload-aware scheduling.
  - title: cgroup-based Metrics
    details: Reads CPU usage from host-side cgroup accounting — accurate, zero-overhead, no LXCFS required.
  - title: Horizontal Scaling
    details: Clone containers automatically when group-level resource usage exceeds thresholds (experimental).
  - title: Notifications
    details: Get notified of scaling events via Email, Gotify, or Uptime Kuma webhooks.
---

## Overview

**LXC AutoScale** is a resource management daemon for Proxmox environments. It monitors LXC container CPU and memory usage every polling cycle (default: 5 minutes) and adjusts allocations based on predefined thresholds.

It runs as a systemd service on the Proxmox host (or remotely via SSH), supports per-container tier configurations, and optionally pins containers to specific CPU cores on hybrid Intel processors.

### Key capabilities

- Automatic vertical scaling of CPU cores and memory
- Per-container or per-group configuration via YAML tiers
- CPU core pinning for Intel Big.LITTLE architectures (12th gen+)
- Horizontal scaling via container cloning (experimental)
- Host CPU and memory reservation to prevent over-allocation
- Energy efficiency mode for off-peak hours
- Notifications via Email, Gotify, Uptime Kuma
- Docker support for remote operation
