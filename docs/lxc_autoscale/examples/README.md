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
21. [Ghost Configuration](#ghost-configuration)
22. [Miniflux Configuration](#miniflux-configuration)
23. [Trilium Notes Configuration](#trilium-notes-configuration)
24. [Vaultwarden Configuration](#vaultwarden-configuration)
25. [PhotoPrism Configuration](#photoprism-configuration)
26. [Ampache Configuration](#ampache-configuration)
27. [OpenProject Configuration](#openproject-configuration)
28. [Kanboard Configuration](#kanboard-configuration)
29. [Etherpad Configuration](#etherpad-configuration)
30. [MediaGoblin Configuration](#mediagoblin-configuration)
31. [Tiny Tiny RSS Configuration](#tiny-tiny-rss-configuration)
32. [Redmine Configuration](#redmine-configuration)
33. [Seafile Configuration](#seafile-configuration)
34. [Wallabag Configuration](#wallabag-configuration)
35. [Rocket.Chat Configuration](#rocketchat-configuration)
36. [Paperwork Configuration](#paperwork-configuration)
37. [Diaspora Configuration](#diaspora-configuration)
38. [Limesurvey Configuration](#limesurvey-configuration)
39. [Paperless Configuration](#paperless-configuration)
40. [Matomo Configuration](#matomo-configuration)

These internal links make it easy to navigate directly to the relevant configuration within the document.
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
```

### **Ghost Configuration**
```yaml
TIER_GHOST:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 2
  max_cores: 4
  min_memory: 1024  # in MB
  max_memory: 4096  # in MB
  lxc_containers: 
    - 999  # Replace with the Ghost container ID
```

### **Miniflux Configuration**
```yaml
TIER_MINIFLUX:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 2
  min_memory: 512  # in MB
  max_memory: 1024  # in MB
  lxc_containers: 
    - 999  # Replace with the Miniflux container ID
```

### **Trilium Notes Configuration**
```yaml
TIER_TRILIUM_NOTES:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 4
  min_memory: 1024  # in MB
  max_memory: 4096  # in MB
  lxc_containers: 
    - 999  # Replace with the Trilium Notes container ID
```

### **Vaultwarden Configuration**
```yaml
TIER_VAULTWARDEN:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 2
  min_memory: 512  # in MB
  max_memory: 1024  # in MB
  lxc_containers: 
    - 999  # Replace with the Vaultwarden container ID
```

### **PhotoPrism Configuration**
```yaml
TIER_PHOTOPRISM:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048  # in MB
  max_memory: 8192  # in MB
  lxc_containers: 
    - 999  # Replace with the PhotoPrism container ID
```

### **Ampache Configuration**
```yaml
TIER_AMPACHE:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 2
  max_cores: 4
  min_memory: 1024  # in MB
  max_memory: 4096  # in MB
  lxc_containers: 
    - 999  # Replace with the Ampache container ID
```

### **OpenProject Configuration**
```yaml
TIER_OPENPROJECT:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048  # in MB
  max_memory: 8192  # in MB
  lxc_containers: 
    - 999  # Replace with the OpenProject container ID
```

### **Kanboard Configuration**
```yaml
TIER_KANBOARD:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 2
  min_memory: 512  # in MB
  max_memory: 1024  # in MB
  lxc_containers: 
    - 999  # Replace with the Kanboard container ID
```

### **Etherpad Configuration**
```yaml
TIER_ETHERPAD:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 2
  max_cores: 4
  min_memory: 1024  # in MB
  max_memory: 4096  # in MB
  lxc_containers: 
    - 999  # Replace with the Etherpad container ID
```

### **MediaGoblin Configuration**
```yaml
TIER_MEDIAGOBLIN:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048  # in MB
  max_memory: 8192  # in MB
  lxc_containers: 
    - 999  # Replace with the MediaGoblin container ID
```

### **Tiny Tiny RSS Configuration**
```yaml
TIER_TINY_TINY_RSS:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 2
  min_memory: 512  # in MB
  max_memory: 1024  # in MB
  lxc_containers: 
    - 999  # Replace with the Tiny Tiny RSS container ID
```

### **Redmine Configuration**
```yaml
TIER_REDMINE:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048  # in MB
  max_memory: 8192  # in MB
  lxc_containers: 
    - 999  # Replace with the Redmine container ID
```

### **Seafile Configuration**
```yaml
TIER_SEAFILE:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048  # in MB
  max_memory: 8192  # in MB
  lxc_containers: 
    - 999  # Replace with the Seafile container ID
```

### **Wallabag Configuration**
```yaml
TIER_WALLABAG:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 2
  min_memory: 512  # in MB
  max_memory: 1024  # in MB
  lxc_containers: 
    - 999  # Replace with the Wallabag container ID
```

### **Rocket.Chat Configuration**
```yaml
TIER_ROCKETCHAT:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048  # in MB
  max_memory: 8192  # in MB
  lxc_containers: 
    - 999  # Replace with the Rocket.Chat container ID
```

### **Paperwork Configuration**
```yaml
TIER_PAPERWORK:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 2
  min_memory: 512  # in MB
  max_memory: 1024  # in MB
  lxc_containers: 
    - 999  # Replace with the Paperwork container ID
```

### **Diaspora Configuration**
```yaml
TIER_DIASPORA:
  cpu_upper_threshold: 85
  cpu_lower_threshold: 20
  memory_upper_threshold: 85
  memory_lower_threshold: 20
  min_cores: 2
  max_cores: 8
  min_memory: 2048  # in MB
  max_memory: 8192  # in MB
  lxc_containers: 
    - 999  # Replace with the Diaspora container ID
```

### **Limesurvey Configuration**
```yaml
TIER_LIMESURVEY:
  cpu_upper_threshold: 80
  cpu_lower_threshold: 15
  memory_upper_threshold: 80
  memory_lower_threshold: 15
  min_cores: 1
  max_cores: 4
  min_memory: 512  # in MB
  max_memory: 2048  # in MB
  lxc_containers: 
    - 999  # Replace with the Limesurvey container ID
```

Certainly! Here are the configuration snippets for **Paperless** and **Matomo**:

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
