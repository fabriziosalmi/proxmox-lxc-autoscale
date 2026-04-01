"""Abstract interface for Proxmox operations (async)."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ProxmoxBackend(ABC):
    """Abstract base for all Proxmox backend implementations."""

    @abstractmethod
    async def list_containers(self) -> List[str]: ...

    @abstractmethod
    async def get_container_config(self, ctid: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    async def is_running(self, ctid: str) -> bool: ...

    @abstractmethod
    async def set_cores(self, ctid: str, cores: int) -> bool: ...

    @abstractmethod
    async def set_memory(self, ctid: str, memory_mb: int) -> bool: ...

    @abstractmethod
    async def start(self, ctid: str) -> bool: ...

    @abstractmethod
    async def stop(self, ctid: str) -> bool: ...

    @abstractmethod
    async def snapshot(self, ctid: str, name: str, description: str = "") -> bool: ...

    @abstractmethod
    async def clone(self, source: str, target: str, snapname: str = "",
                    hostname: str = "") -> bool: ...

    @abstractmethod
    async def set_network(self, ctid: str, net_config: str) -> bool: ...

    @abstractmethod
    async def get_status(self, ctid: str) -> Optional[str]: ...

    @abstractmethod
    async def run_raw(self, cmd: List[str], timeout: int = 30) -> Optional[str]: ...
