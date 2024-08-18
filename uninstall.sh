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

# Kill running LXC AutoScale processes
log "INFO" "Killing any running LXC AutoScale processes..."
if pkill -9 -f lxc_autoscale; then
    log "INFO" "${CHECKMARK} Successfully killed LXC AutoScale processes."
else
    log "ERROR" "${CROSSMARK} Failed to kill LXC AutoScale processes or no processes found."
fi

# Stop and disable the LXC AutoScale service
log "INFO" "Stopping and disabling the LXC AutoScale service..."
if systemctl stop lxc_autoscale.service && systemctl disable lxc_autoscale.service; then
    log "INFO" "${CHECKMARK} Successfully stopped and disabled lxc_autoscale.service."
else
    log "ERROR" "${CROSSMARK} Failed to stop or disable lxc_autoscale.service, or it was not found."
fi

# Remove the LXC AutoScale service file
log "INFO" "Removing the LXC AutoScale service file..."
if rm -f /etc/systemd/system/lxc_autoscale.service; then
    log "INFO" "${CHECKMARK} Successfully removed /etc/systemd/system/lxc_autoscale.service."
else
    log "ERROR" "${CROSSMARK} Failed to remove /etc/systemd/system/lxc_autoscale.service, or it was not found."
fi

# Remove the LXC AutoScale script
log "INFO" "Removing the LXC AutoScale script..."
if rm -f /usr/local/bin/lxc_autoscale.py; then
    log "INFO" "${CHECKMARK} Successfully removed /usr/local/bin/lxc_autoscale.py."
else
    log "ERROR" "${CROSSMARK} Failed to remove /usr/local/bin/lxc_autoscale.py, or it was not found."
fi

# Remove the LXC AutoScale configuration directory
log "INFO" "Removing the LXC AutoScale configuration directory..."
if rm -rf /etc/lxc_autoscale/; then
    log "INFO" "${CHECKMARK} Successfully removed /etc/lxc_autoscale/."
else
    log "ERROR" "${CROSSMARK} Failed to remove /etc/lxc_autoscale/, or it was not found."
fi

# Remove the LXC AutoScale data directory
log "INFO" "Removing the LXC AutoScale data directory..."
if rm -rf /var/lib/lxc_autoscale/; then
    log "INFO" "${CHECKMARK} Successfully removed /var/lib/lxc_autoscale/."
else
    log "ERROR" "${CROSSMARK} Failed to remove /var/lib/lxc_autoscale/, or it was not found."
fi

log "INFO" "LXC AutoScale uninstallation complete!"

