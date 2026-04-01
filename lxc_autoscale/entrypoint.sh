#!/bin/bash
set -euo pipefail

# --- Configuration file ---
if [[ -z "${USER_CONF_PATH:-}" ]]; then
  echo "No user-defined configuration file provided. Using default configuration."
  export CONFIG_PATH='/app/lxc_autoscale.yaml'
else
  echo "Using user-defined configuration file at ${USER_CONF_PATH}."
  export CONFIG_PATH="${USER_CONF_PATH}"
fi

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "Error: Configuration file ${CONFIG_PATH} does not exist."
  exit 1
fi

echo "Using configuration file: ${CONFIG_PATH}"

# --- SSH variables from env or YAML ---
SSH_USER="${SSH_USER:-$(yq eval '.DEFAULT.ssh_user' "${CONFIG_PATH}")}"
SSH_PASS="${SSH_PASS:-$(yq eval '.DEFAULT.ssh_password' "${CONFIG_PATH}")}"
PROXMOX_HOST="${PROXMOX_HOST:-$(yq eval '.DEFAULT.proxmox_host' "${CONFIG_PATH}")}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$(yq eval '.DEFAULT.ssh_key_path // ""' "${CONFIG_PATH}")}"

# Validate required vars (don't echo passwords!)
if [[ -z "${SSH_USER}" || -z "${PROXMOX_HOST}" ]]; then
  echo "Error: SSH_USER and PROXMOX_HOST must be set via environment or YAML."
  exit 1
fi

if [[ -z "${SSH_PASS}" && -z "${SSH_KEY_PATH}" ]]; then
  echo "Error: Either SSH_PASS or SSH_KEY_PATH must be set for SSH authentication."
  exit 1
fi

# --- Create required directories ---
mkdir -p /var/log /var/lock /var/lib/lxc_autoscale/backups

# --- Known hosts setup ---
# Security: NEVER use StrictHostKeyChecking=no.
# Provide a known_hosts file via KNOWN_HOSTS_PATH or SSH_KNOWN_HOSTS env var.
KNOWN_HOSTS_FILE="${KNOWN_HOSTS_PATH:-/root/.ssh/known_hosts}"
if [[ ! -f "${KNOWN_HOSTS_FILE}" ]]; then
  echo "WARNING: No known_hosts file found at ${KNOWN_HOSTS_FILE}."
  echo "  To fix: mount a known_hosts file or set KNOWN_HOSTS_PATH."
  echo "  You can generate one with: ssh-keyscan -H ${PROXMOX_HOST} > known_hosts"
  echo "  Attempting ssh-keyscan for initial setup..."
  mkdir -p "$(dirname "${KNOWN_HOSTS_FILE}")"
  ssh-keyscan -H "${PROXMOX_HOST}" > "${KNOWN_HOSTS_FILE}" 2>/dev/null || {
    echo "Error: ssh-keyscan failed. Provide a known_hosts file manually."
    exit 1
  }
  chmod 600 "${KNOWN_HOSTS_FILE}"
  echo "Host keys for ${PROXMOX_HOST} added to ${KNOWN_HOSTS_FILE}."
fi

# --- Test SSH connection ---
check_ssh_connection() {
  local ssh_opts="-o ConnectTimeout=10 -o UserKnownHostsFile=${KNOWN_HOSTS_FILE}"

  if [[ -n "${SSH_KEY_PATH}" && -f "${SSH_KEY_PATH}" ]]; then
    # Key-based auth (preferred)
    ssh ${ssh_opts} -i "${SSH_KEY_PATH}" "${SSH_USER}@${PROXMOX_HOST}" \
      "echo 'SSH connection successful'" >/dev/null 2>&1
  elif [[ -n "${SSH_PASS}" ]]; then
    # Password auth via sshpass (password NOT visible in logs)
    sshpass -e ssh ${ssh_opts} "${SSH_USER}@${PROXMOX_HOST}" \
      "echo 'SSH connection successful'" >/dev/null 2>&1
  fi

  if [[ $? -ne 0 ]]; then
    echo "Error: Unable to connect to Proxmox host ${PROXMOX_HOST} via SSH."
    echo "  Check credentials and that the host key is in ${KNOWN_HOSTS_FILE}."
    exit 1
  fi
  echo "SSH connection to Proxmox host ${PROXMOX_HOST} verified."
}

# Export SSHPASS for sshpass -e (reads from env, not cmdline — safer)
export SSHPASS="${SSH_PASS}"

check_ssh_connection

# --- #6: Drop to non-root if API-only mode ---
if [[ "${LXC_RUN_AS_ROOT:-true}" == "false" ]]; then
  echo "Running as non-root user 'autoscale' (API/remote mode)."
  exec su-exec autoscale python lxc_autoscale.py --config "${CONFIG_PATH}" 2>/dev/null || \
    exec gosu autoscale python lxc_autoscale.py --config "${CONFIG_PATH}" 2>/dev/null || \
    exec python lxc_autoscale.py --config "${CONFIG_PATH}"
else
  echo "Starting the autoscaling application as root..."
  exec python lxc_autoscale.py --config "${CONFIG_PATH}"
fi
