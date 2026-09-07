# CPU Core Pinning

::: danger Pinning turns off CPU scaling for that tier
Proxmox derives a container's CPU affinity from its `cores` value **only when the
configuration carries no explicit `cpuset` line**. Setting `cpu_pinning` writes one,
so from the container's next start `cores` no longer controls anything: the daemon
goes on computing increments and logging "Increase Cores" for a value the hypervisor
has stopped reading. Verified on Proxmox VE 9.1 with `cores: 1` and a pin of `0-1`,
where the container reported two CPUs after a restart.

Use `cpu_pinning` **or** CPU scaling on a given tier, not both.
:::

::: warning `l3:0` and `numa:0` are often not a restriction
On a single-socket host with one L3 domain and one NUMA node, which is most
machines, both resolve to every online CPU. That is the same as `all`, and no
warning is emitted. Check the logged line before assuming a pin is confining
anything.
:::

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

An explicit range is checked against the host before it is written. A reversed
range (`31-0`), a CPU past the end of the host (`0-999` on a 32-CPU node) or one
that is offline is refused with a message naming what the host does have, and
nothing is pinned. The kernel rejects a cpuset like that, LXC then cannot set up
the cgroup, and the container does not start: a typo in a tier should cost that
tier its pinning, not its container. Membership is only checked when the
topology probe succeeded; a reversed range is refused either way.

Ranges are written in canonical form, so `4,2,0` is stored as `0,2,4` and
`0,0,0,0` as `0`. The CPUs pinned are the same, and the line logged says so.

## How detection works

At first use the daemon runs a single probe on the host (over SSH when `use_remote_proxmox` is set) and reads three things.

- `/sys/devices/cpu_core/cpus` and `/sys/devices/cpu_atom/cpus` list the members of each core type. On a hybrid part the kernel registers one perf PMU per core type, named `cpu_core` and `cpu_atom`, and gives each a `cpus` attribute; a uniform CPU has a single PMU at `/sys/devices/cpu` and neither directory exists. Their presence is therefore the hybrid signal, and their absence is why `p-cores` and `e-cores` are not offered on most hosts. This is the same interface the `perf` tool uses, and it needs `CONFIG_PERF_EVENTS`, which Proxmox kernels set.
- `/sys/devices/system/cpu/cpu*/cache/index*/level`, matched on level 3, groups CPUs by the L3 they share through the matching `shared_cpu_list`. This is generic sysfs and is present on both vendors. The level is read rather than assuming `index3`, because the index depends on which cache levels the CPU reports.
- `/sys/devices/system/node/node*/cpulist` gives the NUMA nodes. A node with no CPUs of its own, such as a CXL or persistent-memory node, is not offered as a group.

::: warning `l3:N` is positional, `numa:N` is not
NUMA groups carry the kernel's own node id, so `numa:1` means the same node across reboots. L3 groups have no kernel-assigned number, so they are numbered here by their lowest CPU: `l3:0` is the domain containing CPU 0, `l3:1` the next, and so on. If the set of online CPUs changes, for instance because a whole CCD is taken offline, the numbering shifts and a tier configured for `l3:1` pins to a different domain without any error. The line described below prints the members of each group; check it after any change to the host's CPU configuration.
:::

The result is logged once, the first time a tier asks for a pinning group, not at startup. A host with no tier setting `cpu_pinning` never logs it at all. It is the fastest way to see what a given node offers:

```
CPU topology: 32 CPUs online, hybrid P/E cores: none; L3 domains: l3:0=0-7,16-23 (32768K), l3:1=8-15,24-31 (32768K); NUMA: numa:0=0-31
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
On a Ryzen X3D chip only one CCD carries the extra V-Cache, and the two CCDs report different L3 sizes. The line above prints the size of each domain, so the larger one is the V-Cache CCD.
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
