"""REST API backend — Proxmox operations via REST API (async wrapper).

Uses ``proxmoxer`` (which is sync) wrapped in ``asyncio.to_thread``.
Enable in config with ``backend: api``.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from backends.base import ProxmoxBackend

logger = logging.getLogger(__name__)

try:
    from proxmoxer import ProxmoxAPI
except ImportError:
    ProxmoxAPI = None  # type: ignore[misc,assignment]


class RESTBackend(ProxmoxBackend):
    """Proxmox backend using the REST API via ``proxmoxer``."""

    def __init__(self, app_config):
        if ProxmoxAPI is None:
            raise RuntimeError(
                "proxmoxer is required for the REST API backend. "
                "Install with: pip install proxmoxer"
            )
        api_cfg = app_config.defaults.proxmox_api
        if not api_cfg.host:
            raise ValueError("proxmox_api.host is required when backend=api")

        connect_kwargs: Dict[str, Any] = {"verify_ssl": api_cfg.verify_ssl}
        if api_cfg.token_name and api_cfg.token_value:
            connect_kwargs["token_name"] = api_cfg.token_name
            connect_kwargs["token_value"] = api_cfg.token_value
        self._api = ProxmoxAPI(api_cfg.host, user=api_cfg.user, **connect_kwargs)
        self._node: Optional[str] = None
        logger.info("Proxmox REST API connected to %s", api_cfg.host)

    def _get_node(self) -> str:
        if self._node is None:
            nodes = self._api.nodes.get()
            if not nodes:
                raise RuntimeError("No Proxmox nodes found via API")
            self._node = nodes[0]["node"]
        return self._node

    def _lxc(self, ctid: str):
        return self._api.nodes(self._get_node()).lxc(ctid)

    # -- Helpers to run sync proxmoxer calls in a thread --------------------

    async def _in_thread(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    # -- ProxmoxBackend interface -------------------------------------------

    async def list_containers(self) -> List[str]:
        try:
            containers = await self._in_thread(
                self._api.nodes(self._get_node()).lxc.get
            )
            return [str(c["vmid"]) for c in containers]
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API list_containers failed: %s", e)
            return []

    async def get_container_config(self, ctid: str) -> Optional[Dict[str, Any]]:
        try:
            cfg = await self._in_thread(self._lxc(ctid).config.get)
            return {"cores": cfg.get("cores", 1), "memory": cfg.get("memory", 512), **cfg}
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API get_container_config(%s) failed: %s", ctid, e)
            return None

    async def is_running(self, ctid: str) -> bool:
        try:
            status = await self._in_thread(self._lxc(ctid).status.current.get)
            return status.get("status") == "running"
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API is_running(%s) failed: %s", ctid, e)
            return False

    async def set_cores(self, ctid: str, cores: int) -> bool:
        try:
            await self._in_thread(self._lxc(ctid).config.put, cores=cores)
            return True
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API set_cores(%s, %d) failed: %s", ctid, cores, e)
            return False

    async def set_memory(self, ctid: str, memory_mb: int) -> bool:
        try:
            await self._in_thread(self._lxc(ctid).config.put, memory=memory_mb)
            return True
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API set_memory(%s, %d) failed: %s", ctid, memory_mb, e)
            return False

    async def start(self, ctid: str) -> bool:
        try:
            await self._in_thread(self._lxc(ctid).status.start.post)
            return True
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API start(%s) failed: %s", ctid, e)
            return False

    async def stop(self, ctid: str) -> bool:
        try:
            await self._in_thread(self._lxc(ctid).status.stop.post)
            return True
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API stop(%s) failed: %s", ctid, e)
            return False

    async def snapshot(self, ctid: str, name: str, description: str = "") -> bool:
        try:
            await self._in_thread(
                self._lxc(ctid).snapshot.post, snapname=name, description=description
            )
            return True
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API snapshot(%s, %s) failed: %s", ctid, name, e)
            return False

    async def clone(self, source: str, target: str, snapname: str = "",
                    hostname: str = "") -> bool:
        try:
            kwargs: Dict[str, Any] = {"newid": int(target)}
            if snapname:
                kwargs["snapname"] = snapname
            if hostname:
                kwargs["hostname"] = hostname
            await self._in_thread(self._lxc(source).clone.post, **kwargs)
            return True
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API clone(%s->%s) failed: %s", source, target, e)
            return False

    async def set_network(self, ctid: str, net_config: str) -> bool:
        try:
            await self._in_thread(self._lxc(ctid).config.put, net0=net_config)
            return True
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API set_network(%s) failed: %s", ctid, e)
            return False

    async def get_status(self, ctid: str) -> Optional[str]:
        try:
            status = await self._in_thread(self._lxc(ctid).status.current.get)
            return f"status: {status.get('status', 'unknown')}"
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error("API get_status(%s) failed: %s", ctid, e)
            return None

    async def run_raw(self, cmd: List[str], timeout: int = 30) -> Optional[str]:
        logger.warning("run_raw() called on REST backend — CLI-only operation: %s", cmd)
        return None
