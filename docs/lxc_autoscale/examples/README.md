# **Self-Hosted Apps Configuration Snippets**

## **Introduction**

This collection provides optimized configuration files for popular self-hosted applications, helping you easily manage resource allocation and scaling in your LXC containers. Each configuration snippet is designed to balance minimal and recommended hardware requirements, ensuring efficient and scalable performance for your self-hosted environments.

## **Summary**

Below is a list of available configuration snippets. Click on any link to jump directly to the relevant configuration:

1. [Nextcloud Configuration](#nextcloud-configuration)
2. [Jellyfin Configuration](#jellyfin-configuration)
3. [Plex Configuration](#plex-configuration)
4. [Bitwarden Configuration](#bitwarden-configuration)
5. [Home Assistant Configuration](#home-assistant-configuration)
6. [Grafana Configuration](#grafana-configuration)
7. [GitLab Configuration](#gitlab-configuration)
8. [Mattermost Configuration](#mattermost-configuration)
9. [Gitea Configuration](#gitea-configuration)
10. [Uptime Kuma Configuration](#uptime-kuma-configuration)
11. [MediaWiki Configuration](#mediawiki-configuration)
12. [BookStack Configuration](#bookstack-configuration)
13. [Paperless Configuration](#paperless-configuration)
14. [Matomo Configuration](#matomo-configuration)
15. [Pi-hole Configuration](#pi-hole-configuration)
16. [Ghost Configuration](#ghost-configuration)
17. [Miniflux Configuration](#miniflux-configuration)
18. [Trilium Notes Configuration](#trilium-notes-configuration)
19. [Vaultwarden Configuration](#vaultwarden-configuration)
20. [PhotoPrism Configuration](#photoprism-configuration)

## **Configuration Snippets**

### **Nextcloud Configuration**
```yaml
TIER_NEXTCLOUD:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048  # in MB
  max_memory: 16384  # in MB
  lxc_containers: 
    - 999  # Replace with the Nextcloud container ID
```

### **Jellyfin Configuration**
```yaml
TIER_JELLYFIN:
  cpu_upper_threshold: 90
  cpu_lower_threshold: 25
  memory_upper_threshold: 90
  memory_lower_threshold: 25
  min_cores: 4
  max_cores: 8
  min_memory: 4096  # in MB
  max_memory: 16384  # in MB
  lxc_containers: 
    - 999  # Replace with the Jellyfin container ID
```

### **Plex Configuration**
```yaml
TIER_PLEX:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048  # in MB
  max_memory: 16384  # in MB
  lxc_containers: 
    - 999  # Replace with the Plex container ID
```

### **Bitwarden Configuration**
```yaml
TIER_BITWARDEN:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 4
  min_memory: 512  # in MB
  max_memory: 2048  # in MB
  lxc_containers: 
    - 999  # Replace with the Bitwarden container ID
```

### **Home Assistant Configuration**
```yaml
TIER_HOME_ASSISTANT:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 4
  min_memory: 1024  # in MB
  max_memory: 4096  # in MB
  lxc_containers: 
    - 999  # Replace with the Home Assistant container ID
```

### **Grafana Configuration**
```yaml
TIER_GRAFANA:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 4
  min_memory: 512  # in MB
  max_memory: 2048  # in MB
  lxc_containers: 
    - 999  # Replace with the Grafana container ID
```

### **GitLab Configuration**
```yaml
TIER_GITLAB:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 4
  max_cores: 8
  min_memory: 4096  # in MB
  max_memory: 16384  # in MB
  lxc_containers: 
    - 999  # Replace with the GitLab container ID
```

### **Mattermost Configuration**
```yaml
TIER_MATTERMOST:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 4
  min_memory: 2048  # in MB
  max_memory: 8192  # in MB
  lxc_containers: 
    - 999  # Replace with the Mattermost container ID
```

### **Gitea Configuration**
```yaml
TIER_GITEA:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 4
  min_memory: 512  # in MB
  max_memory: 2048  # in MB
  lxc_containers: 
    - 999  # Replace with the Gitea container ID
```

### **Uptime Kuma Configuration**
```yaml
TIER_UPTIME_KUMA:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 2
  min_memory: 512  # in MB
  max_memory: 1024  # in MB
  lxc_containers: 
    - 999  # Replace with the Uptime Kuma container ID
```

### **MediaWiki Configuration**
```yaml
TIER_MEDIAWIKI:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 2
  max_cores: 4
  min_memory: 1024  # in MB
  max_memory: 4096  # in MB
  lxc_containers: 
    - 999  # Replace with the MediaWiki container ID
```

### **BookStack Configuration**
```yaml
TIER_BOOKSTACK:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 2
  max_cores: 4
  min_memory: 1024  # in MB
  max_memory: 4096  # in MB
  lxc_containers: 
    - 999  # Replace with the BookStack container ID
```

### **Paperless Configuration**
```yaml
TIER_PAPERLESS:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 2
  max_cores: 4
  min_memory: 1024  # in MB
  max_memory: 4096  # in MB
  lxc_containers: 
    - 999  # Replace with the Paperless container ID
```

### **Matomo Configuration**
```yaml
TIER_MATOMO:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 4
  min_memory: 2048  # in MB
  max_memory: 8192  # in MB
  lxc_containers: 
    - 999  # Replace with the Matomo container ID
```

### **Pi-hole Configuration**
```yaml
TIER_PIHOLE:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 2
  min_memory: 512  # in MB
  max_memory: 1024  # in MB
  lxc
