#!/bin/bash

# Log file
LOGFILE="lxc_autoscale_installer.log"

# Source of the files to install. Override REF to install from a tag or branch.
REF="${LXC_AUTOSCALE_REF:-main}"
RAW_BASE="https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/${REF}/lxc_autoscale"
INSTALL_DIR="/usr/local/bin/lxc_autoscale"

# Every Python module the daemon imports at runtime, relative to lxc_autoscale/.
# Keep in sync with the package: a missing module makes the daemon fail on
# import at startup.
PACKAGE_FILES=(
    "__init__.py"
    "config.py"
    "errors.py"
    "state.py"
    "logging_setup.py"
    "lock_manager.py"
    "ssh.py"
    "lxc_utils.py"
    "boost.py"
    "notification.py"
    "scaling_manager.py"
    "resource_manager.py"
    "lxc_autoscale.py"
    "backends/__init__.py"
    "backends/base.py"
    "backends/cli.py"
    "backends/api.py"
)

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

# Function to download a single file, aborting the installation on failure.
# --fail is what keeps a 404 page from being written into a .py file.
download() {
    local url="$1"
    local dest="$2"
    if ! curl --fail -sSL -o "$dest" "$url"; then
        log "ERROR" "${CROSSMARK} Failed to download $url"
        exit 1
    fi
}

# Function to install the Python dependencies the daemon needs
install_dependencies() {
    apt install git python3-flask python3-requests python3-paramiko python3-yaml python3-pydantic -y

    # Debian 12 ships pydantic 1.x, which the config models do not support.
    if ! python3 -c 'import sys, pydantic; sys.exit(0 if pydantic.VERSION.startswith("2") else 1)' 2>/dev/null; then
        log "WARNING" "pydantic 2 not available from apt, installing it with pip"
        if ! pip3 install --break-system-packages 'pydantic>=2.0,<3.0' 2>/dev/null \
            && ! pip3 install 'pydantic>=2.0,<3.0'; then
            log "ERROR" "${CROSSMARK} Failed to install pydantic 2. The daemon will not start."
            exit 1
        fi
    fi
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

    # Install needed packages
    install_dependencies

    # Create necessary directories
    mkdir -p /etc/lxc_autoscale
    mkdir -p "${INSTALL_DIR}/backends"

    # Download and install the configuration file
    download "${RAW_BASE}/lxc_autoscale.yaml" /etc/lxc_autoscale/lxc_autoscale.yaml

    # Download and install every Python module of the package
    for file in "${PACKAGE_FILES[@]}"; do
        download "${RAW_BASE}/${file}" "${INSTALL_DIR}/${file}"
    done

    # A downloaded file that is not valid Python means the source moved or the
    # download was silently replaced. Catch it here, not at the first poll.
    if ! python3 -m py_compile "${INSTALL_DIR}"/*.py "${INSTALL_DIR}"/backends/*.py; then
        log "ERROR" "${CROSSMARK} Downloaded files are not valid Python. Aborting."
        exit 1
    fi

    # Download and install the systemd service file
    download "${RAW_BASE}/lxc_autoscale.service" /etc/systemd/system/lxc_autoscale.service

    # Make the main script executable
    chmod +x "${INSTALL_DIR}/lxc_autoscale.py"

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
