"""Configuration module for LXC autoscaling."""

import os
import sys
from socket import gethostname
import yaml


CONFIG_FILE = "/etc/lxc_autoscale/lxc_autoscale.yaml"

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
else:
    sys.exit(f"Configuration file {CONFIG_FILE} does not exist. Exiting...")

DEFAULTS = config.get('DEFAULT', {})


def get_config_value(section: str, key: str, default=None):
    """
    Retrieve a configuration value from the specified section and key.

    The function first checks for an environment variable override.
    If no environment variable is set, it falls back to the YAML configuration.

    Args:
        section: The section in the configuration file.
        key: The key within the section.
        default: Default value to return if the key is not found.

    Returns:
        The configuration value.
    """
    env_key = f"{section.upper()}_{key.upper()}"
    return os.getenv(env_key, config.get(section, {}).get(key, default))


# Configuration constants
LOG_FILE = get_config_value('DEFAULT', 'log_file', '/var/log/lxc_autoscale.log')
LOCK_FILE = get_config_value('DEFAULT', 'lock_file', '/var/lock/lxc_autoscale.lock')
BACKUP_DIR = get_config_value(
    'DEFAULT', 'backup_dir', '/var/lib/lxc_autoscale/backups'
)
RESERVE_CPU_PERCENT = int(get_config_value('DEFAULT', 'reserve_cpu_percent', 10))
RESERVE_MEMORY_MB = int(get_config_value('DEFAULT', 'reserve_memory_mb', 2048))
OFF_PEAK_START = int(get_config_value('DEFAULT', 'off_peak_start', 22))
OFF_PEAK_END = int(get_config_value('DEFAULT', 'off_peak_end', 6))
IGNORE_LXC = set(map(str, get_config_value('DEFAULT', 'ignore_lxc', [])))
BEHAVIOUR = get_config_value('DEFAULT', 'behaviour', 'normal').lower()
PROXMOX_HOSTNAME = gethostname()

# LXC tier configurations
LXC_TIER_ASSOCIATIONS = {}
for section, tier_config in config.items():
    if section.startswith('TIER_'):
        nodes = tier_config.get('lxc_containers', [])
        for ctid in nodes:
            LXC_TIER_ASSOCIATIONS[str(ctid)] = tier_config

# Horizontal scaling group configurations
HORIZONTAL_SCALING_GROUPS = {}
for section, group_config in config.items():
    if section.startswith('HORIZONTAL_SCALING_GROUP_'):
        if group_config.get('lxc_containers'):
            group_config['lxc_containers'] = set(
                map(str, group_config.get('lxc_containers', []))
            )
            HORIZONTAL_SCALING_GROUPS[section] = group_config

__all__ = [
    'CONFIG_FILE', 'DEFAULTS', 'LOG_FILE', 'LOCK_FILE', 'BACKUP_DIR',
    'RESERVE_CPU_PERCENT', 'RESERVE_MEMORY_MB', 'OFF_PEAK_START',
    'OFF_PEAK_END', 'IGNORE_LXC', 'BEHAVIOUR', 'PROXMOX_HOSTNAME',
    'get_config_value', 'HORIZONTAL_SCALING_GROUPS', 'LXC_TIER_ASSOCIATIONS'
]
