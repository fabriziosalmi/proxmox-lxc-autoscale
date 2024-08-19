# LXC AutoScale

Welcome to the documentation for **LXC AutoScale**.

LXC AutoScale is a resource management daemon specifically designed for Proxmox environments. It automatically adjusts CPU and memory allocations and can clone LXC containers based on real-time usage metrics and predefined thresholds. Can be run locally or remotely to make your containers always optimized for performance, managing spikes in demand, and optionally preserving resources during off-peak hours.

LXC AutoScale offers two distinct options to suit different user profiles and environments:

## 🚀 LXC AutoScale
The default install option: ideal for new users and straightforward setups. This version provides a simple, out-of-the-box solution that automatically scale the resources of your Proxmox LXC containers. You can reconfigure it at any time or use it as a one-time solution when needed.

- [LXC AutoScale Documentation](lxc_autoscale/README.md)

---

## ✨ LXC AutoScale ML
Designed for more complex environments, this version can be easily extended to fit large automated setups or custom integrations requiring machine-learning-driven autoscaling. It consists of three components: the API, the Monitor, and the Model.

- [LXC AutoScale API documentation](lxc_autoscale_api/README.md)
- [LXC Monitor documentation](lxc_monitor/README.md)
- [LXC AutoScale ML documentation](lxc_model/README.md)

--- 

#### Additional resources

- [Q&A](q%26a/README.md)
