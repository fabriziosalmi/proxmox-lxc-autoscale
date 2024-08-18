# LXC AutoScale 

**LXC AutoScale** is a powerful resource management daemon designed to automatically adjust CPU and memory allocations, as well as clone LXC containers on Proxmox hosts based on current usage and predefined thresholds. It optimizes resource utilization, manages spikes in demand, and ensures that critical containers have the necessary resources. Additionally, it can (optionally) help save energy during off-peak hours. The autoscaling logic is highly customizable, offering a wide range of granular options to fit seamlessly into existing setups and meet specific requirements.

✅ Tested on `Proxmox 8.2.4`

### _LXC AutoScale, with or without AI ?_

- **LXC AutoScale** is the ideal choice for new users. It's straightforward: install, run, and let it handle the rest by automatically scaling the resources of your Proxmox LXC containers. You can easily reconfigure it to fit your setup at any time or use it as a one-time solution when needed.

- **LXC AutoScale ML** is a more advanced option, designed for large automated environments or custom integrations. This solution comprises three services: LXC AutoScale API, LXC Monitor, and LXC AutoScale ML. It is intended for scenarios where more sophisticated, machine learning-driven autoscaling is required. The LXC Monitor logs resource usage data, which is then used by a machine learning model pipeline to train and suggest scaling decisions. These decisions can optionally be sent to the API for automated application. As with any ML-based system, the more data it gathers, the more accurate its predictions become. Users also have access to several customizable options to tailor the solution to their needs.


> [!NOTE]
> The current installer wait 5 seconds and then automatically install the **LXC AutoScale** standard version.

## Features

- ⚙️ **Automatic Resource Scaling:** Dynamically adjust CPU and memory based on usage thresholds.
- ⚖️ **Automatic Horizontal Scaling:** Dynamically clone your LXC containers based on usage thresholds.
- 📊 **Tier Defined Thresholds:** Set specific thresholds for one or more LXC containers.
- 🛡️ **Host Resource Reservation:** Ensure that the host system remains stable and responsive.
- 🔒 **Ignore Scaling Option:** Ensure that one or more LXC containers are not affected by the scaling process.
- 🌱 **Energy Efficiency Mode:** Reduce resource allocation during off-peak hours to save energy.
- 🚦 **Container Prioritization:** Prioritize resource allocation based on resource type.
- 📦 **Automatic Backups:** Backup and rollback container configurations.
- 🔔 **Gotify Notifications:** Optional integration with Gotify for real-time notifications.
- 📈 **JSON metrics:** Collect all resources changes across your autoscaling fleet. 

## Installation

The easiest way to install (and update) LXC AutoScale is by using the following `curl` command:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

Now the service should be running. You can check it by executing `systemctl status lxc_autoscale.service` and if some condition is reached you will quickly see scaling operations. 

### Configuration

You can reconfigure the service any time by editing the `/etc/lxc_autoscale/lxc_autoscale.yaml` configuration file.
Please check the [documentation](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale.md).

## Disclaimer

> [!CAUTION]
> Initial version can be bugged, use at your own risk. I am not responsible for any damage to your lovely stuff by using this tool.

## Contributing

If you would like to contribute to the development of LXC AutoScale, feel free to submit a pull request or [open an issue](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/new/choose) on the [GitHub repository](https://github.com/fabriziosalmi/proxmox-lxc-autoscale).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
