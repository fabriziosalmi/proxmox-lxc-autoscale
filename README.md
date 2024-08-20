# LXC AutoScale

**LXC AutoScale** is a resource management daemon specifically designed for Proxmox environments. It automatically adjusts CPU and memory allocations and can clone LXC containers based on real-time usage metrics and predefined thresholds. Can be run locally or remotely to make your containers always optimized for performance, managing spikes in demand, and optionally preserving resources during off-peak hours. 

**✅ Tested on `Proxmox 8.2.4`**

[QUICK START](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/README.md#quick-start) - [DOCS](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/README.md)

---

LXC AutoScale offers two distinct options to suit different user profiles and environments:

- **🚀 LXC AutoScale**: ideal for new users and straightforward setups. A simple, out-of-the-box solution that automatically manages the resources of your Proxmox LXC containers. You can reconfigure it at any time or use it as a one-time solution when needed.

- **✨ LXC AutoScale ML**: for advanced users and more complex environments. It consists of three components: the **API**, the **Monitor**, and the **Model** (PoC).

> [!NOTE]
> The default installer automatically installs LXC AutoScale after a 5-second delay.


## Features
LXC AutoScale is packed with features that make it an essential tool for managing the auto-scaling of your LXC containers on Proxmox:

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
- 💻 Local or remote execution
- 💃 Easy autoconf for humans

## Quick Start

Getting started with LXC AutoScale on your Proxmox host is quick and simple:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

> [!TIP]
> Once installed, the service should be up and running. You can verify this by executing:
>
> ```bash
> systemctl status lxc_autoscale.service
> ```

If the conditions set in the configuration are met, you will quickly observe scaling operations in action.


## Configuration

LXC AutoScale is designed to be highly customizable. You can reconfigure the service at any time to better suit your specific needs. For detailed instructions on how to adjust the settings, please refer to the **[official documentation](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/README.md)**.

> [!TIP]
> If You need LXC AutoScale configuration for all your LXC containers You can automatically generate it by running this command:
> ```
> curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale_autoconf.sh | bash
> ```

### Additional resources
LXC AutoScale and LXC AutoScale ML can be used and extended in many ways, here some useful additional resources:

- 🎛️ [LXC AutoScale - TIER snippets for 40 self-hosted apps](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/examples/README.md)
- ⏰ [LXC AutoScale API - Cron jobs examples](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale_api/examples/README.md)
  
## Contributing

LXC AutoScale is an open-source project, and contributions are welcome! Whether you want to submit a pull request, report an issue, or suggest a new feature, your input is invaluable. To get involved, you can:

- [Open an issue](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/new/choose) to report bugs or request new features.
- Submit a pull request to the repository.
- Fork the repository to experiment and develop your custom features.

## Disclaimer

> [!CAUTION]
> I am not responsible for any potential damage or issues that may arise from using this tool. Always test new configurations in a controlled environment before applying them to production systems.

## License

LXC AutoScale is licensed under the MIT License, which means you are free to use, modify, and distribute this software with proper attribution. For more details, please see the [LICENSE](LICENSE) file.
