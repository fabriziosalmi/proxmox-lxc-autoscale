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
  - title: Dual Backend
    details: Operate via pct CLI commands, locally on the node or over SSH.
  - title: Tier System
    details: Group containers by workload profile with per-tier thresholds, limits, and CPU core pinning.
  - title: cgroup-based Metrics
    details: Reads CPU and memory from host-side cgroup accounting. No pct exec into containers, no LXCFS required.
  - title: Async Architecture
    details: Fully non-blocking event loop. Concurrent data collection, fire-and-forget notifications, zero-sleep measurements.
  - title: Security Hardening
    details: SSH host key verification, secret masking in logs, environment variable expansion, Pydantic config validation.
---

## Overview

**LXC AutoScale** is an async resource management daemon for Proxmox environments. It monitors LXC container CPU and memory usage every polling cycle (default: 5 minutes) and adjusts allocations based on predefined thresholds.

It runs as a systemd service on the Proxmox host, or drives one remotely over SSH. Configuration is validated at startup via Pydantic models and supports per-container tier overrides.

### Key capabilities

- Async event loop with concurrent container data collection
- Pydantic-validated YAML configuration with `${ENV_VAR}` expansion
- Automatic vertical scaling of CPU cores and memory
- Per-container or per-group configuration via YAML tiers
- CPU and memory measured from host-side cgroup (no `pct exec` needed)
- CPU core pinning by L3 cache domain (CCD/CCX) or NUMA node on any CPU, and by P/E core on hybrid Intel (12th gen+)
- Horizontal scaling via container cloning (experimental)
- Timezone-aware off-peak energy mode
- SSH connection pool with host key verification (default: reject)
- Secret masking in all log output
- Notifications via Email, Gotify, Uptime Kuma (async, with failure backoff)
- Docker support with optional non-root user for API-only mode
