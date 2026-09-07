# LXC AutoScale

[![Pylint](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/actions/workflows/pylint.yml/badge.svg)](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/actions/workflows/pylint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![GitHub release](https://img.shields.io/github/v/release/fabriziosalmi/proxmox-lxc-autoscale)](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/releases/latest)
[![Tests](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/actions/workflows/tests.yml/badge.svg)](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/actions/workflows/tests.yml)

**LXC AutoScale** is an async resource management daemon for Proxmox environments. It automatically adjusts CPU and memory allocations for LXC containers based on real-time usage metrics and predefined thresholds. It runs on the Proxmox node or drives one over SSH. Container cloning (horizontal scaling) exists but is experimental and has known defects; see [Feature status](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/wiki/Feature-Status) before enabling it.

- **v2.0** — async architecture, Pydantic config, security hardening
- **Tested on Proxmox VE 8.x (8.3.3) and 9.1**, Python 3.10 to 3.14

**Quick Start**

| Method    | Instructions |
|-----------|--------------|
| Docker    | [Docker](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/guide/docker.md) |
| No Docker | [Install script](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/README.md#quick-start) |

## Features

- **Async architecture** — fully non-blocking event loop using `asyncio`
- **Pydantic configuration** with type validation and `${ENV_VAR}` expansion for secrets
- Automatic vertical scaling of CPU cores and memory based on usage thresholds
- Horizontal scaling via container cloning (experimental)
- Per-container or per-group threshold configuration using tiers
- **CPU core pinning** to an L3 cache domain (`l3:N`, a CCD on AMD), a NUMA node (`numa:N`), or to P-cores and E-cores on hybrid Intel
- **Cgroup-based metrics** for both CPU and memory (no `pct exec` needed)
- **Timezone-aware** off-peak scheduling (configurable, defaults to UTC)
- Host CPU and memory reservation, subtracted from the pool the daemon considers available
- Container exclusion list (`ignore_lxc`)
- Energy efficiency mode that reduces resources during off-peak hours
- **SSH connection pool** with configurable host key verification (default: reject)
- Notifications via email (SMTP), Gotify, and Uptime Kuma (async, fire-and-forget)
- JSON metrics log with rotation (10MB limit)
- Local execution or remote execution via SSH
- Docker support with optional non-root user for API-only mode
- 445 tests, run in CI on Python 3.10 through 3.14
- **Boost/revert scaling mode** — temporary resource boosts with automatic revert after configurable duration

> [!NOTE]
> If you need to autoscale Virtual Machine resources on Proxmox hosts, you will like [this project](https://github.com/fabriziosalmi/proxmox-vm-autoscale).

## Quick Start

### Prerequisites

- **Proxmox VE 8.x or 9.x** (tested on 8.3.3 and 9.1.7)
- **Python 3.10+**. The daemon does not start on 3.9: a lock is built at import time and binds an event loop that the runtime then replaces. Proxmox VE 7 ships 3.9 and is no longer supported.
- **Root access** to the Proxmox host
- **LXC containers** already created and configured
- **Internet connection** for downloading the installation script

### Installation

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

> [!TIP]
> Once installed, verify the service is running:
>
> ```bash
> systemctl status lxc_autoscale.service
> ```

### CPU Measurement

Starting with v1.2.0, CPU usage is measured via **host-side cgroup accounting** (cgroup v2/v1). This reads the kernel's own CPU time tracking for each container directly from the Proxmox host, without needing to execute commands inside containers. Benefits:

- Accurate measurements that match what Proxmox shows in its web UI
- No dependency on LXCFS being installed in containers
- Minimal overhead (simple file reads instead of `pct exec` per container)
- Works correctly on low-core hosts with many containers

If cgroup accounting is unavailable, the daemon falls back to `/proc/stat` (requires LXCFS) and then to load average estimation.

<details>
<summary>LXCFS Configuration (optional, for fallback method)</summary>

If you want the `/proc/stat` fallback to work correctly, configure LXCFS with the `-l` flag in `/lib/systemd/system/lxcfs.service`:

```
ExecStart=/usr/bin/lxcfs /var/lib/lxcfs -l
```

Then run `systemctl daemon-reload && systemctl restart lxcfs` and restart your containers.

_See the [Proxmox forum thread](https://forum.proxmox.com/threads/lxc-containers-shows-hosts-load-average.45724/page-2) for details._
</details>

### CPU Core Pinning

Pin a tier to a subset of the host's CPUs via the `cpu_pinning` tier setting. Groups are auto-detected from the kernel, so the config does not hard-code CPU numbers.

```yaml
# AMD: keep the database on its own CCD, so background work cannot evict its L3.
TIER_databases:
  lxc_containers:
    - "102"
  cpu_pinning: l3:0

TIER_background_tasks:
  lxc_containers:
    - "105"
    - "106"
  cpu_pinning: l3:1
```

Accepted values: `l3:N` (one L3 cache domain, a CCD/CCX on AMD), `numa:N` (one NUMA node), `p-cores` and `e-cores` (hybrid Intel only), `all`, or an explicit range like `0-11` or `0,2,4,6-8`. The groups this host offers are logged the first time a tier asks for one, not at startup.

> [!IMPORTANT]
> Setting `cpu_pinning` on a tier disables that tier's CPU scaling. Proxmox derives a container's affinity from `cores` only when the config carries no explicit `cpuset` line; the pin writes one, so from the container's next start `cores` no longer controls anything. Verified on Proxmox VE 9.1. Use one or the other on a given tier, not both.

On a single-socket host with one L3 domain, `l3:0` and `numa:0` resolve to every CPU, which is no restriction at all. See [CPU Core Pinning](docs/guide/cpu-pinning.md).

## Configuration

LXC AutoScale is configured via a YAML file at `/etc/lxc_autoscale/lxc_autoscale.yaml`. For detailed configuration options, see the **[documentation](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/guide/configuration.md)**.

> [!TIP]
> If you need LXC AutoScale configuration for all your LXC containers, you can automatically generate it by running this command:
> ```bash
> curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale_autoconf.sh | bash
> ```

### Additional Resources

- [LXC AutoScale UI - Simple web UI to check scaling actions and logs](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/tree/main/lxc_autoscale/ui)
- [LXC AutoScale - TIER snippets for 40 self-hosted apps](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/reference/tier-snippets.md)

> [!TIP]
> LXC AutoScale ML has been moved to a separate [repository](https://github.com/fabriziosalmi/proxmox-lxc-autoscale-ml).

## Frequently Asked Questions

### Can I use this on Proxmox 7.x?

LXC AutoScale is tested on Proxmox VE 8.3.3. It may work on older versions, but compatibility is not guaranteed.

### Will this work with my existing containers?

Yes. Configure the container IDs in the YAML file and the service will start managing them.

### Does this support virtual machines (VMs)?

No, LXC AutoScale is designed for LXC containers only. For VM autoscaling, see [proxmox-vm-autoscale](https://github.com/fabriziosalmi/proxmox-vm-autoscale).

### Can I run this remotely?

Yes. Two options:

Set `use_remote_proxmox: true` and provide SSH credentials. Every command runs through `pct` on the far end. There is no REST path, see below.

### Can I use the Proxmox REST API instead of SSH?

No. A REST implementation sat in the tree for a year without ever being connected to the daemon, so `backend: api` changed nothing while appearing to work. It has been removed, and that value is now refused at startup with a message saying why. Building a real one is tracked as [#56](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/56).

### Is it safe to use in production?

Read [Feature status](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/wiki/Feature-Status) first, and test in a non-production environment. Two things to know before you decide. The `--rollback` flag exists but the backup it reads is never written, so it restores nothing ([#88](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/88)). And the daemon rewrites the configuration of running containers as root, so the blast radius of a mistake is the guest, not the daemon: use `ignore_lxc` to scope it to containers you are willing to have resized while you evaluate it.

### How often does it check container resources?

The default polling interval is 300 seconds (5 minutes). Adjust with the `poll_interval` setting.

### Can I exclude certain containers from autoscaling?

Yes. Add container IDs to the `ignore_lxc` list in the configuration file.

For more detailed questions and answers, see the [Q&A documentation](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/reference/faq.md).

## Commercial support & consulting

Running this on your Proxmox fleet? I offer paid support, custom development, and consulting - infrastructure automation, hardening, and monitoring & detection. Reach out: **fabrizio.salmi@gmail.com**.

## Contributing

Contributions are welcome. To get involved:

- [Open an issue](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/new/choose) to report bugs or request features.
- Submit a pull request.
- Fork the repository to develop custom features.

## Contributors

LXC AutoScale is made better by the people who contribute to it. Thank you to everyone who has helped improve the project.

- [Fabrizio Salmi](https://github.com/fabriziosalmi) — Project author and maintainer
- [Clement Kibet](https://github.com/ckkibet)

See the full [contributors graph](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/graphs/contributors).


## Disclaimer
> [!CAUTION]
> The author assumes no responsibility for any damage or issues that may arise from using this tool.

## License

LXC AutoScale is licensed under the MIT License, which means you are free to use, modify, and distribute this software with proper attribution. For more details, please see the [LICENSE](LICENSE) file.
