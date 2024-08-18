# LXC AutoScale

Welcome to the documentation for **LXC AutoScale**—a powerful and customizable resource management daemon for Proxmox hosts. LXC AutoScale automates CPU and memory allocation adjustments and clones LXC containers based on real-time usage and predefined thresholds. Designed to optimize resource utilization and manage demand spikes, it ensures critical containers always have the necessary resources. The tool also offers energy efficiency during off-peak hours and integrates seamlessly into various environments.

**Which version to use?**

### LXC AutoScale
Perfect for new users, this variant is easy to set up and manage. Simply install, run, and let it automatically handle the scaling of your LXC containers. It can be > reconfigured at any time to suit your specific environment.

### [LXC AutoScale Documentation](lxc_autoscale/README.md)

--- 
### LXC AutoScale ML

A more advanced option, designed for large, automated environments or custom integrations, LXC AutoScale ML utilizes machine learning to enhance scaling decisions. It includes three services: LXC AutoScale API, LXC Monitor, and LXC AutoScale ML, offering a robust solution for complex setups.

 - [API documentation](lxc_autoscale_api/README.md)
 - [Monitor documentation](lxc_monitor/README.md)
 - [Model documentation](lxc_model/README.md)
