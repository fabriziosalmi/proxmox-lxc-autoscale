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

# Function to prompt the user for installation choice
prompt_user_choice() {
    local default_choice="1"
    local timeout=5

    log "INFO" "Prompting user for installation choice with a ${timeout}-second timeout..."

    echo -e "Please choose an installation option:"
    echo "1) ⚙️ LXC AutoScale (default)"
    echo "2) ✨ LXC AutoScale ML (experimental)"
    echo -e "You have ${timeout} seconds to choose. If no choice is made, option 1 will be selected automatically.\n"

    # Using /dev/tty to read input from the terminal directly
    if read -r -t $timeout user_choice < /dev/tty; then
        log "INFO" "User selected option ${user_choice}."
    else
        user_choice=$default_choice
        log "INFO" "No input received, defaulting to option ${user_choice}."
    fi

    echo -e "You chose option ${user_choice}."
    echo

    case $user_choice in
        1)
            install_flag="LXC_AUTO_SCALE"
            ;;
        2)
            install_flag="LXC_AUTO_SCALE_ML"
            ;;
        *)
            log "ERROR" "Invalid choice. Exiting."
            exit 1
            ;;
    esac
}

# Function to install LXC AutoScale
install_lxc_autoscale() {
    log "INFO" "Installing LXC AutoScale..."

    # Disable and stop lxc_autoscale_ml if running. Don't use both at same time (you can still run api and monitor)
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

# Function to install LXC AutoScale ML
install_lxc_autoscale_ml() {
    log "INFO" "Installing LXC AutoScale ML..."

    # Disable and stop lxc_autoscale if running. Don't use both at same time
    systemctl disable lxc_autoscale
    systemctl stop lxc_autoscale

    # Stop lxc_autoscale_ml if running
    systemctl stop lxc_autoscale_ml

    # Reload systemd
    systemctl daemon-reload

    # Install needed packages
    apt install git python3-flask python3-requests -y
    
    # Create necessary directories
    mkdir -p /etc/lxc_autoscale_ml
    mkdir -p /usr/local/bin/lxc_autoscale_api
    mkdir -p /usr/local/bin/lxc_autoscale_ml

    # Create an empty __init__.py file to treat the directory as a Python package
    touch /usr/local/bin/lxc_autoscale_ml/__init__.py
    touch /usr/local/bin/lxc_autoscale_api/__init__.py

    # Download and install all Python files in the lxc_autoscale_ml directory

    # Download and install the api application files
    curl -sSL -o /usr/local/bin/lxc_autoscale_api/lxc_autoscale_api.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/lxc_autoscale_api.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_api/cloning_management.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/cloning_management.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_api/config.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/config.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_api/error_handling.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/error_handling.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_api/health_check.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/health_check.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_api/lxc_management.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/lxc_management.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_api/resource_checking.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/resource_checking.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_api/scaling.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/scaling.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_api/snapshot_management.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/snapshot_management.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_api/utils.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/utils.py
    # Download and install the api configuration file
    curl -sSL -o /etc/lxc_autoscale_ml/lxc_autoscale_api.yaml https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/lxc_autoscale_api.yaml
 
    # Download and install the monitor application file
    curl -sSL -o /usr/local/bin/lxc_monitor.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/monitor/lxc_monitor.py
    # Download and install the monitor configuration file
    curl -sSL -o /etc/lxc_autoscale_ml/lxc_monitor.yaml https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/lxc_autoscale_api.yaml
 
    # Download and install the model application files
    curl -sSL -o /usr/local/bin/lxc_autoscale_ml/config_manager.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/model/config_manager.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_ml/data_manager.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/model/data_manager.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_ml/lock_manager.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/model/lock_manager.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_ml/logger.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/model/logger.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_ml/model.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/model/model.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_ml/scaling.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/model/scaling.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_ml/signal_handler.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/model/signal_handler.py
    curl -sSL -o /usr/local/bin/lxc_autoscale_ml/lxc_autoscale_ml.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/model/lxc_autoscale_ml.py
    # Download and install the model configuration file
    curl -sSL -o /etc/lxc_autoscale_ml/lxc_autoscale_ml.yaml https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/model/lxc_autoscale_ml.yaml

    # Download and install the systemd services file
    curl -sSL -o /etc/systemd/system/lxc_autoscale_ml.service https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/model/lxc_autoscale_ml.service
    curl -sSL -o /etc/systemd/system/lxc_autoscale_api.service https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/api/lxc_autoscale_api.service
    curl -sSL -o /etc/systemd/system/lxc_monitor.service https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/monitor/lxc_monitor.service

    # Make the main script executable
    chmod +x /usr/local/bin/lxc_autoscale_ml/lxc_autoscale_ml.py
    chmod +x /usr/local/bin/lxc_autoscale_api/lxc_autoscale_api.py
    chmod +x /usr/local/bin/lxc_monitor.py

    # Reload systemd to recognize the new service
    systemctl daemon-reload
    systemctl enable lxc_autoscale_ml.service
    systemctl enable lxc_autoscale_api.service
    systemctl enable lxc_monitor.service

    # Automatically start the service after installation
    if systemctl start lxc_autoscale_api.service; then
        log "INFO" "${CHECKMARK} Service LXC AutoScale API started successfully!"
    else
        log "ERROR" "${CROSSMARK} Failed to start Service LXC AutoScale."
    fi

    # Automatically start the service after installation
    if systemctl start lxc_monitor.service; then
        log "INFO" "${CHECKMARK} Service LXC Monitor started successfully!"
    else
        log "ERROR" "${CROSSMARK} Failed to start Service LXC Monitor."
    fi

    # Automatically start the service after installation
    if systemctl start lxc_autoscale_ml.service; then
        log "INFO" "${CHECKMARK} Service LXC AutoScale ML started successfully!"
    else
        log "ERROR" "${CROSSMARK} Failed to start Service LXC AutoScale ML."
    fi

    # Show status for all installed services
    systemctl status lxc_monitor.service --no-pager
    systemctl status lxc_autoscale_api.service --no-pager
    systemctl status lxc_autoscale_ml.service --no-pager
}

# Main script execution
header
backup_files
delete_files_and_folders
prompt_user_choice

# Ensure the install_flag is initialized
install_flag=${install_flag:-""}

# Proceed with installation based on the chosen option
case $install_flag in
    "LXC_AUTO_SCALE")
        install_lxc_autoscale
        ;;
    "LXC_AUTO_SCALE_ML")
        install_lxc_autoscale_ml
        ;;
    *)
        log "ERROR" "Invalid installation flag. Exiting."
        exit 1
        ;;
esac

log "INFO" "${CHECKMARK} Installation process complete!"
