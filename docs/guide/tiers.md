# Tiers

Tiers allow you to apply different scaling rules to groups of containers. Each tier overrides the global `DEFAULT` settings for its assigned containers.

## Defining a tier

Add a `TIER_<name>` section to the YAML config file, listing the container IDs and the desired thresholds:

```yaml
TIER_webservers:
  lxc_containers:
    - "102"
    - "103"
  cpu_upper_threshold: 70
  cpu_lower_threshold: 20
  memory_upper_threshold: 80
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 4096
  core_min_increment: 1
  core_max_increment: 2
  memory_min_increment: 1024
  min_decrease_chunk: 1024
```

## How tiers work

- On each polling cycle, the daemon looks up each container's tier configuration from `LXC_TIER_ASSOCIATIONS`.
- If a container is listed in a `TIER_*` section, that tier's settings are used.
- If no tier is found, the `DEFAULT` settings apply.
- A container can only belong to one tier.

## Available tier settings

All settings from the [Configuration](/guide/configuration) page can be overridden per tier:

| Setting | Description |
|---------|-------------|
| `cpu_upper_threshold` | Scale up CPU when usage exceeds this %. |
| `cpu_lower_threshold` | Scale down CPU when usage drops below this %. |
| `memory_upper_threshold` | Scale up memory when usage exceeds this %. |
| `memory_lower_threshold` | Scale down memory when usage drops below this %. |
| `min_cores` / `max_cores` | Bounds on CPU core allocation. |
| `min_memory` | Minimum memory in MB. |
| `core_min_increment` / `core_max_increment` | Cores added per scale-up step. |
| `memory_min_increment` | MB added per memory scale-up step. |
| `min_decrease_chunk` | MB removed per memory scale-down step. |
| `cpu_pinning` | Pin containers to specific CPU cores. See [CPU Core Pinning](/guide/cpu-pinning). |

## Example: multi-tier setup

```yaml
DEFAULT:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 20
  min_cores: 1
  max_cores: 4
  min_memory: 256

TIER_databases:
  lxc_containers:
    - "100"
    - "101"
  cpu_upper_threshold: 70
  min_cores: 2
  max_cores: 8
  min_memory: 4096

TIER_lightweight:
  lxc_containers:
    - "110"
    - "111"
  cpu_upper_threshold: 90
  max_cores: 2
  min_memory: 128
```

::: tip
For ready-to-use tier configurations, check the [Tier Snippets](/reference/tier-snippets) with 40 presets for popular self-hosted applications.
:::
