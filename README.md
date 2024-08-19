# LXC AutoScale

**LXC AutoScale** is a powerful and flexible resource management daemon specifically designed for Proxmox environments. It automatically adjusts CPU and memory allocations and can clone LXC containers based on real-time usage metrics and predefined thresholds. This ensures that your containers are always optimized for performance, managing spikes in demand, and optionally preserving resources during off-peak hours. 

**✅ Tested on `Proxmox 8.2.4`**

---

LXC AutoScale offers two distinct options to suit different user profiles and environments:

- **LXC AutoScale**: Ideal for new users and straightforward setups. This version provides a simple, out-of-the-box solution that automatically manages the resources of your Proxmox LXC containers. You can reconfigure it at any time or use it as a one-time solution when needed.

- **LXC AutoScale ML**: Designed for advanced users and more complex environments. This version is perfect for large automated setups or custom integrations requiring sophisticated, machine-learning-driven autoscaling. It consists of three components: the **API**, the **Monitor**, and the **Model**.

> [!NOTE]
> The default installer automatically installs LXC AutoScale after a 5-second delay.


## Features
LXC AutoScale is packed with features that make it an essential tool for managing your LXC containers on Proxmox:

- ⚙️ Automatic Resource Scaling
- ⚖️ Automatic Horizontal Scaling
- 📊 Tier Defined Thresholds
- 🛡️ Host Resource Reservation
- 🔒 Ignore Scaling Option
- 🌱 Energy Efficiency Mode
- 🚦 Container Prioritization
- 📦 Automatic Backups
- 🔔 Mail and Push Notifications
- 📈 JSON Metrics

### Additional resources
- 🎛️ [LXC AutoScale - TIER snippets for 40 self-hosted apps](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/examples/README.md)
- ⏰ [LXC AutoScale API - Cron jobs examples](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale_api/examples/README.md)
## Installation

Getting started with LXC AutoScale is quick and simple. The easiest way to install (or update) the service is by using the following `curl` command:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

Once installed, the service should be up and running. You can verify this by executing:

```bash
systemctl status lxc_autoscale.service
```

If the conditions set in the configuration are met, you will quickly observe scaling operations in action.


## Configuration

LXC AutoScale is designed to be highly customizable. You can reconfigure the service at any time to better suit your specific needs. For detailed instructions on how to adjust the settings, please refer to the **[official documentation](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/README.md)**.

## Contributing

LXC AutoScale is an open-source project, and contributions are welcome! Whether you want to submit a pull request, report an issue, or suggest a new feature, your input is invaluable. To get involved, you can:

- Submit a pull request to the repository.
- [Open an issue](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/new/choose) to report bugs or request new features.
- Fork the repository to experiment and develop your custom features.

For more details, visit the [GitHub repository](https://github.com/fabriziosalmi/proxmox-lxc-autoscale).

## Disclaimer

> [!CAUTION]
> Please note that while LXC AutoScale is designed to enhance your container management experience, I am not responsible for any potential damage or issues that may arise from using this tool. Always test new configurations in a controlled environment before applying them to production systems.

## License

LXC AutoScale is licensed under the MIT License, which means you are free to use, modify, and distribute this software with proper attribution. For more details, please see the [LICENSE](LICENSE) file.
