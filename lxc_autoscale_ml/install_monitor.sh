#!/bin/bash

# Variables

# Monitor
REPO_BASE_URL="https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main"
SCRIPT_URL="${REPO_BASE_URL}/lxc_autoscale_ml/monitor/lxc_monitor.py"
SERVICE_URL="${REPO_BASE_URL}/lxc_autoscale_ml/monitor/lxc_monitor.service"
CONF_URL="${REPO_BASE_URL}/lxc_autoscale_ml/monitor/lxc_monitor.yaml"

INSTALL_PATH="/usr/local/bin/lxc_monitor.py"
SERVICE_PATH="/etc/systemd/system/lxc_monitor.service"
CONF_DIR="/etc/lxc_autoscale"
YAML_CONF_PATH="${CONF_DIR}/lxc_monitor.yaml"
# LOG_PATH="/var/log/lxc_monitor.log"

# Function to check and stop the service if running
stop_service_if_running() {
    if systemctl is-active --quiet lxc_autoscale.service; then
        echo "🛑 Stopping LXC AutoScale Monitor service..."
        systemctl stop lxc_autoscale.service
        if [ $? -ne 0 ]; then
            echo "❌ Error: Failed to stop the service."
            exit 1
        fi
    fi
}

# Function to start the service
start_service() {
    echo "🚀 Starting the LXC AutoScale Monitor service..."
    systemctl start lxc_autoscale.service
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to start the service."
        exit 1
    fi
}

# Function to enable the service
enable_service() {
    echo "🔧 Enabling the LXC AutoScale Monitor service..."
    systemctl enable lxc_autoscale.service
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to enable the service."
        exit 1
    fi
}

# Function to backup existing configuration file
backup_existing_conf() {
    if [ -f "$YAML_CONF_PATH" ]; then
        timestamp=$(date +"%Y%m%d-%H%M%S")
        backup_conf="${YAML_CONF_PATH}.${timestamp}.backup"
        echo "💾 Backing up existing configuration file to $backup_conf..."
        cp "$YAML_CONF_PATH" "$backup_conf"
        if [ $? -ne 0 ]; then
            echo "❌ Error: Failed to backup the existing configuration file."
            exit 1
        fi
    fi
}

# Function to prompt user for overwriting the configuration file
prompt_overwrite_conf() {
    if [ -f "$YAML_CONF_PATH" ]; then
        read -p "⚠️ A configuration file already exists at $YAML_CONF_PATH. Do you want to overwrite it? [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "🚫 Keeping the existing configuration file."
            return 1
        fi
    fi
    return 0
}


# Stop the service if it's already running
stop_service_if_running

# Download the main Python script
echo "📥 Downloading the LXC AutoScale Monitor main script..."
curl -sSL -o $INSTALL_PATH $SCRIPT_URL
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to download the main script."
    exit 1
fi

# Make the main script executable
chmod +x $INSTALL_PATH

# Download the systemd service file
echo "📥 Downloading the systemd service file..."
curl -sSL -o $SERVICE_PATH $SERVICE_URL
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to download the service file."
    exit 1
fi

# Set up the configuration directory and file, with backup if needed
echo "📂 Setting up configuration directory and file..."
mkdir -p $CONF_DIR
if prompt_overwrite_conf; then
    backup_existing_conf
    curl -sSL -o $YAML_CONF_PATH $CONF_URL
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to download the configuration file."
        exit 1
    fi
fi

# Set up directories for logs and backups
echo "📂 Setting up directories..."
mkdir -p $(dirname $LOG_PATH)
mkdir -p $BACKUP_DIR

# Create the log file if it doesn't exist
touch $LOG_PATH

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
enable_service
start_service

# Check the status of the service
echo "🔍 Checking service status..."
systemctl status lxc_autoscale.service --no-pager

# Verify that the service is running
if systemctl is-active --quiet lxc_autoscale.service; then
    echo "✅ LXC Monitor service is running successfully."
else
    echo "❌ Error: LXC Monitor service failed to start."
    exit 1
fi

echo "🎉 Installation and setup completed successfully."
