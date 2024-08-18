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

# Declare flags array to avoid uninitialized errors
declare -A flags

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

# Define file versions and associated actions
declare -A file_actions=(
    ["/etc/lxc_autoscale/lxc_autoscale.conf"]="backup remove"
    ["/etc/lxc_autoscale/lxc_autoscale.yaml"]="backup remove"
    ["/etc/autoscaleapi.yaml"]="backup remove"
)

# Define the list of files to check
files_to_check=(
    "/etc/lxc_autoscale/lxc_autoscale.conf"
    "/etc/lxc_autoscale/lxc_autoscale.yaml"
    "/etc/autoscaleapi.yaml"
)

# Define additional files to delete
additional_files_to_delete=(
    "/path/to/additional_file1"
    "/path/to/additional_file2"
    "/path/to/additional_file3"
)

# Define files and folders to remove based on version
version_specific_files=(
    "INI:/usr/local/bin/lxc_autoscale.py:/etc/systemd/system/lxc_autoscale.service:/var/log/lxc_autoscale.log:/var/lib/lxc_autoscale/backups"
    "YAML:/usr/local/bin/lxc_autoscale.py:/etc/systemd/system/lxc_autoscale.service:/var/log/lxc_autoscale.log:/var/lib/lxc_autoscale/backups"
    "API-MONITOR-ML:/usr/local/bin/autoscaleapi:/etc/systemd/system/autoscaleapi.service:/usr/local/bin/lxc_monitor.py:/etc/systemd/system/lxc_monitor.service:/etc/systemd/system/lxc_autoscale_ml.service:/var/log/lxc_metrics.json:/var/log/lxc_autoscale_ml.log:/var/log/lxc_autoscale_ml.json:/usr/local/bin/lxc_autoscale_ml.py"
)

# Function to check file existence and set flags
check_files() {
    log "INFO" "Checking file existence..."
    for file in "${files_to_check[@]}"; do
        if [[ -e "$file" ]]; then
            flags["$file"]="exists"
            log "INFO" "File exists: $file"
        else
            flags["$file"]="missing"
            log "INFO" "File missing: $file"
        fi
    done
}

# Function to generate a tag based on file statuses
generate_tag() {
    local tag=""
    for file in "${files_to_check[@]}"; do
        case "${flags["$file"]}" in
            "exists")
                tag+="1"
                ;;
            "missing")
                tag+="0"
                ;;
        esac
    done
    echo "$tag"
}

# Function to create a backup of found files
backup_files() {
    local timestamp
    timestamp=$(date +"%Y%m%d%H%M%S")

    log "INFO" "Creating backups..."
    for file in "${files_to_check[@]}"; do
        if [[ "${flags["$file"]}" == "exists" ]]; then
            local backup_file="${file}_backup_${timestamp}"
            if cp "$file" "$backup_file"; then
                log "INFO" "Backed up $file to $backup_file"
            else
                log "ERROR" "Failed to back up $file"
            fi
        fi
    done
}

# Function to delete specific files
delete_files() {
    log "INFO" "Deleting specified files..."

    # Delete files specified in files_to_check
    for file in "${files_to_check[@]}"; do
        if [[ "${flags["$file"]}" == "exists" ]]; then
            if rm "$file" 2>/dev/null; then
                log "INFO" "Deleted $file"
            else
                log "WARNING" "Failed to delete $file or it does not exist"
            fi
        fi
    done

    # Delete additional files
    for file in "${additional_files_to_delete[@]}"; do
        if [[ -e "$file" ]]; then
            if rm "$file" 2>/dev/null; then
                log "INFO" "Deleted additional file $file"
            else
                log "WARNING" "Failed to delete additional file $file or it does not exist"
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

# Function to handle different cases based on flags
handle_cases() {
    local tag
    tag=$(generate_tag)

    log "INFO" "Handling cases based on tag: $tag"

    case $tag in
        "000")
            log "INFO" "No previous configuration files detected."
            ;;
        "100")
            log "INFO" "Detected INI configuration. Performing cleanup for INI version."
            backup_files
            delete_files
            rm -f /usr/local/bin/lxc_autoscale.py
            stop_service lxc_autoscale.service
            remove_service_files /etc/systemd/system/lxc_autoscale.service
            ;;
        "010")
            log "INFO" "Detected YAML configuration. Performing cleanup for YAML version."
            backup_files
            delete_files
            rm -f /usr/local/bin/lxc_autoscale.py
            stop_service lxc_autoscale.service
            remove_service_files /etc/systemd/system/lxc_autoscale.service
            ;;
        "001")
            log "INFO" "Detected API-MONITOR-ML configuration. Performing cleanup for API-MONITOR-ML version."
            backup_files
            delete_files
            rm -rf /usr/local/bin/autoscaleapi
            rm -f /usr/local/bin/lxc_monitor.py
            rm -f /usr/local/bin/lxc_autoscale_ml.py
            stop_service autoscaleapi.service
            stop_service lxc_monitor.service
            stop_service lxc_autoscale_ml.service
            remove_service_files /etc/systemd/system/autoscaleapi.service
            remove_service_files /etc/systemd/system/lxc_monitor.service
            remove_service_files /etc/systemd/system/lxc_autoscale_ml.service
            ;;
        "110")
            log "INFO" "Detected both INI and YAML configurations. Performing cleanup for both versions."
            backup_files
            delete_files
            rm -f /usr/local/bin/lxc_autoscale.py
            stop_service lxc_autoscale.service
            remove_service_files /etc/systemd/system/lxc_autoscale.service
            ;;
        "101")
            log "INFO" "Detected INI and API-MONITOR-ML configurations. Performing cleanup for both versions."
            backup_files
            delete_files
            rm -f /usr/local/bin/lxc_autoscale.py
            stop_service lxc_autoscale.service
            remove_service_files /etc/systemd/system/lxc_autoscale.service
            rm -rf /usr/local/bin/autoscaleapi
            rm -f /usr/local/bin/lxc_monitor.py
            rm -f /usr/local/bin/lxc_autoscale_ml.py
            stop_service autoscaleapi.service
            stop_service lxc_monitor.service
            stop_service lxc_autoscale_ml.service
            remove_service_files /etc/systemd/system/autoscaleapi.service
            remove_service_files /etc/systemd/system/lxc_monitor.service
            remove_service_files /etc/systemd/system/lxc_autoscale_ml.service
            ;;
        "011")
            log "INFO" "Detected YAML and API-MONITOR-ML configurations. Performing cleanup for both versions."
            backup_files
            delete_files
            rm -f /usr/local/bin/lxc_autoscale.py
            stop_service lxc_autoscale.service
            remove_service_files /etc/systemd/system/lxc_autoscale.service
            rm -rf /usr/local/bin/autoscaleapi
            rm -f /usr/local/bin/lxc_monitor.py
            rm -f /usr/local/bin/lxc_autoscale_ml.py
            stop_service autoscaleapi.service
            stop_service lxc_monitor.service
            stop_service lxc_autoscale_ml.service
            remove_service_files /etc/systemd/system/autoscaleapi.service
            remove_service_files /etc/systemd/system/lxc_monitor.service
            remove_service_files /etc/systemd/system/lxc_autoscale_ml.service
            ;;
        "111")
            log "INFO" "Detected INI, YAML, and API-MONITOR-ML configurations. Performing cleanup for all versions."
            backup_files
            delete_files
            rm -f /usr/local/bin/lxc_autoscale.py
            stop_service lxc_autoscale.service
            remove_service_files /etc/systemd/system/lxc_autoscale.service
            rm -rf /usr/local/bin/autoscaleapi
            rm -f /usr/local/bin/lxc_monitor.py
            rm -f /usr/local/bin/lxc_autoscale_ml.py
            stop_service autoscaleapi.service
            stop_service lxc_monitor.service
            stop_service lxc_autoscale_ml.service
            remove_service_files /etc/systemd/system/autoscaleapi.service
            remove_service_files /etc/systemd/system/lxc_monitor.service
            remove_service_files /etc/systemd/system/lxc_autoscale_ml.service
            ;;
        *)
            log "ERROR" "Unexpected tag: $tag."
            exit 1
            ;;
    esac

    log "INFO" "Setting ready to install flag..."
    # Example: touch /path/to/ready_to_install.flag
}


prompt_user_choice() {
    local default_choice="1"
    local timeout=5

    log "INFO" "Prompting user for installation choice with a ${timeout}-second timeout..."

    echo -e "Please choose an installation option:"
    echo "1) ⚙️ LXC AutoScale (default)"
    echo "2) ✨ LXC AutoScale ML (experimental)"
    echo -e "You have ${timeout} seconds to choose. If no choice is made, option 1 will be selected automatically.\n"

    # Adding a log to indicate waiting for user input
    log "INFO" "Waiting for user input with a ${timeout}-second timeout..."
    read -r -t $timeout user_choice

    # Adding a log to indicate what choice was made or defaulted to
    if [ -z "$user_choice" ]; then
        log "INFO" "No input received, defaulting to option ${default_choice}."
    else
        log "INFO" "User selected option ${user_choice}."
    fi

    user_choice=${user_choice:-$default_choice}  # Set to default if no input

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

    mkdir -p /etc/lxc_autoscale

    # Download and install necessary files
    curl -sSL -o /etc/lxc_autoscale/lxc_autoscale.yaml https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale.yaml
    curl -sSL -o /usr/local/bin/lxc_autoscale.py https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale.py
    curl -sSL -o /etc/systemd/system/lxc_autoscale.service https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale/lxc_autoscale.service

    chmod +x /usr/local/bin/lxc_autoscale.py

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

    # Download and execute installation scripts
    curl -sSL -o /usr/local/bin/install_api.sh https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/install_api.sh
    curl -sSL -o /usr/local/bin/install_monitor.sh https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/install_monitor.sh
    curl -sSL -o /usr/local/bin/install_model.sh https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/lxc_autoscale_ml/install_model.sh

    chmod +x /usr/local/bin/install_api.sh
    chmod +x /usr/local/bin/install_monitor.sh
    chmod +x /usr/local/bin/install_model.sh

    if /usr/local/bin/install_api.sh && /usr/local/bin/install_monitor.sh && /usr/local/bin/install_model.sh; then
        log "INFO" "${CHECKMARK} LXC AutoScale ML installation complete!"
    else
        log "ERROR" "${CROSSMARK} LXC AutoScale ML installation failed."
    fi
}

# Main script execution
header
check_files
handle_cases
prompt_user_choice

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
