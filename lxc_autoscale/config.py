import logging
import os
import sys
from socket import gethostname
from typing import Any, Dict, List, Set, Union

import yaml
from logging_setup import setup_logging  # Import the logging setup function

CONFIG_FILE = "/etc/lxc_autoscale/lxc_autoscale.yaml"

if not os.path.exists(CONFIG_FILE):
    sys.exit(f"Configuration file {CONFIG_FILE} does not exist. Exiting...")

with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
    config: Dict[str, Any] = yaml.safe_load(file)

if not isinstance(config, dict):
    sys.exit("Invalid configuration format. Expected a dictionary.")

# --- Default Configuration (moved to top) ---
DEFAULTS: Dict[str, Any] = config.get('DEFAULTS', {})

def load_tier_configurations() -> Dict[str, Dict[str, Any]]:
    """Load and validate tier configurations."""
    tier_configs: Dict[str, Dict[str, Any]] = {}
    
    # Setup logging based on the configuration
    setup_logging()
    
    for section, values in config.items():
        if section.startswith('TIER_'):
            tier_name = section[5:]
            if isinstance(values, dict) and 'lxc_containers' in values:
                # Convert container IDs to strings for consistent comparison
                containers = [str(ctid) for ctid in values['lxc_containers']]
                for ctid in containers:
                    tier_configs[ctid] = {
                        'cpu_upper_threshold': values.get('cpu_upper_threshold', DEFAULTS['cpu_upper_threshold']),
                        'cpu_lower_threshold': values.get('cpu_lower_threshold', DEFAULTS['cpu_lower_threshold']),
                        'memory_upper_threshold': values.get('memory_upper_threshold', DEFAULTS['memory_upper_threshold']),
                        'memory_lower_threshold': values.get('memory_lower_threshold', DEFAULTS['memory_lower_threshold']),
                        'min_cores': values.get('min_cores', DEFAULTS['min_cores']),
                        'max_cores': values.get('max_cores', DEFAULTS['max_cores']),
                        'min_memory': values.get('min_memory', DEFAULTS['min_memory']),
                        'core_min_increment': values.get('core_min_increment', DEFAULTS.get('core_min_increment', 1)),
                        'core_max_increment': values.get('core_max_increment', DEFAULTS.get('core_max_increment', 2)),
                        'memory_min_increment': values.get('memory_min_increment', DEFAULTS.get('memory_min_increment', 256)),
                        'min_decrease_chunk': values.get('min_decrease_chunk', DEFAULTS.get('min_decrease_chunk', 128)),
                        'tier_name': tier_name
                    }
                    logging.info(f"Loaded tier configuration for container {ctid} from tier {tier_name}")

    return tier_configs

def get_config_value(section: str, key: str, default: Any) -> Any:
    """Retrieve a configuration value with a fallback to a default."""
    # Map "DEFAULT" to "DEFAULTS" to match YAML
    if section == "DEFAULT":
        section = "DEFAULTS"
    return config.get(section, {}).get(key, default)

def validate_config() -> None:
    """Validate essential configuration values."""
    required_defaults = [
        'reserve_cpu_percent',
        'reserve_memory_mb',
        'off_peak_start',
        'off_peak_end',
        'behaviour',
        'cpu_upper_threshold',
        'cpu_lower_threshold',
        'memory_upper_threshold',
        'memory_lower_threshold'
    ]
    
    missing = [key for key in required_defaults if key not in DEFAULTS]
    if missing:
        sys.exit(f"Missing required configuration values in DEFAULTS: {', '.join(missing)}")

    # Validate thresholds
    if DEFAULTS['cpu_lower_threshold'] >= DEFAULTS['cpu_upper_threshold']:
        sys.exit("CPU lower threshold must be less than upper threshold")
    
    if DEFAULTS['memory_lower_threshold'] >= DEFAULTS['memory_upper_threshold']:
        sys.exit("Memory lower threshold must be less than upper threshold")

# Call validation after loading config
validate_config()

# --- Resource Scaling Constants ---
CPU_SCALE_DIVISOR: float = DEFAULTS.get('cpu_scale_divisor', 2.0)
MEMORY_SCALE_FACTOR: float = DEFAULTS.get('memory_scale_factor', 1.5)
TIMEOUT_EXTENDED: int = DEFAULTS.get('timeout_extended', 60)

# --- General Configuration ---
LOG_FILE: str = get_config_value('DEFAULT', 'log_file', '/var/log/lxc_autoscale.log')
LOCK_FILE: str = get_config_value('DEFAULT', 'lock_file', '/var/lock/lxc_autoscale.lock')
BACKUP_DIR: str = get_config_value('DEFAULT', 'backup_dir', '/var/lib/lxc_autoscale/backups')
IGNORE_LXC: Set[str] = set(str(x) for x in DEFAULTS.get('ignore_lxc', []))
PROXMOX_HOSTNAME: str = gethostname()

# --- Load Tier Configurations ---
LXC_TIER_ASSOCIATIONS = load_tier_configurations()

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
    'IGNORE_LXC',
    'PROXMOX_HOSTNAME',
    'CPU_SCALE_DIVISOR',
    'MEMORY_SCALE_FACTOR',
    'TIMEOUT_EXTENDED',
    'get_config_value',
    'HORIZONTAL_SCALING_GROUPS',
    'LXC_TIER_ASSOCIATIONS',
]