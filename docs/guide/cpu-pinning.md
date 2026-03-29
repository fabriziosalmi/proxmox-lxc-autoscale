# CPU Core Pinning

LXC AutoScale supports pinning containers to specific CPU cores, including automatic detection of Intel hybrid (Big.LITTLE) architectures.

## Why pin cores?

On hybrid Intel CPUs (Alder Lake, Raptor Lake, Arrow Lake — 12th gen and newer), there are two types of cores:

- **P-cores** (Performance) — higher clock speed, suited for latency-sensitive workloads
- **E-cores** (Efficiency) — lower power, suited for background tasks

Pinning containers to the right core type ensures workloads run where they perform best.

## Configuration

Add `cpu_pinning` to any tier block:

```yaml
TIER_databases:
  lxc_containers:
    - "102"
  cpu_pinning: p-cores       # Run on Performance cores
  min_cores: 2
  max_cores: 8
  min_memory: 4096

TIER_background:
  lxc_containers:
    - "105"
    - "106"
  cpu_pinning: e-cores       # Run on Efficiency cores
  max_cores: 4
  min_memory: 512
```

## Accepted values

| Value | Description |
|-------|-------------|
| `p-cores` | Pin to Performance cores (auto-detected). |
| `e-cores` | Pin to Efficiency cores (auto-detected). |
| `all` | No pinning restriction (use all cores). |
| `0-11` | Explicit CPU range. |
| `0,2,4,6-8` | Explicit CPU list with ranges. |

## How detection works

At startup, the daemon reads `/sys/devices/system/cpu/cpu*/topology/core_type` (available on kernel 5.18+):

- `"Core"` — classified as P-core
- `"Atom"` — classified as E-core

On non-hybrid systems, all cores are treated equally and `p-cores`/`e-cores` keywords are not available.

The detected topology is logged at startup:

```
CPU topology: hybrid detected — 12 P-cores (0-11), 8 E-cores (12-19)
```

## How pinning is applied

Pinning writes `lxc.cgroup2.cpuset.cpus` to the container's configuration file at `/etc/pve/lxc/<ctid>.conf`. This is checked and maintained on every scaling cycle.

- If the pinning is already set correctly, no write occurs.
- If the container config has a different pinning, it is updated.
- If no pinning exists yet, the line is appended.

::: warning
Pinning restricts which physical cores a container's vCPUs can be scheduled on. The `cores` setting (number of vCPUs) is independent — a container can have 2 vCPUs pinned to 8 E-cores.
:::

## Example: i5-13500

On a 13th Gen Intel i5-13500 (6 P-cores + 8 E-cores):

```yaml
# Latency-sensitive: databases, web servers
TIER_performance:
  lxc_containers:
    - "100"
    - "101"
  cpu_pinning: p-cores    # Cores 0-11 (P-cores + HT)
  max_cores: 6

# Background: backups, monitoring, CI runners
TIER_background:
  lxc_containers:
    - "110"
    - "111"
    - "112"
  cpu_pinning: e-cores    # Cores 12-19
  max_cores: 4
```
