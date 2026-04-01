# LXC AutoScale

[![Pylint](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/actions/workflows/pylint.yml/badge.svg)](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/actions/workflows/pylint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![GitHub release](https://img.shields.io/github/v/release/fabriziosalmi/proxmox-lxc-autoscale)](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/releases/latest)
[![Tests](https://img.shields.io/badge/tests-320%20passed-brightgreen)](https://github.com/fabriziosalmi/proxmox-lxc-autoscale)
[![Coverage](https://img.shields.io/badge/coverage-86%25-brightgreen)](https://github.com/fabriziosalmi/proxmox-lxc-autoscale)

**LXC AutoScale** is an async resource management daemon for Proxmox environments. It automatically adjusts CPU and memory allocations for LXC containers based on real-time usage metrics and predefined thresholds. It supports local execution, remote execution via SSH, or the **Proxmox REST API** as backend. Container cloning (horizontal scaling) is also supported as an experimental feature.

- **v2.0** — async architecture, Pydantic config, dual CLI/API backend, security hardening
- **Tested with Proxmox 8.x** (8.3.3+)

**Quick Start**

| Method    | Instructions |
|-----------|--------------|
| Docker    | [Docker](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/README.md#docker) |
| No Docker | [Install script](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/README.md#quick-start) |

## Features

- **Async architecture** — fully non-blocking event loop using `asyncio`
- **Dual backend**: CLI (`pct` commands) or **Proxmox REST API** (`proxmoxer`)
- **Pydantic configuration** with type validation and `${ENV_VAR}` expansion for secrets
- Automatic vertical scaling of CPU cores and memory based on usage thresholds
- Horizontal scaling via container cloning (experimental)
- Per-container or per-group threshold configuration using tiers
- **CPU core pinning** for Intel hybrid CPUs (Alder Lake+): pin containers to P-cores or E-cores
- **Cgroup-based metrics** for both CPU and memory (no `pct exec` needed)
- **Timezone-aware** off-peak scheduling (configurable, defaults to UTC)
- Host CPU and memory reservation to prevent over-allocation
- Container exclusion list (`ignore_lxc`)
- Energy efficiency mode that reduces resources during off-peak hours
- **SSH connection pool** with configurable host key verification (default: reject)
- **Secret masking** in log output (passwords, tokens, API keys redacted)
- Notifications via email (SMTP), Gotify, and Uptime Kuma (async, fire-and-forget)
- JSON metrics log with rotation (10MB limit)
- Local execution, remote execution via SSH, or REST API
- Docker support with optional non-root user for API-only mode
- **320 tests** with 86% code coverage

> [!NOTE]
> If you need to autoscale Virtual Machine resources on Proxmox hosts, you will like [this project](https://github.com/fabriziosalmi/proxmox-vm-autoscale).

## Quick Start

### Prerequisites

- **Proxmox VE 7.x or 8.x** (tested with 8.3.3)
- **Python 3.9+**
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

### CPU Core Pinning (Intel Big.LITTLE)

On hybrid Intel CPUs (Alder Lake / Raptor Lake / Arrow Lake, 12th gen+), you can pin containers to Performance or Efficiency cores via the `cpu_pinning` tier setting:

```yaml
TIER_databases:
  lxc_containers:
    - "102"
  cpu_pinning: p-cores       # Run on Performance cores only

TIER_background_tasks:
  lxc_containers:
    - "105"
    - "106"
  cpu_pinning: e-cores       # Run on Efficiency cores only
```

Accepted values: `p-cores`, `e-cores`, `all`, or an explicit range like `0-11` or `0,2,4,6-8`. Core topology is auto-detected from the kernel at startup.

## Configuration

LXC AutoScale is configured via a YAML file at `/etc/lxc_autoscale/lxc_autoscale.yaml`. For detailed configuration options, see the **[documentation](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/README.md)**.

> [!TIP]
> If you need LXC AutoScale configuration for all your LXC containers, you can automatically generate it by running this command:
> ```bash
> curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale_autoconf.sh | bash
> ```

### Additional Resources

- [LXC AutoScale UI - Simple web UI to check scaling actions and logs](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/tree/main/lxc_autoscale/ui)
- [LXC AutoScale - TIER snippets for 40 self-hosted apps](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/examples/README.md)

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

1. **SSH** (default): Set `use_remote_proxmox: true` and provide SSH credentials.
2. **REST API** (v2.0): Set `backend: api` and configure `proxmox_api` with API tokens. Requires `pip install proxmoxer`.

### Can I use the Proxmox REST API instead of SSH?

Yes (v2.0+). Set `backend: api` in the YAML config and provide API token credentials under `proxmox_api`. This avoids SSH entirely and uses scoped API tokens instead of root shell access. See the [configuration docs](docs/guide/configuration.md) for details.

### Is it safe to use in production?

LXC AutoScale backs up container settings before making changes and supports rollback via `--rollback`. Test thoroughly in a non-production environment before deploying to production.

### How often does it check container resources?

The default polling interval is 300 seconds (5 minutes). Adjust with the `poll_interval` setting.

### Can I exclude certain containers from autoscaling?

Yes. Add container IDs to the `ignore_lxc` list in the configuration file.

For more detailed questions and answers, see the [Q&A documentation](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/q%26a/README.md).

## Contributing

Contributions are welcome. To get involved:

- [Open an issue](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/new/choose) to report bugs or request features.
- Submit a pull request.
- Fork the repository to develop custom features.

## Other Projects

If you like this project, you may also like these:

- [caddy-waf](https://github.com/fabriziosalmi/caddy-waf) Caddy WAF (Regex Rules, IP and DNS filtering, Rate Limiting, GeoIP, Tor, Anomaly Detection) 
- [patterns](https://github.com/fabriziosalmi/patterns) Automated OWASP CRS and Bad Bot Detection for Nginx, Apache, Traefik and HaProxy
- [blacklists](https://github.com/fabriziosalmi/blacklists) Hourly updated domains blacklist 🚫 
- [proxmox-vm-autoscale](https://github.com/fabriziosalmi/proxmox-vm-autoscale) Automatically scale virtual machines resources on Proxmox hosts 
- [UglyFeed](https://github.com/fabriziosalmi/UglyFeed) Retrieve, aggregate, filter, evaluate, rewrite and serve RSS feeds using Large Language Models for fun, research and learning purposes 
- [DevGPT](https://github.com/fabriziosalmi/DevGPT) Code together, right now! GPT powered code assistant to build project in minutes
- [websites-monitor](https://github.com/fabriziosalmi/websites-monitor) Websites monitoring via GitHub Actions (expiration, security, performances, privacy, SEO)
- [caddy-mib](https://github.com/fabriziosalmi/caddy-mib) Track and ban client IPs generating repetitive errors on Caddy 
- [zonecontrol](https://github.com/fabriziosalmi/zonecontrol) Cloudflare Zones Settings Automation using GitHub Actions 
- [lws](https://github.com/fabriziosalmi/lws) linux (containers) web services
- [cf-box](https://github.com/fabriziosalmi/cf-box) cf-box is a set of Python tools to play with API and multiple Cloudflare accounts.
- [limits](https://github.com/fabriziosalmi/limits) Automated rate limits implementation for web servers 
- [dnscontrol-actions](https://github.com/fabriziosalmi/dnscontrol-actions) Automate DNS updates and rollbacks across multiple providers using DNSControl and GitHub Actions 
- [proxmox-lxc-autoscale-ml](https://github.com/fabriziosalmi/proxmox-lxc-autoscale-ml) Automatically scale the LXC containers resources on Proxmox hosts with AI
- [csv-anonymizer](https://github.com/fabriziosalmi/csv-anonymizer) CSV fuzzer/anonymizer
- [iamnotacoder](https://github.com/fabriziosalmi/iamnotacoder) AI code generation and improvement


## Disclaimer
> [!CAUTION]
> The author assumes no responsibility for any damage or issues that may arise from using this tool.

## License

LXC AutoScale is licensed under the MIT License, which means you are free to use, modify, and distribute this software with proper attribution. For more details, please see the [LICENSE](LICENSE) file.
