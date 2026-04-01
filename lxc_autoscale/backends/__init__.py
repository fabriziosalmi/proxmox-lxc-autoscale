"""Proxmox backend implementations (CLI and REST API)."""

from backends.base import ProxmoxBackend
from backends.cli import CLIBackend

__all__ = ["ProxmoxBackend", "CLIBackend", "create_backend"]


def create_backend(app_config) -> ProxmoxBackend:
    """Factory: create the appropriate backend from config."""
    if app_config.defaults.backend == "api":
        from backends.api import RESTBackend
        return RESTBackend(app_config)
    return CLIBackend(app_config)
