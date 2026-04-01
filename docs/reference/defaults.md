# Default Settings

All defaults can be overridden in the `DEFAULT` section of the configuration file or per-container via [Tiers](/guide/tiers).

## Scaling parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `poll_interval` | `300` | Seconds between scaling cycles. |
| `cpu_upper_threshold` | `80` | CPU % triggering scale-up. |
| `cpu_lower_threshold` | `20` | CPU % triggering scale-down. |
| `memory_upper_threshold` | `80` | Memory % triggering scale-up. |
| `memory_lower_threshold` | `20` | Memory % triggering scale-down. |
| `min_cores` | `1` | Minimum CPU cores per container. |
| `max_cores` | `4` | Maximum CPU cores per container. |
| `min_memory` | `512` | Minimum memory (MB) per container. |
| `core_min_increment` | `1` | Minimum cores added per scale-up. |
| `core_max_increment` | `2` | Maximum cores added per scale-up. |
| `memory_min_increment` | `256` | Minimum MB added per memory scale-up. |
| `min_decrease_chunk` | `128` | Minimum MB removed per memory scale-down. |

## Host reservation

| Parameter | Default | Description |
|-----------|---------|-------------|
| `reserve_cpu_percent` | `10` | % of host CPU cores never allocated to containers. |
| `reserve_memory_mb` | `2048` | MB of host memory reserved. |

## Energy mode

| Parameter | Default | Description |
|-----------|---------|-------------|
| `off_peak_start` | `22` | Hour (24h) when off-peak begins. |
| `off_peak_end` | `6` | Hour (24h) when off-peak ends. |
| `energy_mode` | `false` | Reduce to minimums during off-peak. Enable via `--energy_mode` flag. |
| `timezone` | `UTC` | IANA timezone for off-peak scheduling (e.g., `Europe/Rome`). |

## Behaviour multiplier

| Value | Multiplier | Effect |
|-------|-----------|--------|
| `conservative` | 0.5x | Slower, smaller scaling steps. |
| `normal` | 1.0x | Default behaviour. |
| `aggressive` | 2.0x | Faster, larger scaling steps. |

## Backend selection

| Parameter | Default | Description |
|-----------|---------|-------------|
| `backend` | `cli` | `cli` for pct commands (local or SSH), `api` for Proxmox REST API. |

## SSH (remote CLI backend)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `use_remote_proxmox` | `false` | Execute pct commands on a remote host via SSH. |
| `proxmox_host` | | IP or hostname of the remote Proxmox host. |
| `ssh_user` | | SSH username. |
| `ssh_password` | | SSH password. Prefer `ssh_key_path` or env var `LXC_AUTOSCALE_SSH_PASSWORD`. |
| `ssh_key_path` | | Path to SSH private key. |
| `ssh_port` | `22` | SSH port. |
| `ssh_host_key_policy` | `reject` | `reject` (verify host keys), `system` (warn on unknown), `auto` (deprecated). |

## Proxmox REST API backend

| Parameter | Default | Description |
|-----------|---------|-------------|
| `proxmox_api.host` | | Proxmox host IP or hostname. |
| `proxmox_api.user` | | Proxmox user (e.g., `root@pam` or `autoscale@pve`). |
| `proxmox_api.token_name` | | API token name. |
| `proxmox_api.token_value` | | API token secret. Use env var `${PROXMOX_API_TOKEN}`. |
| `proxmox_api.verify_ssl` | `true` | Verify SSL certificates when connecting to the API. |

## File paths

| Parameter | Default |
|-----------|---------|
| `log_file` | `/var/log/lxc_autoscale.log` |
| `lock_file` | `/var/lock/lxc_autoscale.lock` |
| `backup_dir` | `/var/lib/lxc_autoscale/backups` |

## Container exclusion

| Parameter | Description |
|-----------|-------------|
| `ignore_lxc` | List of container IDs to exclude from all scaling operations. |
