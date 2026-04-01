"""Typed exceptions for LXC AutoScale.

Replaces the pattern of returning None on failure with explicit,
catchable exception types. Callers can handle specific failure
modes instead of guessing what went wrong.
"""


class AutoScaleError(Exception):
    """Base exception for all LXC AutoScale errors."""


class CommandError(AutoScaleError):
    """A subprocess or remote command failed."""

    def __init__(self, cmd, message="", returncode=None):
        self.cmd = cmd
        self.returncode = returncode
        super().__init__(f"Command failed: {cmd} — {message}")


class CommandTimeout(CommandError):
    """A command exceeded its timeout."""

    def __init__(self, cmd, timeout):
        self.timeout = timeout
        super().__init__(cmd, f"timed out after {timeout}s", returncode=None)


class ContainerNotFound(AutoScaleError):
    """A container ID was not found or is invalid."""

    def __init__(self, ctid):
        self.ctid = ctid
        super().__init__(f"Container not found: {ctid}")


class CgroupReadError(AutoScaleError):
    """Failed to read cgroup metrics for a container."""

    def __init__(self, ctid, detail=""):
        self.ctid = ctid
        super().__init__(f"Cgroup read failed for {ctid}: {detail}")


class BackendError(AutoScaleError):
    """An error in the Proxmox backend (CLI or API)."""


class ConfigurationError(AutoScaleError):
    """Invalid or missing configuration."""
