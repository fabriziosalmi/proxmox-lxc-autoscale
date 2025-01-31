# 🚀 LXC AutoScale

**LXC AutoScale** is a resource management daemon specifically designed for Proxmox environments. It automatically adjusts CPU and memory allocations with no downtime and can clone LXC containers based on real-time usage metrics and predefined thresholds. Can be run locally or remotely to make your containers always optimized for performance, managing spikes in demand, and optionally preserving resources during off-peak hours. 

- **✅ Works with `Proxmox 8.3.3`** 

**Quick Start**

| Method           | Instructions                                                                                                   |
|------------------|----------------------------------------------------------------------------------------------------------------|
| 🐳    | [Docker](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/README.md#docker) |
| 🐧    | [no Docker](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/README.md#quick-start) |

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
- 🐳 Docker supported

> [!NOTE]
> If You need to autoscale Virtual Machines resources on Proxmox hosts You will like [this project](https://github.com/fabriziosalmi/proxmox-vm-autoscale).

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

> [!IMPORTANT]
> You need to check your `/lib/systemd/system/lxcfs.service` file for the presence of the `-l` option which makes `loadavg` retrieval working as expected. Here the required configuration:
>
> ```
> [Unit]
> Description=FUSE filesystem for LXC
> ConditionVirtualization=!container
> Before=lxc.service
> Documentation=man:lxcfs(1)
> 
> [Service]
> OOMScoreAdjust=-1000
> ExecStartPre=/bin/mkdir -p /var/lib/lxcfs
> # ExecStart=/usr/bin/lxcfs /var/lib/lxcfs
> ExecStart=/usr/bin/lxcfs /var/lib/lxcfs -l
> KillMode=process
> Restart=on-failure
> ExecStopPost=-/bin/fusermount -u /var/lib/lxcfs
> Delegate=yes
> ExecReload=/bin/kill -USR1 $MAINPID
>
> [Install]
> WantedBy=multi-user.target
> ```
> 
> Just update the `/lib/systemd/system/lxcfs.service` file, execute `systemctl daemon-reload && systemctl restart lxcfs` and when you are ready to apply the fix restart the LXC containers.
> 
> _Tnx to No-Pen9082 to point me out to that. [Here](https://forum.proxmox.com/threads/lxc-containers-shows-hosts-load-average.45724/page-2) the Proxmox forum thread on the topic._

## Configuration

LXC AutoScale is designed to be highly customizable. You can reconfigure the service at any time to better suit your specific needs. For detailed instructions on how to adjust the settings, please refer to the **[official documentation](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/README.md)**.

> [!TIP]
> If You need LXC AutoScale configuration for all your LXC containers You can automatically generate it by running this command:
> ```
> curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale_autoconf.sh | bash
> ```

### Additional resources
LXC AutoScale and LXC AutoScale ML can be used and extended in many ways, here some useful additional resources:

- 🌐 [LXC AutoScale UI - Simple web UI to check scaling actions and logs](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/tree/main/lxc_autoscale/ui)
- 🎛️ [LXC AutoScale - TIER snippets for 40 self-hosted apps](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/blob/main/docs/lxc_autoscale/examples/README.md)

> [!TIP]
> LXC AutoScale ML has been finally moved to a new, separate [repository](https://github.com/fabriziosalmi/proxmox-lxc-autoscale-ml).

## Contributing

LXC AutoScale is an open-source project, and contributions are welcome! Whether you want to submit a pull request, report an issue, or suggest a new feature, your input is invaluable. To get involved, you can:

- [Open an issue](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/new/choose) to report bugs or request new features.
- Submit a pull request to the repository.
- Fork the repository to experiment and develop your custom features.

### ⚠️ Disclaimer
> [!CAUTION]
> The author assumes no responsibility for any damage or issues that may arise from using this tool.

## License

LXC AutoScale is licensed under the MIT License, which means you are free to use, modify, and distribute this software with proper attribution. For more details, please see the [LICENSE](LICENSE) file.
