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

### Remote execution

| Parameter | Description |
|-----------|-------------|
| `use_remote_proxmox` | Set to `true` to execute commands on a remote Proxmox host via SSH. |
| `proxmox_host` | IP or hostname of the remote Proxmox host. |
| `ssh_user` | SSH username. |
| `ssh_password` | SSH password (or use `ssh_key_path` instead). |
| `ssh_key_path` | Path to SSH private key. |
| `ssh_port` | SSH port (default: `22`). |

::: tip
Secrets can be overridden via environment variables: `LXC_AUTOSCALE_SSH_PASSWORD`, `LXC_AUTOSCALE_SMTP_PASSWORD`, `LXC_AUTOSCALE_GOTIFY_TOKEN`, `LXC_AUTOSCALE_UPTIME_KUMA_WEBHOOK`.
:::
