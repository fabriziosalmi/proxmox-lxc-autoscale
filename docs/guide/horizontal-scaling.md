# Horizontal Scaling

::: warning Experimental
Horizontal scaling is an experimental feature. Test thoroughly in a non-production environment before using it in production.
:::

::: danger Known defects, verified on a live node
Group membership is held in memory and never persisted. After a daemon restart the
group no longer knows about the clones it created, so it recomputes the next clone
id from the members listed in the YAML and arrives at an id that is already in use.
`pct clone` then fails, and it fails again on **every** poll: the grace period is
recorded only after a successful scale-out, so nothing throttles the retry.

Each attempt takes an LVM snapshot of the source container before cloning, and
nothing removes it when the clone fails. Four accumulated in ninety seconds of
retrying during testing; at the default five-minute interval that is **288 snapshots
per day on the source container, growing without bound**, on thin-provisioned
storage. No code prunes them.

Scale-in also stops the last container without destroying it, so ids are never
released.

Pilot this on a node where you are watching it, and check
`pct listsnapshot <source>` after the first restart.
:::

Horizontal scaling clones containers when group-level resource usage exceeds thresholds, and removes clones when usage drops.

## Configuration

```yaml
HORIZONTAL_SCALING_GROUP_1:
  base_snapshot_name: "101"
  min_instances: 2
  max_instances: 5
  starting_clone_id: 99000
  clone_network_type: "static"   # "static" or "dhcp"
  static_ip_range:
    - "192.168.100.195"
    - "192.168.100.200"
  horiz_cpu_upper_threshold: 95
  horiz_memory_upper_threshold: 95
  horiz_cpu_lower_threshold: 30
  horiz_memory_lower_threshold: 30
  scale_out_grace_period: 300    # seconds between scale-out actions
  scale_in_grace_period: 600     # seconds between scale-in actions
  lxc_containers:
    - "101"
```

## How it works

1. **Metrics** — Average CPU and memory usage are calculated across all containers in the group.
2. **Scale out** — If averages exceed the upper thresholds, a new container is cloned from the base snapshot. With `clone_network_type: static` the address is chosen before the clone, by reading the addresses actually configured on the existing members and taking the first free entry of `static_ip_range`. If every address is taken, the scale-out is skipped and logged, and no clone is created.
3. **Scale in** — If averages drop below the lower thresholds and the group has more than `min_instances`, the last clone is stopped.
4. **Grace periods** — Scale-out and scale-in actions are throttled by configurable grace periods.

## Parameters

| Parameter | Description |
|-----------|-------------|
| `base_snapshot_name` | Container ID to use as the clone source. |
| `min_instances` | Minimum number of containers in the group. Never scales below this. |
| `max_instances` | Maximum number of containers (clones stop here). |
| `min_containers` | Deprecated alias for `min_instances`. Still honoured, logs a warning at startup. |
| `starting_clone_id` | First container ID for new clones. |
| `clone_network_type` | `"dhcp"` or `"static"`. |
| `static_ip_range` | List of IPs for static assignment. Leave `[]` for DHCP. An entry may carry its own prefix (`10.0.0.5/16`); bare addresses default to `/24`. |
| `horiz_cpu_upper_threshold` | Group avg CPU % to trigger scale-out. |
| `horiz_memory_upper_threshold` | Group avg memory % to trigger scale-out. |
| `horiz_cpu_lower_threshold` | Group avg CPU % to trigger scale-in. |
| `horiz_memory_lower_threshold` | Group avg memory % to trigger scale-in. |
| `scale_out_grace_period` | Minimum seconds between scale-out actions. |
| `scale_in_grace_period` | Minimum seconds between scale-in actions. |

## Use case

A web server container group that experiences traffic spikes: when average CPU exceeds 95%, a clone is created and started automatically. When traffic drops, excess clones are stopped.
