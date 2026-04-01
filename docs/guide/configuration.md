# Configuration

LXC AutoScale is configured via a single YAML file.

## File location

```
/etc/lxc_autoscale/lxc_autoscale.yaml
```

Back up before editing:

```bash
cp /etc/lxc_autoscale/lxc_autoscale.yaml /etc/lxc_autoscale/lxc_autoscale.yaml.backup
```

## Full example

```yaml
DEFAULT:
  log_file: /var/log/lxc_autoscale.log
  lock_file: /var/lock/lxc_autoscale.lock
  backup_dir: /var/lib/lxc_autoscale/backups
  reserve_cpu_percent: 10
  reserve_memory_mb: 2048
  off_peak_start: 22
  off_peak_end: 6
  behaviour: normal          # normal | conservative | aggressive
  cpu_upper_threshold: 80
  cpu_lower_threshold: 20
  memory_upper_threshold: 70
  memory_lower_threshold: 20
  min_cores: 1
  max_cores: 4
  min_memory: 256
  core_min_increment: 1
  core_max_increment: 2
  memory_min_increment: 256
  min_decrease_chunk: 256
  ignore_lxc:
    - "104"
```

## Parameter reference

### Polling

| Parameter | Default | Description |
|-----------|---------|-------------|
| `poll_interval` | `300` | Seconds between each scaling cycle. Shorter = faster response, more host overhead. |

### CPU thresholds

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cpu_upper_threshold` | `80` | CPU % above which cores are added. |
| `cpu_lower_threshold` | `20` | CPU % below which cores are removed. |
| `core_min_increment` | `1` | Minimum cores added per scale-up. |
| `core_max_increment` | `2` | Maximum cores added per scale-up. |
| `min_cores` | `1` | Minimum cores a container can have. |
| `max_cores` | `4` | Maximum cores a container can have. |

### Memory thresholds

| Parameter | Default | Description |
|-----------|---------|-------------|
| `memory_upper_threshold` | `70` | Memory % above which memory is increased. |
| `memory_lower_threshold` | `20` | Memory % below which memory is reduced. |
| `memory_min_increment` | `256` | Minimum MB added per scale-up. |
| `min_decrease_chunk` | `256` | Minimum MB removed per scale-down. |
| `min_memory` | `256` | Minimum MB a container can have. |

### Host reservation

| Parameter | Default | Description |
|-----------|---------|-------------|
| `reserve_cpu_percent` | `10` | % of host CPU cores reserved (never allocated to containers). |
| `reserve_memory_mb` | `2048` | MB of host memory reserved. |

### Energy mode

| Parameter | Default | Description |
|-----------|---------|-------------|
| `off_peak_start` | `22` | Hour (24h) when off-peak begins. |
| `off_peak_end` | `6` | Hour (24h) when off-peak ends. |
| `energy_mode` | `false` | Enable via `--energy_mode` flag. Reduces containers to minimums during off-peak. |

### Behaviour

| Parameter | Default | Description |
|-----------|---------|-------------|
| `behaviour` | `normal` | `conservative` (0.5x scaling), `normal` (1x), or `aggressive` (2x). |

### Container exclusion

| Parameter | Description |
|-----------|-------------|
| `ignore_lxc` | List of container IDs to exclude from all scaling operations. |

### Scaling mode (v2.0)

LXC AutoScale supports two scaling modes, configurable per-tier or globally:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `scaling_mode` | `threshold` | `threshold` (permanent adjustments) or `boost` (temporary boost with auto-revert). |
| `boost_factor` | `1.5` | Primary boost multiplier (+50%). |
| `boost_fallback_factor` | `1.25` | Fallback multiplier if primary exceeds host capacity (+25%). |
| `boost_duration` | `120` | Seconds before automatic revert to original values. |
| `saturation_threshold` | `0.95` | Usage fraction (0.0-1.0) that triggers boost. |
| `consecutive_samples` | `3` | Consecutive polls above threshold before boosting. |

**Threshold mode** (default): resources are adjusted permanently based on upper/lower thresholds. A container that spikes stays scaled until usage drops below the lower threshold.

**Boost mode**: when a container is saturated for N consecutive polls, resources are boosted by a factor for a limited duration, then automatically reverted. If the container is still saturated after revert, the next poll cycle re-evaluates and re-boosts if needed.

```yaml
TIER_databases:
  lxc_containers:
    - "105"
  scaling_mode: boost
  boost_factor: 1.5
  boost_duration: 300
  saturation_threshold: 0.90
  consecutive_samples: 2
```

Boost state is persisted to disk and survives daemon restarts. If an administrator changes a container's resources from the Proxmox UI while a boost is active, the daemon detects the change and adopts the new value as baseline.

### Backend selection (v2.0)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `backend` | `cli` | `cli` (pct commands, local or SSH) or `api` (Proxmox REST API via proxmoxer). |
| `timezone` | `UTC` | IANA timezone for off-peak scheduling (e.g., `Europe/Rome`, `America/New_York`). |

### Remote SSH execution

| Parameter | Description |
|-----------|-------------|
| `use_remote_proxmox` | Set to `true` to execute commands on a remote Proxmox host via SSH. |
| `proxmox_host` | IP or hostname of the remote Proxmox host. |
| `ssh_user` | SSH username. |
| `ssh_password` | SSH password (or use `ssh_key_path` instead). |
| `ssh_key_path` | Path to SSH private key. |
| `ssh_port` | SSH port (default: `22`). |
| `ssh_host_key_policy` | `reject` (default, safe), `system` (warn on unknown), `auto` (deprecated, insecure). |

### Proxmox REST API backend (v2.0)

Set `backend: api` to use the Proxmox REST API instead of CLI commands. Requires `pip install proxmoxer`.

```yaml
DEFAULT:
  backend: api
  proxmox_api:
    host: 192.168.1.1
    user: root@pam
    token_name: autoscale
    token_value: ${PROXMOX_API_TOKEN}
    verify_ssl: true
```

| Parameter | Description |
|-----------|-------------|
| `proxmox_api.host` | IP or hostname of the Proxmox host. |
| `proxmox_api.user` | Proxmox user (e.g., `root@pam`). |
| `proxmox_api.token_name` | API token name (created in Proxmox UI > Datacenter > API Tokens). |
| `proxmox_api.token_value` | API token secret value. |
| `proxmox_api.verify_ssl` | `true` (default) to verify SSL certificates, `false` to skip. |

::: tip
Create a dedicated API token with minimal permissions (VM.Audit + VM.Config.CPU + VM.Config.Memory) rather than using root credentials.
:::

### Environment variable expansion (v2.0)

All string values in the YAML config support `${ENV_VAR}` and `${ENV_VAR:-default}` syntax:

```yaml
DEFAULT:
  ssh_password: ${SSH_PASSWORD}
  proxmox_api:
    token_value: ${PROXMOX_TOKEN:-not-set}
```

Additionally, these environment variables override specific config keys directly:

- `LXC_AUTOSCALE_SSH_PASSWORD` → `ssh_password`
- `LXC_AUTOSCALE_SMTP_PASSWORD` → `smtp_password`
- `LXC_AUTOSCALE_GOTIFY_TOKEN` → `gotify_token`
- `LXC_AUTOSCALE_UPTIME_KUMA_WEBHOOK` → `uptime_kuma_webhook_url`
