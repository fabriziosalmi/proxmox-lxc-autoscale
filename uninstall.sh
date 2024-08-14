#!/bin/bash

# Variables
SERVICE_NAME="lxc_autoscale.service"
INSTALL_PATH="/usr/local/bin/lxc_autoscale.py"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
CONFIG_DIR="/etc/lxc_autoscale"
LOG_PATH="/var/log/lxc_autoscale.log"
BACKUP_DIR="/var/lib/lxc_autoscale/backups"
LOCK_FILE="/var/lock/lxc_autoscale.lock"

# Dirty workaround to force existing process to terminate
echo "⚠️ Dirty workaround to force existing process to terminate.."
kill -9 $(ps aux | grep lxc_autoscale | grep -v grep | awk '{print $2}')

# Function to kill the process if it's running
kill_process() {
    local pids=$(pgrep -f "$INSTALL_PATH")
    if [ -n "$pids" ]; then
        echo "🛑 Killing the running LXC AutoScale process(es)..."
        echo "$pids" | xargs kill -9
        # Verify that the processes have been killed
        sleep 2
        if pgrep -f "$INSTALL_PATH" > /dev/null; then
            echo "⚠️ Failed to kill some LXC AutoScale processes. Please check manually."
        else
            echo "✅ All LXC AutoScale processes have been successfully killed."
        fi
    else
        echo "✅ No running LXC AutoScale process found."
    fi
}

# Stop the service if it's running
echo "🛑 Stopping the LXC AutoScale service..."
systemctl stop $SERVICE_NAME

# Kill the process if it's still running
kill_process

# Disable the service to prevent it from starting on boot
echo "🔧 Disabling the LXC AutoScale service..."
systemctl disable $SERVICE_NAME

# Remove the service file
if [ -f "$SERVICE_PATH" ]; then
    echo "🗑️ Removing the systemd service file..."
    rm -f $SERVICE_PATH
else
    echo "⚠️ Service file not found at $SERVICE_PATH."
fi

# Reload systemd daemon to apply changes
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Remove the script
if [ -f "$INSTALL_PATH" ]; then
    echo "🗑️ Removing the LXC AutoScale script..."
    rm -f $INSTALL_PATH
else
    echo "⚠️ Script not found at $INSTALL_PATH."
fi

# Remove the configuration directory
if [ -d "$CONFIG_DIR" ]; then
    echo "🗑️ Removing the configuration directory..."
    rm -rf $CONFIG_DIR
else
    echo "⚠️ Configuration directory not found at $CONFIG_DIR."
fi

# Remove the backup directory
if [ -d "$BACKUP_DIR" ]; then
    echo "🗑️ Removing the backup directory..."
    rm -rf $BACKUP_DIR
else
    echo "⚠️ Backup directory not found at $BACKUP_DIR."
fi

# Remove the log file
if [ -f "$LOG_PATH" ]; then
    echo "🗑️ Removing the log file..."
    rm -f $LOG_PATH
else
    echo "⚠️ Log file not found at $LOG_PATH."
fi

# Remove the lock file
if [ -f "$LOCK_FILE" ]; then
    echo "🗑️ Removing the lock file..."
    rm -f $LOCK_FILE
else
    echo "⚠️ Lock file not found at $LOCK_FILE."
fi

echo "✅ Uninstallation of LXC AutoScale completed successfully."
