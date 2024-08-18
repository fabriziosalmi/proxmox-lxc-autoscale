#!/bin/bash

# Ensure the script is run as root
if [ "$(id -u)" -ne 0 ]; then
  echo "🚫 This script must be run as root. Please use sudo or run as root."
  exit 1
fi

# Step 1: Create the necessary directory
echo "📁 Creating directory /usr/local/bin/lxc_autoscale_api..."
mkdir -p /usr/local/bin/lxc_autoscale_api
mkdir -p /etc/lxc_autoscale

# Flask testing server (gunicorn setup will be release later on)

# Step 2: Install necessary packages
echo "📦 Installing required packages..."
apt update
apt install git python3-flask python3-requests -y

# Step 3: Clone the repository
echo "🐙 Cloning the repository..."
git clone https://github.com/fabriziosalmi/proxmox-lxc-autoscale

# Step 4: Copy service file to systemd
echo "📝 Copying service file to systemd directory..."
cp proxmox-lxc-autoscale/lxc_autoscale_ml/api/lxc_autoscale_api.service /etc/systemd/system/lxc_autoscale_api.service

# Step 5: Reload systemd daemon
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Step 6: Copy the necessary files to the appropriate directories
echo "📂 Copying Python scripts and configuration files..."
cp proxmox-lxc-autoscale/lxc_autoscale_ml/api/*.py /usr/local/bin/lxc_autoscale_api/
cp proxmox-lxc-autoscale/lxc_autoscale_ml/api/config.yaml /etc/lxc_autoscale/lxc_autoscale_api.yaml

# Step 7: Enable and start the service
echo "🚀 Enabling and starting the autoscaleapi service..."
systemctl enable lxc_autoscale_api.service
systemctl start lxc_autoscale_api.service

# Step 10: Clean up the cloned repository
echo "🧹 Cleaning up..."
rm -rf proxmox-lxc-autoscale

echo "✅ Installation complete. The LXC AutoScale API service is now running. 🎉"
