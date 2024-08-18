#!/bin/bash

# Ensure the script is run as root
if [ "$(id -u)" -ne 0 ]; then
  echo "🚫 This script must be run as root. Please use sudo or run as root."
  exit 1
fi

# Step 1: Create the necessary directory
echo "📁 Creating directory /usr/local/bin/autoscaleapi..."
mkdir -p /usr/local/bin/autoscaleapi

# Step 2: Install necessary packages
echo "📦 Installing required packages..."
apt update
apt install git python3-flask python3-requests python3-gunicorn -y

# Step 3: Create a symlink for gunicorn
echo "🔗 Creating symlink for gunicorn..."
ln -s /usr/lib/python3/dist-packages/gunicorn/app/wsgiapp.py /usr/local/bin/gunicorn
chmod +x /usr/local/bin/gunicorn

# Step 4: Add shebang to gunicorn script
echo "✏️ Adding shebang to gunicorn script..."
sed -i '1i #!/usr/bin/python3' /usr/local/bin/gunicorn

# Step 5: Clone the repository
echo "🐙 Cloning the repository..."
git clone https://github.com/fabriziosalmi/proxmox-lxc-autoscale

# Step 6: Copy service file to systemd
echo "📝 Copying service file to systemd directory..."
cp proxmox-lxc-autoscale/lxc_autoscale_ml/api/lxc_autoscale_api.service /etc/systemd/system/lxc_autoscale_api.service

# Step 7: Reload systemd daemon
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Step 8: Copy the necessary files to the appropriate directories
echo "📂 Copying Python scripts and configuration files..."
cp proxmox-lxc-autoscale/lxc_autoscale_ml/api/*.py /usr/local/bin/lxc_autoscale_api/
cp proxmox-lxc-autoscale/lxc_autoscale_ml/api/config.yaml /etc/lxc_autoscale_api.yaml

# Step 9: Enable and start the service
echo "🚀 Enabling and starting the autoscaleapi service..."
systemctl enable lxc_autoscale_api.service
systemctl start lxc_autoscale_api.service

# Step 10: Clean up the cloned repository
echo "🧹 Cleaning up..."
rm -rf proxmox-lxc-autoscale

echo "✅ Installation complete. The LXC AutoScale API service is now running. 🎉"
