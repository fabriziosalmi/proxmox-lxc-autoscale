# Function to install LXC AutoScale
install_lxc_autoscale() {
    log "INFO" "Installing LXC AutoScale..."

    # Create necessary directories
    mkdir -p /etc/lxc_autoscale
    mkdir -p /usr/local/bin/lxc_autoscale

    # Download and install the configuration file
    curl -sSL -o /etc/lxc_autoscale/lxc_autoscale.yaml https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale.yaml

    # Download and install all Python files in the lxc_autoscale directory
    curl -sSL -o /usr/local/bin/lxc_autoscale/config.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/config.py
    curl -sSL -o /usr/local/bin/lxc_autoscale/logging_setup.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/logging_setup.py
    curl -sSL -o /usr/local/bin/lxc_autoscale/lock_manager.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lock_manager.py
    curl -sSL -o /usr/local/bin/lxc_autoscale/lxc_utils.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_utils.py
    curl -sSL -o /usr/local/bin/lxc_autoscale/notification.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/notification.py
    curl -sSL -o /usr/local/bin/lxc_autoscale/resource_manager.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/resource_manager.py
    curl -sSL -o /usr/local/bin/lxc_autoscale/scaling_manager.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/scaling_manager.py
    curl -sSL -o /usr/local/bin/lxc_autoscale/main.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale.py

    # Download and install the systemd service file
    curl -sSL -o /etc/systemd/system/lxc_autoscale.service https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale.service

    # Make the main script executable
    chmod +x /usr/local/bin/lxc_autoscale/main.py

    # Reload systemd to recognize the new service
    systemctl daemon-reload
    systemctl enable lxc_autoscale.service

    # Automatically start the service after installation
    if systemctl start lxc_autoscale.service; then
        log "INFO" "${CHECKMARK} Service LXC AutoScale started successfully!"
    else
        log "ERROR" "${CROSSMARK} Failed to start Service LXC AutoScale."
    fi
}
