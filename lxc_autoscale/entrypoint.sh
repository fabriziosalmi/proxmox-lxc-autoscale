#!/bin/bash

# Check if a user-defined configuration file is provided
if [[ -z "${USER_CONF_PATH}" ]]; then
  echo "No user-defined configuration file provided. Using default configuration."
  export CONFIG_PATH='/app/lxc_autoscale.yaml'
else
  echo "Using user-defined configuration file at ${USER_CONF_PATH}."
  export CONFIG_PATH="${USER_CONF_PATH}"
fi

# Ensure that the config file exists
if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "Error: Configuration file ${CONFIG_PATH} does not exist."
  exit 1
fi

# Debug output for the configuration file path
echo "Using configuration file: ${CONFIG_PATH}"

# Set SSH variables from environment or YAML if not provided
if [[ -z "${SSH_USER}" ]]; then
  SSH_USER=$(yq eval '.DEFAULT.ssh_user' "${CONFIG_PATH}")
  echo "Debug: SSH_USER read from YAML: ${SSH_USER}"
fi

if [[ -z "${SSH_PASS}" ]]; then
  SSH_PASS=$(yq eval '.DEFAULT.ssh_password' "${CONFIG_PATH}")
  echo "Debug: SSH_PASS read from YAML: ${SSH_PASS}"
fi

if [[ -z "${PROXMOX_HOST}" ]]; then
  PROXMOX_HOST=$(yq eval '.DEFAULT.proxmox_host' "${CONFIG_PATH}")
  echo "Debug: PROXMOX_HOST read from YAML: ${PROXMOX_HOST}"
fi

# Verify SSH variables are set
if [[ -z "${SSH_USER}" || -z "${SSH_PASS}" || -z "${PROXMOX_HOST}" ]]; then
  echo "Error: SSH_USER, SSH_PASS, and PROXMOX_HOST must be set via environment variables or in the YAML file."
  exit 1
fi

# Create required directories to ensure paths are writable
mkdir -p /var/log /var/lock /var/lib/lxc_autoscale/backups

# Function to test SSH connection and run a command
check_ssh_connection() {
  local ssh_test_command="echo 'SSH connection successful and command executed'"
  
  # Test SSH connection using sshpass
  sshpass -p "${SSH_PASS}" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "${SSH_USER}@${PROXMOX_HOST}" "${ssh_test_command}" >/dev/null 2>&1

  # Check if the SSH command was successful
  if [[ $? -ne 0 ]]; then
    echo "Error: Unable to connect to Proxmox host ${PROXMOX_HOST} via SSH or execute the test command."
    exit 1
  else
    echo "SSH connection to Proxmox host ${PROXMOX_HOST} successful, and test command executed correctly."
  fi
}

# Call the SSH connection test function
check_ssh_connection

# Start the Python application with the correct configuration path
echo "Starting the autoscaling application..."
python lxc_autoscale.py --config "${CONFIG_PATH}"
