import os
import sys
import yaml
from socket import gethostname

# Path to the configuration file
CONFIG_FILE = "/etc/lxc_autoscale/lxc_autoscale.yaml"

# Load configuration from the YAML file
if os.path.exists(CONFIG_FILE):
    # If the configuration file exists, load it
    with open(CONFIG_FILE, 'r') as file:
        config = yaml.safe_load(file)
else:
    # If the configuration file does not exist, exit the program with an error message
    sys.exit(f"Configuration file {CONFIG_FILE} does not exist. Exiting...")

# Retrieve the 'DEFAULT' section from the configuration
DEFAULTS = config.get('DEFAULT', {})

# Function to retrieve configuration values, allowing for environment variable overrides
def get_config_value(section, key, default=None):
    """
    Retrieve a configuration value from the specified section and key.
    The function first checks for an environment variable override.
    If no environment variable is set, it falls back to the YAML configuration.
    """
    env_key = f"{section.upper()}_{key.upper()}"
    return os.getenv(env_key, config.get(section, {}).get(key, default))

# Constants extracted from the 'DEFAULTS' section of the configuration
LOG_FILE = get_config_value('DEFAULT', 'log_file', '/var/log/lxc_autoscale.log')  # Log file path
LOCK_FILE = get_config_value('DEFAULT', 'lock_file', '/var/lock/lxc_autoscale.lock')  # Lock file path
BACKUP_DIR = get_config_value('DEFAULT', 'backup_dir', '/var/lib/lxc_autoscale/backups')  # Backup directory
RESERVE_CPU_PERCENT = int(get_config_value('DEFAULT', 'reserve_cpu_percent', 10))  # Reserved CPU percentage
RESERVE_MEMORY_MB = int(get_config_value('DEFAULT', 'reserve_memory_mb', 2048))  # Reserved memory in MB
OFF_PEAK_START = int(get_config_value('DEFAULT', 'off_peak_start', 22))  # Off-peak start hour (24-hour format)
OFF_PEAK_END = int(get_config_value('DEFAULT', 'off_peak_end', 6))  # Off-peak end hour (24-hour format)
IGNORE_LXC = set(map(str, get_config_value('DEFAULT', 'ignore_lxc', [])))  # Set of LXC containers to ignore
BEHAVIOUR = get_config_value('DEFAULT', 'behaviour', 'normal').lower()  # Script behaviour (normal, conservative, aggressive)
PROXMOX_HOSTNAME = gethostname()  # Get the hostname of the Proxmox server

# Load and associate LXC containers with their respective tier configurations
LXC_TIER_ASSOCIATIONS = {}
for section, tier_config in config.items():
    if section.startswith('TIER_'):
        # Each 'TIER_' section defines a group of LXC containers and their configurations
        nodes = tier_config.get('lxc_containers', [])
        for ctid in nodes:
            LXC_TIER_ASSOCIATIONS[str(ctid)] = tier_config  # Map container IDs to their tier configurations

# Load horizontal scaling group configurations
HORIZONTAL_SCALING_GROUPS = {}
for section, group_config in config.items():
    if section.startswith('HORIZONTAL_SCALING_GROUP_'):
        # Each 'HORIZONTAL_SCALING_GROUP_' section defines a group of containers for horizontal scaling
        if group_config.get('lxc_containers'):
            group_config['lxc_containers'] = set(map(str, group_config.get('lxc_containers', [])))
            HORIZONTAL_SCALING_GROUPS[section] = group_config  # Map the group name to its configuration

# Exporting constants and functions for use in other modules
__all__ = [
    'CONFIG_FILE', 'DEFAULTS', 'LOG_FILE', 'LOCK_FILE', 'BACKUP_DIR',
    'RESERVE_CPU_PERCENT', 'RESERVE_MEMORY_MB', 'OFF_PEAK_START',
    'OFF_PEAK_END', 'IGNORE_LXC', 'BEHAVIOUR', 'PROXMOX_HOSTNAME',
    'get_config_value', 'HORIZONTAL_SCALING_GROUPS', 'LXC_TIER_ASSOCIATIONS'
]
