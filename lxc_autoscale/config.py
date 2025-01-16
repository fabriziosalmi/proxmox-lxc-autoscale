"""Configuration module for LXC autoscaling."""

import os
import sys
from socket import gethostname
from typing import Any, Dict, List, Set, Union

import yaml

CONFIG_FILE = "/etc/lxc_autoscale/lxc_autoscale.yaml"

if not os.path.exists(CONFIG_FILE):
    sys.exit(f"Configuration file {CONFIG_FILE} does not exist. Exiting...")

with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
    config: Dict[str, Any] = yaml.safe_load(file)

if not isinstance(config, dict):
    sys.exit("Invalid configuration format. Expected a dictionary.")


def get_config_value(section: str, key: str, default: Any = None) -> Any:
    """
    Retrieve a configuration value from the specified section and key.

    The function first checks for an environment variable override.
    If no environment variable is set, it falls back to the YAML configuration.
    If no environment variable and no configuration is found, return the default.

    Args:
        section: The section in the configuration file.
        key: The key within the section.
        default: Default value to return if the key is not found.

    Returns:
        The configuration value.
    """
    env_key = f"LXC_AUTOSCALE_{section.upper()}_{key.upper()}"
    env_value = os.getenv(env_key)
    if env_value is not None:
        return env_value
    if isinstance(config.get(section), dict):
        return config.get(section, {}).get(key, default)
    return default

# --- Default Configuration ---
DEFAULTS: Dict[str, Any] = config.get('DEFAULT', {})

# --- General Configuration ---
LOG_FILE: str = get_config_value('DEFAULT', 'log_file', '/var/log/lxc_autoscale.log')
LOCK_FILE: str = get_config_value('DEFAULT', 'lock_file', '/var/lock/lxc_autoscale.lock')
BACKUP_DIR: str = get_config_value('DEFAULT', 'backup_dir', '/var/lib/lxc_autoscale/backups')
RESERVE_CPU_PERCENT: int = int(get_config_value('DEFAULT', 'reserve_cpu_percent', 10))
RESERVE_MEMORY_MB: int = int(get_config_value('DEFAULT', 'reserve_memory_mb', 2048))
OFF_PEAK_START: int = int(get_config_value('DEFAULT', 'off_peak_start', 22))
OFF_PEAK_END: int = int(get_config_value('DEFAULT', 'off_peak_end', 6))
IGNORE_LXC: Set[str] = set(map(str, get_config_value('DEFAULT', 'ignore_lxc', [])))
BEHAVIOUR: str = get_config_value('DEFAULT', 'behaviour', 'normal').lower()
PROXMOX_HOSTNAME: str = gethostname()


# --- Scaling Constants ---
CPU_SCALE_DIVISOR: int = 10
MEMORY_SCALE_FACTOR: int = 10
TIMEOUT_EXTENDED: int = 300


# --- Tier Configurations ---
LXC_TIER_ASSOCIATIONS: Dict[str, Dict[str, Any]] = {}
for section, tier_config in config.items():
    if section.startswith('TIER_') and isinstance(tier_config, dict):
        nodes: List[Union[str, int]] = tier_config.get('lxc_containers', [])
        if isinstance(nodes, list):
            for ctid in nodes:
                LXC_TIER_ASSOCIATIONS[str(ctid)] = tier_config
        else:
            print(f"Warning: lxc_containers in {section} is not a list and will be ignored")

# --- Horizontal Scaling Groups ---
HORIZONTAL_SCALING_GROUPS: Dict[str, Dict[str, Any]] = {}
for section, group_config in config.items():
    if section.startswith('HORIZONTAL_SCALING_GROUP_') and isinstance(group_config, dict):
        lxc_containers = group_config.get('lxc_containers')
        if lxc_containers:
            if isinstance(lxc_containers, list):
                group_config['lxc_containers'] = set(map(str, lxc_containers))
                HORIZONTAL_SCALING_GROUPS[section] = group_config
            else:
                print(f"Warning: lxc_containers in {section} is not a list and will be ignored")


__all__ = [
    'CONFIG_FILE',
    'DEFAULTS',
    'LOG_FILE',
    'LOCK_FILE',
    'BACKUP_DIR',
    'RESERVE_CPU_PERCENT',
    'RESERVE_MEMORY_MB',
    'OFF_PEAK_START',
    'OFF_PEAK_END',
    'IGNORE_LXC',
    'BEHAVIOUR',
    'PROXMOX_HOSTNAME',
    'get_config_value',
    'HORIZONTAL_SCALING_GROUPS',
    'LXC_TIER_ASSOCIATIONS',
    'CPU_SCALE_DIVISOR',
    'MEMORY_SCALE_FACTOR',
    'TIMEOUT_EXTENDED',
]