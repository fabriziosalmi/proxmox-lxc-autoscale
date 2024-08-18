# LXC AutoScale

**LXC AutoScale** is a powerful and flexible resource management daemon specifically designed for Proxmox environments. It automatically adjusts CPU and memory allocations and can clone LXC containers based on real-time usage metrics and predefined thresholds. This ensures that your containers are always optimized for performance, managing spikes in demand, and preserving resources during off-peak hours. With a highly customizable autoscaling logic, LXC AutoScale seamlessly integrates into your existing setup, catering to a wide range of requirements—from small homelabs to large-scale automated environments.

**✅ Tested on `Proxmox 8.2.4`**

LXC AutoScale offers two distinct options to suit different user profiles and environments:

- **LXC AutoScale**: Ideal for new users and straightforward setups. This version provides a simple, out-of-the-box solution that automatically manages the resources of your Proxmox LXC containers. It’s easy to install, requires minimal configuration, and works reliably to ensure your containers are always running optimally. You can reconfigure it at any time or use it as a one-time solution when needed.

- **LXC AutoScale ML**: Designed for advanced users and more complex environments. This version is perfect for large automated setups or custom integrations requiring sophisticated, machine-learning-driven autoscaling. It consists of three components: the **API**, the **Monitor**, and the **Model**. Together, these services provide deep insights, automated scaling decisions based on real-time data, and extensive control over your container environment.

> [!NOTE]
> The default installer automatically installs the **LXC AutoScale** standard version after a 5-second delay.


## Features
LXC AutoScale is packed with features that make it an essential tool for managing your LXC containers on Proxmox:

### ⚙️ Automatic Resource Scaling
Dynamically adjusts CPU and memory allocations based on predefined usage thresholds, ensuring that your containers always have the resources they need.

### ⚖️ Automatic Horizontal Scaling
Automatically clones LXC containers when usage thresholds are exceeded, providing additional capacity during peak demand.

### 📊 Tier Defined Thresholds
Allows you to set specific scaling thresholds for individual containers or groups of containers, giving you fine-grained control over resource allocation.

### 🛡️ Host Resource Reservation
Ensures that the Proxmox host remains stable and responsive by reserving a portion of the CPU and memory resources.

### 🔒 Ignore Scaling Option
Excludes specific containers from the scaling process, preventing unintended resource adjustments.

### 🌱 Energy Efficiency Mode
Reduces resource allocations during off-peak hours to conserve energy and reduce operational costs.

### 🚦 Container Prioritization
Prioritizes resource allocation based on container importance, ensuring critical services always have priority access to resources.

### 📦 Automatic Backups
Automatically backs up and allows rollback of container configurations, providing an added layer of safety against unexpected changes.

### 🔔 Gotify Notifications
Optional integration with Gotify for real-time notifications about scaling actions, container status, and other critical events.

### 📈 JSON Metrics
Collects and exports detailed metrics on resource changes across your autoscaling fleet, enabling in-depth analysis and monitoring.


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
