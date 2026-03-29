# Uninstallation

## Automated

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/uninstall.sh | bash
```

## Manual

```bash
# Stop and disable the service
systemctl disable lxc_autoscale.service
systemctl stop lxc_autoscale.service

# Back up config if needed
# cp -rp /etc/lxc_autoscale/lxc_autoscale.yaml ~/lxc_autoscale.yaml.backup

# Remove all files
rm -f /etc/systemd/system/lxc_autoscale.service
rm -rf /usr/local/bin/lxc_autoscale/
rm -rf /etc/lxc_autoscale/
rm -rf /var/lib/lxc_autoscale/
rm -f /var/log/lxc_autoscale.log
rm -f /var/log/lxc_autoscale.json

# Reload systemd
systemctl daemon-reload
```
