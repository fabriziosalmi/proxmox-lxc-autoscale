#!/bin/bash

# Log file for uninstallation
LOGFILE="lxc_autoscale_uninstaller.log"

# Define text styles and emojis
BOLD=$(tput bold)
RESET=$(tput sgr0)
GREEN=$(tput setaf 2)
RED=$(tput setaf 1)
CHECKMARK="\xE2\x9C\x85"  # ✔️
CROSSMARK="\xE2\x9D\x8C"  # ❌

# Log function
log() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    case $level in
        "INFO")
            echo -e "${timestamp} [${GREEN}${level}${RESET}] ${message}" | tee -a "$LOGFILE"
            ;;
        "ERROR")
            echo -e "${timestamp} [${RED}${level}${RESET}] ${message}" | tee -a "$LOGFILE"
            ;;
    esac
}

log "INFO" "Starting LXC AutoScale uninstallation..."

# Function to stop and disable a service
uninstall_service() {
    local service_name="$1"
    log "INFO" "Stopping and disabling the $service_name service..."
    if systemctl stop "$service_name" && systemctl disable "$service_name"; then
        log "INFO" "${CHECKMARK} Successfully stopped and disabled $service_name."
    else
        log "ERROR" "${CROSSMARK} Failed to stop or disable $service_name, or it was not found."
    fi
}

# Function to remove files and directories
remove_files() {
    local files=("$@")
    for file in "${files[@]}"; do
        log "INFO" "Removing $file..."
        if rm -rf "$file"; then
            log "INFO" "${CHECKMARK} Successfully removed $file."
        else
            log "ERROR" "${CROSSMARK} Failed to remove $file, or it was not found."
        fi
    done
}

# Uninstall LXC AutoScale API
log "INFO" "Uninstalling LXC AutoScale API..."
uninstall_service "lxc_autoscale_api.service"
remove_files "/usr/local/bin/lxc_autoscale_api" "/etc/systemd/system/lxc_autoscale_api.service" "/etc/lxc_autoscale/lxc_autoscale_api.yaml"

# Uninstall LXC AutoScale ML
log "INFO" "Uninstalling LXC AutoScale ML..."
uninstall_service "lxc_autoscale_ml.service"
remove_files "/usr/local/bin/lxc_autoscale_ml.py" "/etc/systemd/system/lxc_autoscale_ml.service" "/etc/lxc_autoscale/lxc_autoscale_ml.yaml"

# Uninstall LXC Monitor
log "INFO" "Uninstalling LXC Monitor..."
uninstall_service "lxc_monitor.service"
remove_files "/usr/local/bin/lxc_monitor.py" "/etc/systemd/system/lxc_monitor.service" "/etc/lxc_autoscale/lxc_monitor.yaml"

# Cleanup shared configuration directory
log "INFO" "Cleaning up shared configuration directory if empty..."
if [ -d "/etc/lxc_autoscale" ] && [ ! "$(ls -A /etc/lxc_autoscale)" ]; then
    rmdir /etc/lxc_autoscale
    log "INFO" "${CHECKMARK} Successfully removed empty directory /etc/lxc_autoscale."
fi

# Final cleanup
log "INFO" "Reloading systemd daemon to reflect changes..."
systemctl daemon-reload

log "INFO" "LXC AutoScale uninstallation complete!"
