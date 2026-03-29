# Tier Snippets for Self-Hosted Apps

Ready-to-use tier configurations for 40 popular self-hosted applications. Copy the relevant block into your `/etc/lxc_autoscale/lxc_autoscale.yaml` file and replace `999` with your actual container ID.

::: info
Tier sections must be placed **after** the `DEFAULT` section in the configuration file. Tier settings override the defaults for their assigned containers.
:::

## Heavy workloads (4-8 cores)

### Nextcloud

```yaml
TIER_NEXTCLOUD:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048
  max_memory: 16384
  lxc_containers:
    - "999"
```

### Jellyfin

```yaml
TIER_JELLYFIN:
  cpu_upper_threshold: 90
  cpu_lower_threshold: 25
  memory_upper_threshold: 90
  memory_lower_threshold: 25
  min_cores: 4
  max_cores: 8
  min_memory: 4096
  max_memory: 16384
  lxc_containers:
    - "999"
```

### Plex

```yaml
TIER_PLEX:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048
  max_memory: 16384
  lxc_containers:
    - "999"
```

### GitLab

```yaml
TIER_GITLAB:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 4
  max_cores: 8
  min_memory: 4096
  max_memory: 16384
  lxc_containers:
    - "999"
```

### PhotoPrism

```yaml
TIER_PHOTOPRISM:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048
  max_memory: 8192
  lxc_containers:
    - "999"
```

### OpenProject / Redmine / Rocket.Chat / Seafile / MediaGoblin / Diaspora

```yaml
TIER_HEAVY_APP:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048
  max_memory: 8192
  lxc_containers:
    - "999"
```

## Medium workloads (2-4 cores)

### Mattermost / Matomo / Nextcloud Talk

```yaml
TIER_MEDIUM_APP:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 4
  min_memory: 2048
  max_memory: 8192
  lxc_containers:
    - "999"
```

### Home Assistant

```yaml
TIER_HOME_ASSISTANT:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 4
  min_memory: 1024
  max_memory: 4096
  lxc_containers:
    - "999"
```

### Grafana / Bitwarden / Gitea / Limesurvey

```yaml
TIER_STANDARD_APP:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 4
  min_memory: 512
  max_memory: 2048
  lxc_containers:
    - "999"
```

### Ghost / Trilium Notes / MediaWiki / BookStack / Paperless / Ampache / Etherpad / Invoice Ninja

```yaml
TIER_MIDRANGE_APP:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 2
  max_cores: 4
  min_memory: 1024
  max_memory: 4096
  lxc_containers:
    - "999"
```

## Lightweight workloads (1-2 cores)

### Uptime Kuma / Pi-hole / Miniflux / Vaultwarden / Kanboard / Wallabag / Paperwork / Tiny Tiny RSS / Shaarli / FreshRSS / Firefly III / Monica / Listmonk

```yaml
TIER_LIGHTWEIGHT_APP:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 2
  min_memory: 512
  max_memory: 1024
  lxc_containers:
    - "999"
```

## Customization tips

- Adjust `cpu_upper_threshold` lower (e.g. 70) for faster scale-up response on latency-sensitive apps.
- On hybrid Intel CPUs, add `cpu_pinning: p-cores` to heavy tiers and `cpu_pinning: e-cores` to lightweight ones. See [CPU Core Pinning](/guide/cpu-pinning).
- Group multiple containers of the same type into a single tier by adding all their IDs to `lxc_containers`.
