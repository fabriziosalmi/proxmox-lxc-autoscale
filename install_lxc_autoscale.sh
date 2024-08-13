#!/bin/bash

# Variables
SCRIPT_URL="https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/usr/local/bin/lxc_autoscale.py"
SERVICE_URL="https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/etc/systemd/system/lxc_autoscale.service"
INSTALL_PATH="/usr/local/bin/lxc_autoscale.py"
SERVICE_PATH="/etc/systemd/system/lxc_autoscale.service"
LOG_PATH="/var/log/lxc_autoscale.log"
BACKUP_DIR="/var/lib/lxc_autoscale/backups"

# Download the Python script
echo "📥 Downloading the LXC AutoScale script..."
curl -o $INSTALL_PATH $SCRIPT_URL
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to download the script."
    exit 1
fi

# Make the script executable
chmod +x $INSTALL_PATH

# Download the systemd service file
echo "📥 Downloading the systemd service file..."
curl -o $SERVICE_PATH $SERVICE_URL
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to download the service file."
    exit 1
fi

# Set up directories for logs and backups
echo "📂 Setting up directories..."
mkdir -p $(dirname $LOG_PATH)
mkdir -p $BACKUP_DIR

# Set the correct permissions
echo "🔧 Setting permissions..."
chown root:root $LOG_PATH
chown -R root:root $BACKUP_DIR
chmod 755 $BACKUP_DIR
chmod 644 $LOG_PATH

# Reload systemd to recognize the new service
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start the LXC AutoScale service
echo "🚀 Enabling and starting the service..."
systemctl enable lxc_autoscale.service
systemctl start lxc_autoscale.service

# Check the status of the service
echo "🔍 Checking service status..."
systemctl status lxc_autoscale.service --no-pager

# Verify that the service is running
if systemctl is-active --quiet lxc_autoscale.service; then
    echo "✅ LXC AutoScale service is running successfully."
else
    echo "❌ Error: LXC AutoScale service failed to start."
    exit 1
fi

echo "🎉 Installation and setup completed successfully."
