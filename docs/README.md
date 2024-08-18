# LXC AutoScale

Welcome to the documentation for **LXC AutoScale**—a powerful and customizable resource management daemon for Proxmox hosts. LXC AutoScale automates CPU and memory allocation adjustments and clones LXC containers based on real-time usage and predefined thresholds. Designed to optimize resource utilization and manage demand spikes, it ensures critical containers always have the necessary resources. The tool also offers energy efficiency during off-peak hours and integrates seamlessly into various environments.

## Key Features

- **Automatic Resource Scaling**
- **Horizontal Scaling**
- **Energy Efficiency Mode**
- **Container Prioritization**
- **Automatic Backups**
- **JSON Metrics & Gotify Notifications**

## LXC AutoScale Variants

### LXC AutoScale

Perfect for new users, this variant is easy to set up and manage. Simply install, run, and let it automatically handle the scaling of your LXC containers. It can be reconfigured at any time to suit your specific environment.

### LXC AutoScale ML

A more advanced option, designed for large, automated environments or custom integrations, LXC AutoScale ML utilizes machine learning to enhance scaling decisions. It includes three services: LXC AutoScale API, LXC Monitor, and LXC AutoScale ML, offering a robust solution for complex setups.


## Documentation

- [LXC AutoScale](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale.md)
- [LXC AutoScale ML](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale_ml.md)
  - [API](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale_api.md)
  - [Monitor](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_monitor.md)
  - [Model](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_model.md)
