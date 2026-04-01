"""Configuration loading and validation using Pydantic models.

Backward-compatible with existing YAML format — new fields are optional
with safe defaults.
"""

import logging
import os
import re
import stat
import sys
from typing import Any, Dict, List, Literal, Optional, Set, Union

import yaml

try:
    from pydantic import BaseModel, field_validator, model_validator
except ImportError:
    sys.exit(
        "pydantic>=2.0 is required. Install with: pip install 'pydantic>=2.0'"
    )

_CTID_RE = re.compile(r"^[0-9]+$")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SSHConfig(BaseModel):
    """SSH connection settings."""
    host: Optional[str] = None
    port: int = 22
    user: Optional[str] = None
    password: Optional[str] = None
    key_path: Optional[str] = None
    host_key_policy: Literal["reject", "system", "auto"] = "reject"


class ProxmoxAPIConfig(BaseModel):
    """Proxmox REST API settings (optional backend)."""
    enabled: bool = False
    host: Optional[str] = None
    user: Optional[str] = None
    token_name: Optional[str] = None
    token_value: Optional[str] = None
    verify_ssl: bool = True


class DefaultsConfig(BaseModel):
    """Top-level DEFAULT section of the YAML config."""
    # Paths
    log_file: str = "/var/log/lxc_autoscale.log"
    lock_file: str = "/var/lock/lxc_autoscale.lock"
    backup_dir: str = "/var/lib/lxc_autoscale/backups"

    # Daemon
    poll_interval: int = 300
    energy_mode: bool = False
    behaviour: Literal["normal", "conservative", "aggressive"] = "normal"
    timezone: str = "UTC"

    # Resource reserves
    reserve_cpu_percent: int = 10
    reserve_memory_mb: int = 2048

    # Off-peak
    off_peak_start: int = 22
    off_peak_end: int = 6

    # Thresholds
    cpu_upper_threshold: float = 80
    cpu_lower_threshold: float = 20
    memory_upper_threshold: float = 80
    memory_lower_threshold: float = 20

    # Limits
    min_cores: int = 1
    max_cores: int = 4
    min_memory: int = 512

    # Increments
    core_min_increment: int = 1
    core_max_increment: int = 2
    memory_min_increment: int = 256
    min_decrease_chunk: int = 128

    # Scaling constants
    cpu_scale_divisor: float = 2.0
    memory_scale_factor: float = 1.5
    timeout_extended: int = 60

    # Containers to ignore
    ignore_lxc: List[str] = []

    # Backend selection
    backend: Literal["cli", "api"] = "cli"
    use_remote_proxmox: bool = False

    # SSH (flattened from legacy format)
    proxmox_host: Optional[str] = None
    ssh_port: int = 22
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    ssh_host_key_policy: Literal["reject", "system", "auto"] = "reject"

    # Notification settings (kept as optional loose fields)
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_to: Optional[List[str]] = None
    gotify_url: Optional[str] = None
    gotify_token: Optional[str] = None
    uptime_kuma_webhook_url: Optional[str] = None

    # Proxmox API (nested)
    proxmox_api: ProxmoxAPIConfig = ProxmoxAPIConfig()

    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def validate_thresholds(self) -> "DefaultsConfig":
        if self.cpu_lower_threshold >= self.cpu_upper_threshold:
            raise ValueError("cpu_lower_threshold must be < cpu_upper_threshold")
        if self.memory_lower_threshold >= self.memory_upper_threshold:
            raise ValueError("memory_lower_threshold must be < memory_upper_threshold")
        if self.min_cores > self.max_cores:
            raise ValueError("min_cores must be <= max_cores")
        return self

    def get_ssh_config(self) -> SSHConfig:
        """Build SSHConfig from flattened legacy fields."""
        return SSHConfig(
            host=self.proxmox_host,
            port=self.ssh_port,
            user=self.ssh_user,
            password=self.ssh_password,
            key_path=self.ssh_key_path,
            host_key_policy=self.ssh_host_key_policy,
        )


class TierConfig(BaseModel):
    """Per-tier container scaling configuration."""
    lxc_containers: List[str] = []
    cpu_upper_threshold: float = 80
    cpu_lower_threshold: float = 20
    memory_upper_threshold: float = 80
    memory_lower_threshold: float = 20
    min_cores: int = 1
    max_cores: int = 4
    min_memory: int = 512
    core_min_increment: int = 1
    core_max_increment: int = 2
    memory_min_increment: int = 256
    min_decrease_chunk: int = 128
    cpu_pinning: Optional[str] = None
    tier_name: str = ""

    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def validate_thresholds(self) -> "TierConfig":
        if self.cpu_lower_threshold >= self.cpu_upper_threshold:
            raise ValueError("cpu_lower_threshold must be < cpu_upper_threshold")
        if self.memory_lower_threshold >= self.memory_upper_threshold:
            raise ValueError("memory_lower_threshold must be < memory_upper_threshold")
        if self.min_cores > self.max_cores:
            raise ValueError("min_cores must be <= max_cores")
        return self


class HorizontalScalingGroup(BaseModel):
    """Horizontal scaling group configuration."""
    lxc_containers: Set[str] = set()
    horiz_cpu_upper_threshold: float = 80
    horiz_cpu_lower_threshold: float = 20
    horiz_memory_upper_threshold: float = 80
    horiz_memory_lower_threshold: float = 20
    min_containers: int = 1
    max_instances: int = 5
    starting_clone_id: int = 200
    base_snapshot_name: str = ""
    clone_network_type: str = "dhcp"
    static_ip_range: List[str] = []
    scale_out_grace_period: int = 300
    scale_in_grace_period: int = 600

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Config loading (backward-compatible with raw YAML)
# ---------------------------------------------------------------------------

CONFIG_FILE = "/etc/lxc_autoscale/lxc_autoscale.yaml"

# #4: Pattern for ${ENV_VAR} or ${ENV_VAR:-default} expansion
_ENV_VAR_RE = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}')


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand ${ENV_VAR} and ${ENV_VAR:-default} in strings."""
    if isinstance(value, str):
        def _replace(m):
            var_name = m.group(1)
            default = m.group(2)
            return os.environ.get(var_name, default if default is not None else m.group(0))
        return _ENV_VAR_RE.sub(_replace, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def _load_raw_yaml(path: str) -> Dict[str, Any]:
    """Load raw YAML with ${ENV_VAR} expansion, returning empty dict on missing file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        # #4: Expand environment variables in all string values
        return _expand_env_vars(raw)
    except FileNotFoundError:
        logging.warning("Config file not found at %s, using defaults", path)
        return {}
    except yaml.YAMLError as e:
        logging.error("Error parsing config file: %s", e)
        sys.exit(1)


def _check_config_permissions(path: str) -> None:
    """Warn if the config file is readable by group or others."""
    try:
        st = os.stat(path)
        mode = st.st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            logging.warning(
                "Config file %s is readable by group/others (mode %o). "
                "Recommend chmod 0600 to protect secrets.",
                path,
                stat.S_IMODE(mode),
            )
    except OSError:
        pass


def _apply_env_overrides(raw: Dict[str, Any]) -> None:
    """Override secrets from environment variables."""
    env_map = {
        "LXC_AUTOSCALE_SSH_PASSWORD": "ssh_password",
        "LXC_AUTOSCALE_SMTP_PASSWORD": "smtp_password",
        "LXC_AUTOSCALE_GOTIFY_TOKEN": "gotify_token",
        "LXC_AUTOSCALE_UPTIME_KUMA_WEBHOOK": "uptime_kuma_webhook_url",
    }
    defaults = raw.setdefault("DEFAULT", {})
    for env_var, config_key in env_map.items():
        env_val = os.environ.get(env_var)
        if env_val is not None:
            defaults[config_key] = env_val
            logging.info("Secret '%s' overridden from env var %s", config_key, env_var)


def load_config(path: str = CONFIG_FILE) -> "AppConfig":
    """Load and validate the full application configuration."""
    _check_config_permissions(path)
    raw = _load_raw_yaml(path)
    _apply_env_overrides(raw)

    # Parse defaults
    raw_defaults = raw.get("DEFAULT", {})
    # Convert ignore_lxc items to strings
    if "ignore_lxc" in raw_defaults:
        raw_defaults["ignore_lxc"] = [str(x) for x in raw_defaults["ignore_lxc"]]
    defaults = DefaultsConfig(**raw_defaults)

    # Parse tiers
    tier_associations: Dict[str, TierConfig] = {}
    for section, values in raw.items():
        if section.startswith("TIER_") and isinstance(values, dict):
            tier_name = section[5:]
            containers = [str(c) for c in values.get("lxc_containers", [])]
            for ctid in containers:
                if not _CTID_RE.match(ctid):
                    logging.warning("Skipping invalid container ID %r in tier %s", ctid, tier_name)
                    continue
                tier_data = {**values, "tier_name": tier_name, "lxc_containers": containers}
                # Fill missing fields from defaults
                for field in TierConfig.model_fields:
                    if field not in tier_data and field not in ("lxc_containers", "tier_name", "cpu_pinning"):
                        tier_data.setdefault(field, getattr(defaults, field, None))
                tier_associations[ctid] = TierConfig(**tier_data)
                logging.info("Loaded tier config for container %s (tier: %s)", ctid, tier_name)

    # Parse horizontal scaling groups
    horiz_groups: Dict[str, HorizontalScalingGroup] = {}
    for section, group_raw in raw.items():
        if section.startswith("HORIZONTAL_SCALING_GROUP_") and isinstance(group_raw, dict):
            lxc = group_raw.get("lxc_containers")
            if isinstance(lxc, list):
                group_raw["lxc_containers"] = set(map(str, lxc))
                horiz_groups[section] = HorizontalScalingGroup(**group_raw)

    return AppConfig(
        defaults=defaults,
        tier_associations=tier_associations,
        horizontal_scaling_groups=horiz_groups,
        raw=raw,
    )


class AppConfig:
    """Top-level application configuration container."""

    def __init__(
        self,
        defaults: DefaultsConfig,
        tier_associations: Dict[str, TierConfig],
        horizontal_scaling_groups: Dict[str, HorizontalScalingGroup],
        raw: Dict[str, Any],
    ):
        self.defaults = defaults
        self.tier_associations = tier_associations
        self.horizontal_scaling_groups = horizontal_scaling_groups
        self.raw = raw

    def get_tier_or_defaults(self, ctid: str) -> Union[TierConfig, DefaultsConfig]:
        """Get tier config for a container, falling back to defaults."""
        return self.tier_associations.get(str(ctid), self.defaults)

    def get_config_value(self, section: str, key: str, default: Any = None) -> Any:
        """Legacy helper for backward compatibility."""
        if section == "DEFAULT":
            return getattr(self.defaults, key, default)
        return self.raw.get(section, {}).get(key, default)


# ---------------------------------------------------------------------------
# Module-level singleton (backward compat for existing imports)
# ---------------------------------------------------------------------------

_app_config: Optional[AppConfig] = None


def get_app_config() -> AppConfig:
    """Get or create the singleton AppConfig."""
    global _app_config
    if _app_config is None:
        _app_config = load_config()
    return _app_config


# Legacy compatibility aliases — existing code imports these
_cfg = get_app_config()
config = _cfg.raw
DEFAULTS = _cfg.defaults.model_dump()
IGNORE_LXC: Set[str] = set(str(x) for x in _cfg.defaults.ignore_lxc)
LXC_TIER_ASSOCIATIONS: Dict[str, Any] = {
    k: v.model_dump() for k, v in _cfg.tier_associations.items()
}
HORIZONTAL_SCALING_GROUPS: Dict[str, Any] = {
    k: v.model_dump() for k, v in _cfg.horizontal_scaling_groups.items()
}
# Convert sets to sets (pydantic may serialize differently)
for _k, _v in HORIZONTAL_SCALING_GROUPS.items():
    if isinstance(_v.get("lxc_containers"), (list, set)):
        _v["lxc_containers"] = set(map(str, _v["lxc_containers"]))

PROXMOX_HOSTNAME: str = os.uname().nodename
CONFIG_FILE_PATH: str = CONFIG_FILE
LOG_FILE: str = _cfg.defaults.log_file
LOCK_FILE: str = _cfg.defaults.lock_file
BACKUP_DIR: str = _cfg.defaults.backup_dir
CPU_SCALE_DIVISOR: float = _cfg.defaults.cpu_scale_divisor
MEMORY_SCALE_FACTOR: float = _cfg.defaults.memory_scale_factor
TIMEOUT_EXTENDED: int = _cfg.defaults.timeout_extended


def get_config_value(section: str, key: str, default: Any = None) -> Any:
    """Legacy function-level accessor."""
    return _cfg.get_config_value(section, key, default)


def validate_config() -> None:
    """Validate essential configuration — now handled by Pydantic validators."""
    # Pydantic already validates on construction; this is kept for
    # backward compatibility with code that calls it explicitly.
    pass


# Run validation on import (same behavior as before)
validate_config()

__all__ = [
    "AppConfig",
    "DefaultsConfig",
    "TierConfig",
    "SSHConfig",
    "ProxmoxAPIConfig",
    "HorizontalScalingGroup",
    "get_app_config",
    "load_config",
    # Legacy aliases
    "CONFIG_FILE",
    "DEFAULTS",
    "LOG_FILE",
    "LOCK_FILE",
    "BACKUP_DIR",
    "IGNORE_LXC",
    "PROXMOX_HOSTNAME",
    "CPU_SCALE_DIVISOR",
    "MEMORY_SCALE_FACTOR",
    "TIMEOUT_EXTENDED",
    "get_config_value",
    "HORIZONTAL_SCALING_GROUPS",
    "LXC_TIER_ASSOCIATIONS",
    "config",
]
