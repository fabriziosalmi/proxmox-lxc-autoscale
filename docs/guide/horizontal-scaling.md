# Horizontal Scaling

::: warning Experimental
Horizontal scaling is an experimental feature. Test thoroughly in a non-production environment before using it in production.
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
2. **Scale out** — If averages exceed the upper thresholds, a new container is cloned from the base snapshot.
3. **Scale in** — If averages drop below the lower thresholds and the group has more than `min_containers`, the last clone is stopped.
4. **Grace periods** — Scale-out and scale-in actions are throttled by configurable grace periods.

## Parameters

| Parameter | Description |
|-----------|-------------|
| `base_snapshot_name` | Container ID to use as the clone source. |
| `min_instances` | Minimum number of containers in the group. |
| `max_instances` | Maximum number of containers (clones stop here). |
| `starting_clone_id` | First container ID for new clones. |
| `clone_network_type` | `"dhcp"` or `"static"`. |
| `static_ip_range` | List of IPs for static assignment. Leave `[]` for DHCP. |
| `horiz_cpu_upper_threshold` | Group avg CPU % to trigger scale-out. |
| `horiz_memory_upper_threshold` | Group avg memory % to trigger scale-out. |
| `horiz_cpu_lower_threshold` | Group avg CPU % to trigger scale-in. |
| `horiz_memory_lower_threshold` | Group avg memory % to trigger scale-in. |
| `scale_out_grace_period` | Minimum seconds between scale-out actions. |
| `scale_in_grace_period` | Minimum seconds between scale-in actions. |

## Use case

A web server container group that experiences traffic spikes: when average CPU exceeds 95%, a clone is created and started automatically. When traffic drops, excess clones are stopped.
