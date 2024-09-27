#!/bin/bash

# Log file
LOGFILE="lxc_autoscale_installer.log"

# Define text styles and emojis
BOLD=$(tput bold)
RESET=$(tput sgr0)
GREEN=$(tput setaf 2)
RED=$(tput setaf 1)
YELLOW=$(tput setaf 3)
BLUE=$(tput setaf 4)
CHECKMARK="\xE2\x9C\x85"  # ✔️
CROSSMARK="\xE2\x9D\x8C"  # ❌
CLOCK="\xE2\x8F\xB3"      # ⏳
ROCKET="\xF0\x9F\x9A\x80" # 🚀

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
        "WARNING")
            echo -e "${timestamp} [${YELLOW}${level}${RESET}] ${message}" | tee -a "$LOGFILE"
            ;;
    esac
}

# ASCII Art Header with optional emoji
header() {
    echo -e "\n${BLUE}${BOLD}🎨 LXC AutoScale Installer${RESET}"
    echo "============================="
    echo "Welcome to the LXC AutoScale cleanup and installation script!"
    echo "============================="
    echo
}

# List of files to back up and then remove
files_to_backup_and_remove=(
    "/etc/lxc_autoscale/lxc_autoscale.conf"
    "/etc/lxc_autoscale/lxc_autoscale.yaml"
    "/etc/autoscaleapi.yaml"
)

# List of additional files and folders to remove without backup
files_and_folders_to_remove=(
    "/etc/lxc_autoscale_ml/lxc_autoscale_api.yaml"
    "/etc/lxc_autoscale_ml/lxc_autoscale_ml.yaml"
    "/etc/lxc_autoscale_ml/lxc_monitor.yaml"
    "/usr/local/bin/lxc_autoscale.py"
    "/usr/local/bin/lxc_monitor.py"
    "/usr/local/bin/lxc_autoscale_ml.py"
    "/usr/local/bin/autoscaleapi"
    "/var/log/lxc_autoscale.log"
    "/var/lib/lxc_autoscale/backups"
)

# Function to create a backup of specified files
backup_files() {
    local timestamp
    timestamp=$(date +"%Y%m%d%H%M%S")

    log "INFO" "Creating backups..."
    for file in "${files_to_backup_and_remove[@]}"; do
        if [[ -e "$file" ]]; then
            local backup_file="${file}_backup_${timestamp}"
            if cp "$file" "$backup_file"; then
                log "INFO" "Backed up $file to $backup_file"
            else
                log "ERROR" "Failed to back up $file"
            fi
        fi
    done
}

# Function to delete specified files and folders
delete_files_and_folders() {
    log "INFO" "Deleting specified files and folders..."

    # Delete files that were backed up
    for file in "${files_to_backup_and_remove[@]}"; do
        if [[ -e "$file" ]]; then
            if rm "$file" 2>/dev/null; then
                log "INFO" "Deleted $file"
            else
                log "WARNING" "Failed to delete $file or it does not exist"
            fi
        fi
    done

    # Delete additional files and folders
    for item in "${files_and_folders_to_remove[@]}"; do
        if [[ -e "$item" ]]; then
            if rm -rf "$item" 2>/dev/null; then
                log "INFO" "Deleted $item"
            else
                log "WARNING" "Failed to delete $item or it does not exist"
            fi
        fi
    done
}

# Function to stop a service if it's loaded
stop_service() {
    local service_name="$1"
    if systemctl stop "$service_name" 2>/dev/null; then
        log "INFO" "Stopped $service_name"
    else
        log "WARNING" "Failed to stop $service_name or it is not loaded"
    fi
}

# Function to remove systemd service files
remove_service_files() {
    local service_files=("$@")
    for file in "${service_files[@]}"; do
        if rm "$file" 2>/dev/null; then
            log "INFO" "Removed service file $file"
        else
            log "WARNING" "Failed to remove service file $file or it does not exist"
        fi
    done
}

# Function to install LXC AutoScale
install_lxc_autoscale() {
    log "INFO" "Installing LXC AutoScale..."

    # Disable and stop lxc_autoscale_ml if running. Don't use both at the same time (you can still run api and monitor)
    systemctl disable lxc_autoscale_ml
    systemctl stop lxc_autoscale_ml

    # Stop lxc_autoscale if running
    systemctl stop lxc_autoscale

    # Reload systemd
    systemctl daemon-reload

    # Create necessary directories
    mkdir -p /etc/lxc_autoscale
    mkdir -p /usr/local/bin/lxc_autoscale

    # Create an empty __init__.py file to treat the directory as a Python package
    touch /usr/local/bin/lxc_autoscale/__init__.py

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
    curl -sSL -o /usr/local/bin/lxc_autoscale/lxc_autoscale.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale.py

    # Download and install the systemd service file
    curl -sSL -o /etc/systemd/system/lxc_autoscale.service https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale.service

    # Make the main script executable
    chmod +x /usr/local/bin/lxc_autoscale/lxc_autoscale.py

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

# Main script execution
header
backup_files
delete_files_and_folders

# Proceed with LXC AutoScale installation
install_lxc_autoscale

log "INFO" "${CHECKMARK} Installation process complete!"
