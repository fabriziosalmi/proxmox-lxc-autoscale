# CPU Core Pinning

LXC AutoScale can pin containers to a subset of the host's CPUs. Groups are auto-detected from the kernel, so a tier can say "run this on one CCD" without hard-coding CPU numbers that change when the node is replaced.

## Why pin cores?

Two different reasons, depending on the host.

**Asymmetric cores.** Hybrid Intel CPUs (Alder Lake, Raptor Lake, Arrow Lake, 12th gen and newer) mix P-cores (higher clock, latency-sensitive work) with E-cores (lower power, background work). Pinning puts each workload on the core type that suits it.

**Cache and memory locality.** On AMD (and on multi-socket hosts of either vendor), the cost is not core speed but distance. A Ryzen or EPYC package is built from several CCDs, each with its own L3 slice. A thread that migrates across CCDs loses its L3 working set and pays Infinity Fabric latency to reach the other side. Confining a container to one L3 domain, or to one NUMA node, keeps its cache warm and its memory local.

## Configuration

Add `cpu_pinning` to any tier block:

```yaml
TIER_databases:
  lxc_containers:
    - "102"
  cpu_pinning: l3:0          # Confine to the first L3 domain (CCD 0 on AMD)
  min_cores: 2
  max_cores: 8
  min_memory: 4096

TIER_background:
  lxc_containers:
    - "105"
    - "106"
  cpu_pinning: l3:1          # Keep noisy neighbours off the database's cache
  max_cores: 4
  min_memory: 512
```

## Accepted values

| Value | Availability | Description |
|-------|--------------|-------------|
| `l3:0`, `l3:1`, … | Any CPU | One L3 cache domain. On AMD this is a CCD/CCX; on most Intel server parts the whole package shares one L3, so only `l3:0` exists. Numbered from the lowest CPU id upward. |
| `numa:0`, `numa:1`, … | Any CPU | One NUMA node, numbered by its kernel node id. Multi-socket hosts and EPYC in NPS2/NPS4 expose more than one. |
| `p-cores` | Hybrid Intel only | Performance cores. |
| `e-cores` | Hybrid Intel only | Efficiency cores. |
| `all` | Any CPU | Every online CPU, from `/sys/devices/system/cpu/online`. No effective restriction. |
| `0-11` | Any CPU | Explicit CPU range. |
| `0,2,4,6-8` | Any CPU | Explicit CPU list with ranges. |

Values are case-insensitive.

## How detection works

At first use the daemon runs a single probe on the host (over SSH when `use_remote_proxmox` is set) and reads three things.

- `/sys/devices/system/cpu/cpu*/topology/core_type` classifies each CPU as `Core` or `Atom`. This attribute is populated only for CPUs the kernel marks as hybrid, which today means Intel 12th gen and newer. It is absent on every AMD host, so `p-cores` and `e-cores` are not offered there.
- `/sys/devices/system/cpu/cpu*/cache/index3/shared_cpu_list` groups CPUs by the L3 they share. This is generic sysfs and is present on both vendors.
- `/sys/devices/system/node/node*/cpulist` gives the NUMA nodes. A node with no CPUs of its own, such as a CXL or persistent-memory node, is not offered as a group.

The result is logged once, and it is the fastest way to see what a given node offers:

```
CPU topology: 32 CPUs, hybrid P/E cores: none; L3 domains: l3:0=0-7,16-23 (32768K), l3:1=8-15,24-31 (32768K); NUMA: numa:0=0-31
```

On a hybrid Intel node the same line reads:

```
CPU topology: 20 CPUs, hybrid P/E cores: 0-11 / 12-19; L3 domains: l3:0=0-19 (24576K); NUMA: numa:0=0-19
```

If a tier asks for `p-cores` or `e-cores` on a host that reports no hybrid cores, the daemon logs a warning naming the groups that host does have and does not write a pin. It does not silently pin the container to every core.

::: warning
Not writing a pin is not the same as removing one. If the container config already carries an `lxc.cgroup2.cpuset.cpus` line, from an earlier release or a previous `cpu_pinning` value, that line stays in force. Change `cpu_pinning` to a value the host can resolve, or delete the line from `/etc/pve/lxc/<ctid>.conf` yourself.
:::

::: tip Picking the right CCD on an X3D part
On a Ryzen X3D chip only one CCD carries the extra V-Cache, and the two CCDs report different L3 sizes. The startup line above prints the size of each domain, so the larger one is the V-Cache CCD.
:::

## How pinning is applied

Pinning writes `lxc.cgroup2.cpuset.cpus` to the container's configuration file at `/etc/pve/lxc/<ctid>.conf`. This is checked and maintained on every scaling cycle.

- If the pinning is already set correctly, no write occurs.
- If the container config has a different pinning, it is updated.
- If no pinning exists yet, the line is appended.

::: warning
Pinning restricts which physical CPUs a container's vCPUs can be scheduled on. The `cores` setting (number of vCPUs) is independent. A container can have 2 vCPUs pinned to an 8-core L3 domain.
:::

## Example: AMD Ryzen, two CCDs

A 16-core part with two 8-core CCDs, SMT on, so CPUs 0-7 and 16-23 share one L3 and 8-15 and 24-31 share the other.

```yaml
# Latency-sensitive: databases, web servers. Own CCD, own L3.
TIER_performance:
  lxc_containers:
    - "100"
    - "101"
  cpu_pinning: l3:0
  max_cores: 8

# Background: backups, monitoring, CI runners. The other CCD.
TIER_background:
  lxc_containers:
    - "110"
    - "111"
    - "112"
  cpu_pinning: l3:1
  max_cores: 4
```

## Example: dual-socket EPYC

Keep each tier's memory accesses local to one socket.

```yaml
TIER_socket0:
  lxc_containers:
    - "200"
  cpu_pinning: numa:0

TIER_socket1:
  lxc_containers:
    - "201"
  cpu_pinning: numa:1
```

## Example: Intel i5-13500

A 13th Gen Intel i5-13500 has 6 P-cores (12 threads) and 8 E-cores.

```yaml
TIER_performance:
  lxc_containers:
    - "100"
  cpu_pinning: p-cores    # Cores 0-11
  max_cores: 6

TIER_background:
  lxc_containers:
    - "110"
  cpu_pinning: e-cores    # Cores 12-19
  max_cores: 4
```
