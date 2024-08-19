#!/bin/bash

# Define the timestamp for backup and log filenames
TIMESTAMP=$(date +"%Y%m%d%H%M%S")

# Log file for uninstallation (with timestamp)
LOGFILE="lxc_uninstall_${TIMESTAMP}.log"

# Define text styles and emojis
BOLD=$(tput bold)
RESET=$(tput sgr0)
GREEN=$(tput setaf 2)
RED=$(tput setaf 1)
CHECKMARK="\xE2\x9C\x85"  # ✔️
CROSSMARK="\xE2\x9D\x8C"  # ❌
THANKS="\xF0\x9F\x99\x8F"  # 🙏
URL="\xF0\x9F\x94\x97"  # 🔗

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

# Backup the LXC AutoScale configuration file
log "INFO" "Backing up the LXC AutoScale configuration file..."
BACKUP_DIR="/etc/lxc_autoscale/backups"
CONFIG_FILE="/etc/lxc_autoscale/lxc_autoscale.yaml"
BACKUP_FILE="${BACKUP_DIR}/lxc_autoscale_backup_${TIMESTAMP}.yaml"

if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    log "INFO" "Created backup directory at $BACKUP_DIR."
fi

if cp "$CONFIG_FILE" "$BACKUP_FILE"; then
    log "INFO" "${CHECKMARK} Successfully backed up $CONFIG_FILE to $BACKUP_FILE."
else
    log "ERROR" "${CROSSMARK} Failed to backup $CONFIG_FILE."
fi

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

# Remove the LXC AutoScale script files from /usr/local/bin/lxc_autoscale/
log "INFO" "Removing the LXC AutoScale script files..."
if rm -rf /usr/local/bin/lxc_autoscale/; then
    log "INFO" "${CHECKMARK} Successfully removed /usr/local/bin/lxc_autoscale/ directory and its contents."
else
    log "ERROR" "${CROSSMARK} Failed to remove /usr/local/bin/lxc_autoscale/ or it was not found."
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

# Remove the LXC AutoScale log files
log "INFO" "Removing the LXC AutoScale log files..."
LOG_FILES=("/var/log/lxc_autoscale.log" "/var/log/lxc_autoscale.json")
for log_file in "${LOG_FILES[@]}"; do
    if rm -f "$log_file"; then
        log "INFO" "${CHECKMARK} Successfully removed $log_file."
    else
        log "ERROR" "${CROSSMARK} Failed to remove $log_file, or it was not found."
    fi
done

log "INFO" "LXC AutoScale uninstallation complete!"
log "INFO" "${THANKS} ${BOLD}Thank you for using LXC AutoScale!${RESET}"
log "INFO" "${BOLD}For more information and updates, visit the repository:${RESET}"
log "INFO" "${URL} ${BOLD}https://github.com/fabriziosalmi/proxmox-lxc-autoscale${RESET}"
