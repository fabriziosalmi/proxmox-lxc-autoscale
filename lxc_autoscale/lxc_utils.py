"""Utility functions for LXC container management.

Provides CPU/memory measurement (cgroup-based), container data collection,
CPU topology detection, and backup/rollback operations.

Performance optimizations:
- #2: No sleep on first CPU sample — stores raw reading, calculates delta next cycle
- #3: Core count cached per-container, passed from collector, not re-queried
- #4: Memory read from host-side cgroup (like CPU), no pct exec
- #7: Backup skipped if settings unchanged
- #8: CPU pinning state cached, only applied on change
- #10: JSON log uses persistent file handle with periodic flush
"""

import asyncio
import json
import logging
import os
import re
import time as _time
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, Union
from zoneinfo import ZoneInfo

from config import (
    BACKUP_DIR, IGNORE_LXC, LOG_FILE, PROXMOX_HOSTNAME,
    LXC_TIER_ASSOCIATIONS, config, get_config_value, get_app_config,
)

logger = logging.getLogger(__name__)

# Per-container locks — created on demand for concurrent async tasks.
_container_locks: Dict[str, asyncio.Lock] = {}
_locks_mutex = Lock()


def _get_container_lock(ctid: str) -> asyncio.Lock:
    with _locks_mutex:
        if ctid not in _container_locks:
            _container_locks[ctid] = asyncio.Lock()
        return _container_locks[ctid]


_CTID_RE = re.compile(r'^[0-9]+$')


def validate_container_id(ctid: str) -> None:
    if not _CTID_RE.match(ctid):
        raise ValueError(f"Invalid container ID: {ctid!r}")


# ---------------------------------------------------------------------------
# Async command execution
# ---------------------------------------------------------------------------

async def run_command(cmd: Union[str, List[str]], timeout: int = 30) -> Optional[str]:
    cfg = get_app_config()
    if cfg.defaults.use_remote_proxmox:
        return await _run_remote_command(cmd, timeout)
    return await run_local_command(cmd, timeout)


async def run_local_command(cmd: Union[str, List[str]], timeout: int = 30) -> Optional[str]:
    if isinstance(cmd, str):
        import shlex
        cmd = shlex.split(cmd)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode == 0:
            return stdout.decode('utf-8').strip()
        logger.error("Command failed (rc=%d): %s — %s",
                     proc.returncode, cmd, stderr.decode('utf-8').strip())
    except asyncio.TimeoutError:
        logger.error("Command timed out after %ds: %s", timeout, cmd)
        proc.kill()
        await proc.wait()
    except OSError as e:
        logger.error("OS error executing %s: %s", cmd, e)
    return None


_ssh_pool = None

async def _run_remote_command(cmd: Union[str, List[str]], timeout: int = 30) -> Optional[str]:
    from ssh import AsyncSSHPool
    cfg = get_app_config()
    global _ssh_pool
    if _ssh_pool is None:
        _ssh_pool = AsyncSSHPool(cfg.defaults.get_ssh_config())
    return await _ssh_pool.run_command(cmd, timeout)


# ---------------------------------------------------------------------------
# Container queries
# ---------------------------------------------------------------------------

async def get_containers() -> List[str]:
    output = await run_command(["pct", "list"])
    if not output:
        return []
    container_list = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        ctid = parts[0]
        try:
            validate_container_id(ctid)
            container_list.append(ctid)
        except ValueError:
            logger.warning("Skipping invalid ID from pct list: %r", ctid)
    return [ctid for ctid in container_list if ctid and not is_ignored(ctid)]


def is_ignored(ctid: str) -> bool:
    return str(ctid) in IGNORE_LXC


async def is_container_running(ctid: str) -> bool:
    validate_container_id(ctid)
    status = await run_command(["pct", "status", ctid])
    return bool(status and "status: running" in status.lower())


# ---------------------------------------------------------------------------
# #7: Backup with change detection — skip if settings unchanged
# ---------------------------------------------------------------------------

_last_backup_settings: Dict[str, Dict[str, Any]] = {}


async def backup_container_settings(ctid: str, settings: Dict[str, Any]) -> None:
    """Write backup only if settings changed since last write."""
    if _last_backup_settings.get(ctid) == settings:
        return  # nothing changed, skip I/O
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True, mode=0o700)
        backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
        # Symlink-safe: resolve and verify path stays within BACKUP_DIR
        real_dir = os.path.realpath(BACKUP_DIR)
        real_file = os.path.realpath(backup_file)
        if not real_file.startswith(real_dir + os.sep):
            logger.error("Symlink attack detected on backup path: %s", backup_file)
            return
        async with _get_container_lock(ctid):
            fd = os.open(real_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(settings, f)
        _last_backup_settings[ctid] = settings.copy()
        logger.debug("Backup saved for container %s", ctid)
    except OSError as e:
        logger.error("Failed to backup settings for %s: %s", ctid, e)


async def load_backup_settings(ctid: str) -> Optional[Dict[str, Any]]:
    try:
        backup_file = os.path.join(BACKUP_DIR, f"{ctid}_backup.json")
        if os.path.exists(backup_file):
            async with _get_container_lock(ctid):
                with open(backup_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        logger.warning("No backup found for container %s", ctid)
        return None
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Failed to load backup for %s: %s", ctid, e)
        return None


async def rollback_container_settings(ctid: str) -> None:
    settings = await load_backup_settings(ctid)
    if settings:
        logger.info("Rolling back container %s to backup settings", ctid)
        validate_container_id(ctid)
        await run_command(["pct", "set", ctid, "-cores", str(settings['cores'])])
        await run_command(["pct", "set", ctid, "-memory", str(settings['memory'])])


# ---------------------------------------------------------------------------
# #10: Buffered JSON event log — persistent file handle, periodic flush
# ---------------------------------------------------------------------------

_json_log_file = None
_json_log_lock = asyncio.Lock()
_JSON_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB — rotate when exceeded
_JSON_LOG_BACKUP_COUNT = 3


def _get_json_log_path() -> str:
    return LOG_FILE.replace('.log', '.json')


def _rotate_json_log_if_needed() -> None:
    """#7: Rotate JSON log file if it exceeds size limit."""
    path = _get_json_log_path()
    try:
        if os.path.exists(path) and os.path.getsize(path) > _JSON_LOG_MAX_BYTES:
            global _json_log_file
            if _json_log_file and not _json_log_file.closed:
                _json_log_file.close()
                _json_log_file = None
            # Rotate: .json -> .json.1, .json.1 -> .json.2, etc.
            for i in range(_JSON_LOG_BACKUP_COUNT, 0, -1):
                src = f"{path}.{i}" if i > 0 else path
                dst = f"{path}.{i + 1}" if i < _JSON_LOG_BACKUP_COUNT else None
                if dst and os.path.exists(src):
                    os.replace(src, dst)
            if os.path.exists(path):
                os.replace(path, f"{path}.1")
            logger.debug("JSON log rotated: %s", path)
    except OSError as e:
        logger.warning("Failed to rotate JSON log: %s", e)


def _get_json_log_handle():
    """Get or open a persistent file handle for JSON event logging."""
    global _json_log_file
    _rotate_json_log_if_needed()
    if _json_log_file is None or _json_log_file.closed:
        json_path = _get_json_log_path()
        os.makedirs(os.path.dirname(json_path) or '.', exist_ok=True)
        fd = os.open(json_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        _json_log_file = os.fdopen(fd, 'a', encoding='utf-8', buffering=1)
    return _json_log_file


async def log_json_event(ctid: str, action: str, resource_change) -> None:
    cfg = get_app_config()
    tz = ZoneInfo(cfg.defaults.timezone)
    log_data = {
        "timestamp": datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S %Z'),
        "proxmox_host": PROXMOX_HOSTNAME,
        "container_id": ctid,
        "action": action,
        "change": resource_change,
    }
    async with _json_log_lock:
        fh = _get_json_log_handle()
        fh.write(json.dumps(log_data) + '\n')
        fh.flush()


def prune_old_backups(max_per_container: int = 5) -> None:
    """Remove old backup files, keeping only the most recent N per container."""
    if not os.path.isdir(BACKUP_DIR):
        return
    real_dir = os.path.realpath(BACKUP_DIR)
    try:
        backup_files = sorted(
            (os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)
             if f.endswith('_backup.json')),
            key=lambda p: os.path.getmtime(p),
        )
        max_total = max_per_container * 100
        if len(backup_files) > max_total:
            for old_file in backup_files[:len(backup_files) - max_total]:
                # Symlink-safe: verify file is inside BACKUP_DIR
                real_path = os.path.realpath(old_file)
                if not real_path.startswith(real_dir + os.sep):
                    logger.warning("Refusing to delete file outside backup dir: %s", old_file)
                    continue
                os.unlink(real_path)
                logger.debug("Pruned old backup: %s", old_file)
    except OSError as e:
        logger.warning("Failed to prune backups: %s", e)


# ---------------------------------------------------------------------------
# Host resource queries
# ---------------------------------------------------------------------------

async def get_total_cores() -> int:
    total_cores = int(await run_command(["nproc"]) or 0)
    reserve_pct = int(get_config_value('DEFAULT', 'reserve_cpu_percent', 10))
    reserved = max(1, int(total_cores * reserve_pct / 100))
    return total_cores - reserved


async def get_total_memory() -> int:
    try:
        output = await run_command(["free", "-m"])
        total_memory = 0
        if output:
            for line in output.splitlines():
                if line.startswith("Mem:"):
                    total_memory = int(line.split()[1])
                    break
    except (ValueError, OSError) as e:
        logger.error("Failed to get total memory: %s", e)
        total_memory = 0
    reserve_mb = int(get_config_value('DEFAULT', 'reserve_memory_mb', 2048))
    return max(0, total_memory - reserve_mb)


# ---------------------------------------------------------------------------
# CPU topology detection & core pinning
# ---------------------------------------------------------------------------

_CPU_RANGE_RE = re.compile(r'^[0-9]+([-,][0-9]+)*$')
_cached_topology: Optional[Dict[str, Any]] = None


def _cpus_to_range(cpus: List[int]) -> str:
    if not cpus:
        return ""
    ranges: List[str] = []
    start = end = cpus[0]
    for cpu in cpus[1:]:
        if cpu == end + 1:
            end = cpu
        else:
            ranges.append(f"{start}-{end}" if end > start else str(start))
            start = end = cpu
    ranges.append(f"{start}-{end}" if end > start else str(start))
    return ",".join(ranges)


async def detect_cpu_topology() -> Dict[str, Any]:
    global _cached_topology
    if _cached_topology is not None:
        return _cached_topology
    nproc_out = await run_command(["nproc"])
    if not nproc_out:
        _cached_topology = {'p_cores': [], 'e_cores': [], 'all': [], 'hybrid': False}
        return _cached_topology
    num_cpus = int(nproc_out)
    all_cpus = list(range(num_cpus))
    script = (
        'for f in /sys/devices/system/cpu/cpu[0-9]*/topology/core_type; do '
        '[ -f "$f" ] && printf "%s:%s\\n" '
        '"$(basename $(dirname $(dirname "$f")))" "$(cat "$f")"; done'
    )
    output = await run_command(["sh", "-c", script])
    p_cores: List[int] = []
    e_cores: List[int] = []
    if output:
        for line in output.strip().splitlines():
            if ':' not in line:
                continue
            cpu_name, core_type = line.split(':', 1)
            try:
                cpu_id = int(cpu_name.replace('cpu', ''))
            except ValueError:
                continue
            if core_type.strip().lower() in ('atom', 'efficiency'):
                e_cores.append(cpu_id)
            else:
                p_cores.append(cpu_id)
    hybrid = bool(p_cores and e_cores)
    if not hybrid:
        p_cores = all_cpus
        e_cores = []
    _cached_topology = {
        'p_cores': sorted(p_cores), 'e_cores': sorted(e_cores),
        'all': sorted(all_cpus), 'hybrid': hybrid,
    }
    return _cached_topology


async def resolve_cpu_pinning(pinning_config: str) -> Optional[str]:
    val = pinning_config.strip().lower()
    topo = await detect_cpu_topology()
    if val == 'p-cores':
        return _cpus_to_range(topo['p_cores']) if topo['p_cores'] else None
    elif val == 'e-cores':
        return _cpus_to_range(topo['e_cores']) if topo['e_cores'] else None
    elif val == 'all':
        return _cpus_to_range(topo['all'])
    elif _CPU_RANGE_RE.match(val):
        return val
    logger.error("Invalid cpu_pinning value: %r", pinning_config)
    return None


# ---------------------------------------------------------------------------
# #8: CPU pinning with state cache — only apply on change
# ---------------------------------------------------------------------------

_applied_pinning: Dict[str, str] = {}  # ctid -> last applied cpu_range


async def apply_cpu_pinning(ctid: str, cpu_range: str) -> bool:
    """Apply CPU core pinning only if it differs from last applied state."""
    validate_container_id(ctid)
    if not _CPU_RANGE_RE.match(cpu_range):
        logger.error("Invalid CPU range %r for container %s", cpu_range, ctid)
        return False

    # Skip if already applied this exact range
    if _applied_pinning.get(ctid) == cpu_range:
        logger.debug("Container %s: pinning unchanged (%s), skipping", ctid, cpu_range)
        return True

    conf_path = f"/etc/pve/lxc/{ctid}.conf"
    target_line = f"lxc.cgroup2.cpuset.cpus: {cpu_range}"

    cfg = get_app_config()
    if cfg.defaults.use_remote_proxmox:
        # Remote: read file, build new content in Python, write back via tee.
        # Never pass user-controlled data through sed or sh -c.
        current = await run_command(["cat", conf_path])
        if current is None:
            logger.error("Cannot read config file %s", conf_path)
            return False
        lines = current.splitlines(True)
        found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == target_line:
                _applied_pinning[ctid] = cpu_range
                return True
            if stripped.startswith('lxc.cgroup2.cpuset.cpus:'):
                lines[i] = target_line + '\n'
                found = True
        if not found:
            lines.append(target_line + '\n')
        new_content = ''.join(lines)
        # Write back atomically via tee (stdin, no shell interpolation)
        proc = await asyncio.create_subprocess_exec(
            "tee", conf_path,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate(input=new_content.encode())
        if proc.returncode != 0:
            logger.error("Failed to set CPU pinning for container %s", ctid)
            return False
    else:
        # Local: native Python file I/O — no shell, no injection risk
        try:
            real_conf = os.path.realpath(conf_path)
            if not real_conf.startswith('/etc/pve/lxc/'):
                logger.error("Symlink attack on config path: %s -> %s", conf_path, real_conf)
                return False
            with open(real_conf, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            found = False
            for i, line in enumerate(lines):
                if line.strip() == target_line:
                    _applied_pinning[ctid] = cpu_range
                    return True
                if line.startswith('lxc.cgroup2.cpuset.cpus:'):
                    lines[i] = target_line + '\n'
                    found = True
            if not found:
                lines.append(target_line + '\n')
            with open(real_conf, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except OSError as e:
            logger.error("Failed to set CPU pinning for container %s: %s", ctid, e)
            return False

    _applied_pinning[ctid] = cpu_range
    logger.info("Container %s: CPU pinning set to %s", ctid, cpu_range)
    return True


# ---------------------------------------------------------------------------
# #2 + #3: CPU measurement — zero-sleep, core count passed from collector
# ---------------------------------------------------------------------------

_cgroup_path_cache: Dict[str, str] = {}
_prev_cpu_readings: Dict[str, Tuple[float, float]] = {}
_cgroup_negative_cache: Dict[str, int] = {}  # ctid -> cycles remaining until retry
_NEGATIVE_CACHE_TTL = 5  # skip cgroup discovery for N poll cycles

# #3: Core count cache — populated by collect_data_for_container
_core_count_cache: Dict[str, int] = {}


def evict_stale_caches(active_ctids: set) -> None:
    """Remove cache entries for containers no longer in the active set.

    Call once per poll cycle after get_containers() to prevent unbounded
    cache growth when containers are deleted or stopped.
    """
    for cache in (
        _cgroup_path_cache, _prev_cpu_readings, _core_count_cache,
        _cgroup_mem_path_cache, _cgroup_mem_negative_cache,
        _applied_pinning, _last_backup_settings,
        _cgroup_negative_cache,
    ):
        stale = [k for k in cache if k not in active_ctids]
        for k in stale:
            del cache[k]
    # Container locks: remove stale ones (safe if not currently held)
    with _locks_mutex:
        stale_locks = [k for k in _container_locks if k not in active_ctids]
        for k in stale_locks:
            lock = _container_locks[k]
            if not lock.locked():
                del _container_locks[k]


def set_cached_core_count(ctid: str, cores: int) -> None:
    """Store core count from the collector so CPU calc doesn't re-query."""
    _core_count_cache[ctid] = cores


async def _get_num_cpus(ctid: str) -> int:
    """Get core count — use cache first, fall back to pct config."""
    cached = _core_count_cache.get(ctid)
    if cached:
        return cached
    validate_container_id(ctid)
    config_output = await run_command(["pct", "config", ctid])
    if config_output:
        for line in config_output.splitlines():
            if line.startswith("cores:"):
                cores = int(line.split()[1])
                _core_count_cache[ctid] = cores
                return cores
    return 1


async def _read_cgroup_cpu_usec(ctid: str) -> Optional[float]:
    validate_container_id(ctid)
    # Negative cache: skip discovery if recently failed
    neg = _cgroup_negative_cache.get(ctid, 0)
    if neg > 0:
        _cgroup_negative_cache[ctid] = neg - 1
        return None
    # Positive cache: use known working path
    cached = _cgroup_path_cache.get(ctid)
    if cached:
        val = await _parse_cgroup_file(cached)
        if val is not None:
            return val
        del _cgroup_path_cache[ctid]
    v2_paths = [
        f"/sys/fs/cgroup/lxc.payload.{ctid}/cpu.stat",
        f"/sys/fs/cgroup/lxc/{ctid}/cpu.stat",
    ]
    for path in v2_paths:
        val = await _parse_cgroup_v2(path)
        if val is not None:
            _cgroup_path_cache[ctid] = path
            return val
    v1_path = f"/sys/fs/cgroup/cpuacct/lxc/{ctid}/cpuacct.usage"
    val = await _parse_cgroup_v1(v1_path)
    if val is not None:
        _cgroup_path_cache[ctid] = v1_path
        return val
    # All paths failed — negative cache to avoid retrying every cycle
    _cgroup_negative_cache[ctid] = _NEGATIVE_CACHE_TTL
    return None


async def _parse_cgroup_file(path: str) -> Optional[float]:
    return await (_parse_cgroup_v2(path) if path.endswith("cpu.stat") else _parse_cgroup_v1(path))


async def _parse_cgroup_v2(path: str) -> Optional[float]:
    output = await run_command(["cat", path])
    if not output:
        return None
    for line in output.splitlines():
        if line.startswith("usage_usec"):
            try:
                return float(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


async def _parse_cgroup_v1(path: str) -> Optional[float]:
    output = await run_command(["cat", path])
    if not output:
        return None
    try:
        return float(output.strip()) / 1000.0
    except ValueError:
        return None


async def _cgroup_method(ctid: str) -> float:
    """CPU usage from host-side cgroup — #2: NEVER sleeps.

    On first call, stores the raw sample and returns -1.0 (sentinel for
    'no data yet'). On second call, computes the delta from the cached
    previous sample taken during the last poll cycle.
    """
    usage_usec = await _read_cgroup_cpu_usec(ctid)
    if usage_usec is None:
        raise RuntimeError("cgroup CPU path not found")

    now = _time.monotonic()
    prev = _prev_cpu_readings.get(ctid)

    if prev is None:
        # First sample — just store it, return sentinel. No sleep.
        _prev_cpu_readings[ctid] = (usage_usec, now)
        return -1.0  # sentinel: "no delta available yet"

    prev_usec, prev_ts = prev
    _prev_cpu_readings[ctid] = (usage_usec, now)
    delta_usec = usage_usec - prev_usec
    delta_sec = now - prev_ts

    if delta_sec <= 0 or delta_usec < 0:
        _prev_cpu_readings.pop(ctid, None)
        return 0.0

    num_cpus = await _get_num_cpus(ctid)
    cpu_pct = (delta_usec / (delta_sec * 1_000_000 * num_cpus)) * 100
    return round(max(min(cpu_pct, 100.0), 0.0), 2)


async def _proc_stat_method(ctid: str) -> float:
    """CPU via /proc/stat — fallback. Still needs 2s sleep (pct exec)."""
    validate_container_id(ctid)

    async def _get_cpu_line() -> str:
        out = await run_command(["pct", "exec", ctid, "--", "cat", "/proc/stat"])
        if not out:
            raise RuntimeError("Failed to read /proc/stat")
        for line in out.splitlines():
            if line.startswith("cpu "):
                return line
        raise RuntimeError("/proc/stat has no aggregate cpu line")

    initial = await _get_cpu_line()
    iv = list(map(int, initial.split()[1:]))
    initial_idle, initial_total = iv[3] + iv[4], sum(iv)
    await asyncio.sleep(2)
    current = await _get_cpu_line()
    cv = list(map(int, current.split()[1:]))
    current_idle, current_total = cv[3] + cv[4], sum(cv)
    dt, di = current_total - initial_total, current_idle - initial_idle
    if dt <= 0:
        return 0.0
    return round(max(min(((dt - di) / dt) * 100, 100.0), 0.0), 2)


async def _loadavg_method(ctid: str) -> float:
    validate_container_id(ctid)
    out = await run_command(["pct", "exec", ctid, "--", "cat", "/proc/loadavg"])
    if not out:
        raise RuntimeError("Failed to read /proc/loadavg")
    loadavg = float(out.split()[0])
    num_cpus = await _get_num_cpus(ctid)
    return round(min((loadavg / num_cpus) * 100, 100.0), 2)


async def get_cpu_usage(ctid: str) -> float:
    """Get CPU usage. Returns 0.0 on first cycle (no delta yet)."""
    validate_container_id(ctid)
    methods = [
        ("cgroup", _cgroup_method),
        ("proc_stat", _proc_stat_method),
        ("loadavg", _loadavg_method),
    ]
    for name, method in methods:
        try:
            cpu = await method(ctid)
            if cpu == -1.0:
                # First sample (cgroup), no delta yet — skip scaling this cycle
                logger.info("CPU for %s: first sample stored, will compute next cycle", ctid)
                return 0.0
            if cpu is not None and cpu >= 0.0:
                logger.info("CPU usage for %s using %s: %.2f%%", ctid, name, cpu)
                return cpu
        except (RuntimeError, ValueError, OSError) as e:
            logger.debug("%s failed for %s: %s", name, ctid, e)
    logger.error("All CPU methods failed for container %s", ctid)
    return 0.0


# ---------------------------------------------------------------------------
# #4: Memory from cgroup — no pct exec needed
# ---------------------------------------------------------------------------

_cgroup_mem_path_cache: Dict[str, Tuple[str, str]] = {}  # ctid -> (current_path, stat_path)


_cgroup_mem_negative_cache: Dict[str, int] = {}


async def _read_cgroup_memory(ctid: str) -> Optional[Tuple[int, int]]:
    """Read memory usage from host-side cgroup. Returns (used_bytes, total_bytes)."""
    validate_container_id(ctid)
    neg = _cgroup_mem_negative_cache.get(ctid, 0)
    if neg > 0:
        _cgroup_mem_negative_cache[ctid] = neg - 1
        return None

    cached = _cgroup_mem_path_cache.get(ctid)
    if cached:
        current_path, stat_path = cached
        used = await _read_mem_file(current_path)
        limit = await _read_mem_limit(stat_path)
        if used is not None and limit is not None:
            return used, limit
        del _cgroup_mem_path_cache[ctid]

    # cgroup v2 candidates
    v2_bases = [
        f"/sys/fs/cgroup/lxc.payload.{ctid}",
        f"/sys/fs/cgroup/lxc/{ctid}",
    ]
    for base in v2_bases:
        current_p = f"{base}/memory.current"
        stat_p = f"{base}/memory.max"
        used = await _read_mem_file(current_p)
        limit = await _read_mem_file(stat_p)
        if used is not None and limit is not None and limit > 0:
            _cgroup_mem_path_cache[ctid] = (current_p, stat_p)
            return used, limit

    # cgroup v1 fallback
    v1_usage = f"/sys/fs/cgroup/memory/lxc/{ctid}/memory.usage_in_bytes"
    v1_limit = f"/sys/fs/cgroup/memory/lxc/{ctid}/memory.limit_in_bytes"
    used = await _read_mem_file(v1_usage)
    limit = await _read_mem_file(v1_limit)
    if used is not None and limit is not None and limit > 0:
        _cgroup_mem_path_cache[ctid] = (v1_usage, v1_limit)
        return used, limit

    _cgroup_mem_negative_cache[ctid] = _NEGATIVE_CACHE_TTL
    return None


async def _read_mem_file(path: str) -> Optional[int]:
    output = await run_command(["cat", path])
    if not output:
        return None
    val = output.strip()
    # "max" in cgroup v2 memory.max means unlimited
    if val == "max":
        return None
    try:
        return int(val)
    except ValueError:
        return None


async def _read_mem_limit(path: str) -> Optional[int]:
    """Read memory limit, handling cgroup v2 'max' as None."""
    return await _read_mem_file(path)


async def get_memory_usage(ctid: str) -> float:
    """Get memory usage % — cgroup first (fast), pct exec fallback (slow)."""
    validate_container_id(ctid)

    # Try cgroup (host-side, no pct exec)
    result = await _read_cgroup_memory(ctid)
    if result is not None:
        used, total = result
        if total > 0:
            pct = (used / total) * 100
            logger.info("Memory usage for %s (cgroup): %.2f%%", ctid, pct)
            return round(max(min(pct, 100.0), 0.0), 2)

    # Fallback: pct exec (slow, enters container)
    meminfo_output = await run_command(["pct", "exec", ctid, "--", "cat", "/proc/meminfo"])
    if meminfo_output:
        try:
            total = 0
            mem_available = None
            for line in meminfo_output.splitlines():
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_available = int(line.split()[1])
            if total and mem_available is not None:
                pct = ((total - mem_available) * 100) / total
                logger.info("Memory usage for %s (procfs): %.2f%%", ctid, pct)
                return pct
        except (ValueError, IndexError):
            logger.error("Failed to parse memory info for %s", ctid)
    logger.error("Failed to get memory usage for %s", ctid)
    return 0.0


# ---------------------------------------------------------------------------
# Container data collection
# ---------------------------------------------------------------------------

async def get_container_data(ctid: str) -> Optional[Dict[str, Any]]:
    if is_ignored(ctid) or not await is_container_running(ctid):
        return None
    try:
        config_output = await run_command(["pct", "config", ctid])
        cores = memory = 0
        if config_output:
            for line in config_output.splitlines():
                if line.startswith("cores:"):
                    cores = int(line.split()[1])
                elif line.startswith("memory:"):
                    memory = int(line.split()[1])
        # #3: Cache core count for CPU calc
        set_cached_core_count(ctid, cores)
        settings = {"cores": cores, "memory": memory}
        await backup_container_settings(ctid, settings)
        return {
            "cpu": await get_cpu_usage(ctid),
            "mem": await get_memory_usage(ctid),
            "initial_cores": cores,
            "initial_memory": memory,
        }
    except (ValueError, OSError) as e:
        logger.error("Error collecting data for %s: %s", ctid, e)
        return None


def prioritize_containers(
    containers: Dict[str, Dict[str, Any]],
) -> List[Tuple[str, Dict[str, Any]]]:
    """Sort containers by resource usage priority."""
    if not containers:
        return []
    try:
        return sorted(
            containers.items(),
            key=lambda item: (item[1]['cpu'], item[1]['mem']),
            reverse=True,
        )
    except (KeyError, TypeError) as e:
        logger.error("Error prioritizing containers: %s", e)
        return []


def get_container_config(ctid: str) -> Dict[str, Any]:
    from config import DEFAULTS
    return LXC_TIER_ASSOCIATIONS.get(ctid, DEFAULTS)


# ---------------------------------------------------------------------------
# Name generation (pure, sync)
# ---------------------------------------------------------------------------

def generate_unique_snapshot_name(base_name: str) -> str:
    cfg = get_app_config()
    tz = ZoneInfo(cfg.defaults.timezone)
    return f"{base_name}-{datetime.now(tz).strftime('%Y%m%d%H%M%S')}"


def generate_cloned_hostname(base_name: str, clone_number: int) -> str:
    sanitised = re.sub(r'[^a-zA-Z0-9-]', '-', str(base_name)).strip('-')
    if not sanitised:
        sanitised = 'container'
    return f"{sanitised}-cloned-{clone_number}"
