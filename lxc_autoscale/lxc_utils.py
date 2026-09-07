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
from typing import Any, Dict, List, Optional, Tuple, Union
from zoneinfo import ZoneInfo

from config import (
    BACKUP_DIR, IGNORE_LXC, LOG_FILE, PROXMOX_HOSTNAME,
    LXC_TIER_ASSOCIATIONS, config, get_config_value, get_app_config,
)
from state import get_state_cache

logger = logging.getLogger(__name__)

# State cache singleton — replaces scattered module-level dicts
_state = get_state_cache()

# Backward-compat aliases — point to state cache internals
_container_locks = _state._locks
_locks_mutex = _state._locks_mutex


def _get_container_lock(ctid: str) -> asyncio.Lock:
    """Return a per-container async lock via the state cache."""
    return _state.get_container_lock(ctid)


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


async def run_command_with_input(
    cmd: Union[str, List[str]], data: str, timeout: int = 30,
) -> bool:
    """
    Run a command where the container config is running, feeding it `data`.

    Mirrors run_command: local when the daemon runs on the node, over SSH when
    use_remote_proxmox is set. The remote branch of apply_cpu_pinning used to
    build its content correctly and then hand it to a local subprocess, so the
    node it was talking to never received the write.

    Args:
        cmd: The command to run.
        data: What to write to its standard input.
        timeout: Seconds to wait.

    Returns:
        True when the command exited zero.
    """
    cfg = get_app_config()
    if cfg.defaults.use_remote_proxmox:
        from ssh import AsyncSSHPool
        global _ssh_pool
        if _ssh_pool is None:
            _ssh_pool = AsyncSSHPool(cfg.defaults.get_ssh_config())
        return await _ssh_pool.run_command_with_input(cmd, data, timeout)
    return await run_local_command_with_input(cmd, data, timeout)


async def run_local_command_with_input(
    cmd: Union[str, List[str]], data: str, timeout: int = 30,
) -> bool:
    """Run a local command, feeding it `data` on stdin."""
    if isinstance(cmd, str):
        import shlex
        cmd = shlex.split(cmd)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(input=data.encode()), timeout=timeout)
        if proc.returncode == 0:
            return True
        logger.error("Command failed (rc=%d): %s — %s",
                     proc.returncode, cmd, stderr.decode('utf-8').strip())
    except asyncio.TimeoutError:
        logger.error("Command timed out after %ds: %s", timeout, cmd)
        proc.kill()
        await proc.wait()
    except OSError as e:
        logger.error("OS error executing %s: %s", cmd, e)
    return False


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

# Backward-compat alias — backed by state cache
_last_backup_settings = _state.last_backup


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

# `\Z`, not `$`: `$` also matches before a trailing newline, so "0-3\n"
# satisfies this. Nothing reaches it with one today only because
# resolve_cpu_pinning happens to call .strip() first.
_CPU_RANGE_RE = re.compile(r'^[0-9]+([-,][0-9]+)*\Z')
_cached_topology: Optional[Dict[str, List[int]]] = None

# One round trip, because on a remote Proxmox host each of these is an SSH call.
# The L3 domains are found by matching cache level 3 rather than assuming index3,
# and the trailing `exit 0` matters: a glob that matches nothing makes the loop
# exit non-zero, which run_command would report as a failure on every host that
# has no hybrid cores.
#
# P and E cores come from the perf PMU interface. The previous source,
# /sys/devices/system/cpu/cpu*/topology/core_type, does not exist: the only file
# that creates cpuN/topology/ is drivers/base/topology.c, it installs one
# attribute group wholesale, and core_type is in neither of its two arrays. It
# is absent at every tag checked from v5.18 to v6.17 and appears in none of the
# three ABI documents. Reading it never selected a core anywhere, on any vendor,
# which is why `p-cores` pinned to every CPU and `e-cores` pinned to nothing.
#
# What the kernel does create, on hybrid parts only, is one PMU per core type:
# arch/x86/events/intel/core.c names them "cpu_core" and "cpu_atom" and gives
# each a `cpus` attribute (intel_hybrid_get_attr_cpus, DEVICE_ATTR(cpus, ...)),
# so the members are readable at /sys/devices/cpu_core/cpus and
# /sys/devices/cpu_atom/cpus. Their presence is itself the hybrid signal: a
# uniform CPU has a single PMU at /sys/devices/cpu. This is also the interface
# the perf tool uses. It needs CONFIG_PERF_EVENTS, which Proxmox kernels set.
_TOPOLOGY_PROBE = (
    'printf "online:%s\\n" "$(cat /sys/devices/system/cpu/online 2>/dev/null)"; '
    'printf "nproc:%s\\n" "$(nproc)"; '
    'printf "pmu:core:%s\\n" "$(cat /sys/devices/cpu_core/cpus 2>/dev/null)"; '
    'printf "pmu:atom:%s\\n" "$(cat /sys/devices/cpu_atom/cpus 2>/dev/null)"; '
    'for lf in $(grep -l "^3$" '
    '/sys/devices/system/cpu/cpu[0-9]*/cache/index[0-9]*/level 2>/dev/null); do '
    'd=$(dirname "$lf"); printf "l3:%s:%s\\n" '
    '"$(cat "$d/shared_cpu_list")" "$(cat "$d/size")"; done; '
    'for f in /sys/devices/system/node/node[0-9]*/cpulist; do '
    '[ -f "$f" ] || continue; printf "numa:%s:%s\\n" '
    '"$(basename "$(dirname "$f")")" "$(cat "$f")"; done; '
    'exit 0'
)


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


def _range_to_cpus(cpu_range: str) -> List[int]:
    """Parse a sysfs cpulist such as "0-7,16-23" into [0..7, 16..23]."""
    cpus: List[int] = []
    for part in cpu_range.strip().split(','):
        if not part:
            continue
        try:
            if '-' in part:
                lo, hi = part.split('-', 1)
                cpus.extend(range(int(lo), int(hi) + 1))
            else:
                cpus.append(int(part))
        except ValueError:
            logger.debug("Unparseable cpulist fragment %r in %r", part, cpu_range)
            return []
    return cpus


async def detect_cpu_topology() -> Dict[str, List[int]]:
    """Named CPU groups usable as `cpu_pinning` keywords, e.g. {"l3:0": [0, 1, ...]}.

    `p-cores`/`e-cores` appear only where the kernel registers a PMU per core
    type, which is hybrid Intel parts with CONFIG_PERF_EVENTS. `l3:N` (a CCD/CCX
    on AMD) and `numa:N` are derived from generic sysfs and work on any vendor.

    A group is offered only when the host actually has it. Asking for one that
    is absent is refused and named, rather than quietly resolving to every CPU.
    """
    global _cached_topology
    if _cached_topology is not None:
        return _cached_topology

    output = await run_command(["sh", "-c", _TOPOLOGY_PROBE])
    if not output:
        # Deliberately not cached. Under use_remote_proxmox the probe is an SSH
        # call, and caching one timeout would disable pinning for the whole run.
        logger.error("CPU topology probe returned nothing; retrying next cycle")
        return {}

    num_cpus = 0
    online: List[int] = []
    p_cores: List[int] = []
    e_cores: List[int] = []
    l3_sizes: Dict[str, str] = {}
    numa_nodes: Dict[str, str] = {}

    for line in output.strip().splitlines():
        kind, _, rest = line.partition(':')
        if kind == 'online':
            online = _range_to_cpus(rest)
        elif kind == 'nproc':
            num_cpus = int(rest) if rest.isdigit() else 0
        elif kind == 'pmu':
            which, _, cpulist = rest.partition(':')
            target = p_cores if which == 'core' else e_cores
            target.extend(_range_to_cpus(cpulist))
        elif kind == 'l3':
            cpulist, _, size = rest.rpartition(':')
            if _range_to_cpus(cpulist):
                l3_sizes.setdefault(cpulist, size)
        elif kind == 'numa':
            node_name, _, cpulist = rest.partition(':')
            # A CPU-less NUMA node (CXL, persistent memory) is not pinnable.
            if _range_to_cpus(cpulist):
                numa_nodes[node_name.removeprefix('node')] = cpulist

    # nproc reports the daemon's own affinity mask, so it undercounts (and
    # misnumbers) whenever the unit sets CPUAffinity= or runs in a cpuset.
    if not online:
        online = list(range(num_cpus))
    groups: Dict[str, List[int]] = {}
    if online:
        groups['all'] = online
    if p_cores and e_cores:
        groups['p-cores'] = sorted(p_cores)
        groups['e-cores'] = sorted(e_cores)

    l3_ordered = sorted(l3_sizes, key=lambda cpulist: _range_to_cpus(cpulist)[0])
    for index, cpulist in enumerate(l3_ordered):
        groups[f'l3:{index}'] = _range_to_cpus(cpulist)
    for node_id, cpulist in numa_nodes.items():
        groups[f'numa:{node_id}'] = _range_to_cpus(cpulist)

    logger.info(
        "CPU topology: %d CPUs online, hybrid P/E cores: %s; L3 domains: %s; NUMA: %s",
        len(online),
        _cpus_to_range(groups['p-cores']) + " / " + _cpus_to_range(groups['e-cores'])
        if 'p-cores' in groups else "none",
        ", ".join(f"l3:{i}={cpulist} ({l3_sizes[cpulist]})"
                  for i, cpulist in enumerate(l3_ordered)) or "unknown",
        ", ".join(f"numa:{n}={c}" for n, c in numa_nodes.items()) or "unknown",
    )
    # Only a result worth reusing is cached. The `not output` path above is
    # careful not to cache a failed probe, but output that arrives and parses to
    # nothing reaches here: an SSH banner or a motd on stdout under
    # use_remote_proxmox is enough. Caching {} makes `is not None` true forever
    # and disables every pinning keyword for the life of the daemon, which is
    # the failure that path exists to prevent.
    if groups:
        _cached_topology = groups
    else:
        logger.error("CPU topology probe produced no usable groups from: %r",
                     output[:200])
    return groups


def _validated_cpu_range(cpu_range: str, online: List[int]) -> Optional[str]:
    """
    Checks an explicit `cpu_pinning` range and returns it in canonical form.

    The regular expression above is a syntax check and nothing more, so on a
    32-CPU host every one of these used to be written verbatim into
    /etc/pve/lxc/<ctid>.conf:

        "31-0"     a reversed range
        "0-999"    past the end of the host
        "99"       a CPU that does not exist
        "0,0,0,0"  the same CPU four times

    The kernel refuses a malformed or out-of-range cpuset, so LXC cannot set up
    the cgroup and the container does not start. A typo in a tier's config
    stopping a container is worse than that tier not being pinned (#78).

    Membership is checked only when the online set is known. If the topology
    probe failed there is nothing authoritative to check against, and refusing
    every explicit range because one SSH call timed out would trade a rare
    misconfiguration for a common outage. The structural checks still run: a
    reversed range is wrong on any host.

    Args:
        cpu_range: The value as written in the configuration, already stripped
            and lowercased.
        online: The online CPUs, or an empty list when they are not known.

    Returns:
        The canonical range, or None when it cannot be pinned.
    """
    cpus: List[int] = []
    for part in cpu_range.split(','):
        if '-' in part:
            low, _, high = part.partition('-')
            start, end = int(low), int(high)
            if start > end:
                logger.error(
                    "cpu_pinning: %r has a reversed range (%s). The kernel "
                    "refuses a cpuset like that and the container will not "
                    "start, so nothing is pinned.", cpu_range, part,
                )
                return None
            cpus.extend(range(start, end + 1))
        else:
            cpus.append(int(part))

    unique = sorted(set(cpus))
    if online:
        missing = [cpu for cpu in unique if cpu not in online]
        if missing:
            logger.error(
                "cpu_pinning: %r names CPU%s %s, which this host does not have "
                "online (it has %s). The kernel refuses a cpuset naming a CPU "
                "that is not there and the container will not start, so nothing "
                "is pinned.",
                cpu_range, "" if len(missing) == 1 else "s",
                _cpus_to_range(missing), _cpus_to_range(online),
            )
            return None

    canonical = _cpus_to_range(unique)
    if canonical != cpu_range:
        logger.info("cpu_pinning: %r pins the same CPUs as %r; writing the "
                    "latter.", cpu_range, canonical)
    return canonical


async def resolve_cpu_pinning(pinning_config: str) -> Optional[str]:
    val = pinning_config.strip().lower()
    groups = await detect_cpu_topology()
    if val in groups:
        return _cpus_to_range(groups[val])
    if val in ('p-cores', 'e-cores'):
        logger.warning(
            "cpu_pinning: %s needs a CPU whose cores are of more than one type, and "
            "this host does not report any (/sys/devices/cpu_core and "
            "/sys/devices/cpu_atom are absent on a uniform CPU). Not pinning; any "
            "cpuset already in the container config is left as it is, and pct set "
            "-cpuset '' clears it. Use one of %s, or an explicit range.",
            val, ", ".join(groups) or "none",
        )
        return None
    if _CPU_RANGE_RE.match(val):
        return _validated_cpu_range(val, groups.get('all', []))
    logger.error(
        "Invalid cpu_pinning value: %r. Known groups on this host: %s. "
        "An explicit range such as 0-7 or 0,2,4-6 also works.",
        pinning_config, ", ".join(groups) or "none",
    )
    return None


# ---------------------------------------------------------------------------
# #8: CPU pinning with state cache — only apply on change
# ---------------------------------------------------------------------------

_applied_pinning = _state.applied_pinning


_CPUSET_KEY = "lxc.cgroup2.cpuset.cpus:"

# A pct container config holds the live configuration first, then one
# `[snapshotname]` section per snapshot, each a full copy of the config at the
# time it was taken (pct(1), "Snapshots"). Only the part before the first
# section header applies to the running container.
_SECTION_HEADER_RE = re.compile(r"^\[")


def _split_live_section(content: str) -> Tuple[List[str], List[str]]:
    """
    Splits a container config into its live lines and everything after them.

    Args:
        content: The whole config file.

    Returns:
        (live_lines, rest_lines), where rest_lines starts at the first
        `[snapshot]` header and is returned untouched.
    """
    lines = content.splitlines(True)
    for index, line in enumerate(lines):
        if _SECTION_HEADER_RE.match(line):
            return lines[:index], lines[index:]
    return lines, []


def _set_cpuset_line(content: str, cpu_range: str) -> Tuple[str, bool]:
    """
    Sets the cpuset key in the live section of a container config.

    Writing to the file as if it were flat put the pin inside the last snapshot
    section, where it has no effect on the running container, and a cpuset line
    found in a snapshot was taken as proof the live section already had one.

    Args:
        content: The whole config file.
        cpu_range: The value for `lxc.cgroup2.cpuset.cpus`.

    Returns:
        (new_content, changed). `changed` is False when the live section
        already carries exactly this pin, so the caller can skip the write.
    """
    target = f"{_CPUSET_KEY} {cpu_range}"
    live, rest = _split_live_section(content)

    for index, line in enumerate(live):
        stripped = line.strip()
        if stripped == target:
            return content, False
        if stripped.startswith(_CPUSET_KEY):
            live[index] = target + "\n"
            return "".join(live) + "".join(rest), True

    # Append at the end of the live section, not at the end of the file.
    if live and not live[-1].endswith("\n"):
        live[-1] += "\n"
    live.append(target + "\n")
    return "".join(live) + "".join(rest), True


def _container_conf_path(ctid: str) -> str:
    """The documented path of a container config, before symlink resolution."""
    return f"/etc/pve/lxc/{ctid}.conf"


def _is_expected_conf_path(real_path: str, ctid: str) -> bool:
    """
    Checks that a resolved config path is one pmxcfs is expected to produce.

    `/etc/pve/lxc` is documented as a symbolic link to
    `nodes/<LOCAL_HOST_NAME>/lxc/` (pmxcfs, "Symbolic links"), so on every node
    the realpath of a container config is under `/etc/pve/nodes/<node>/lxc/`.
    Requiring the resolved path to still start with `/etc/pve/lxc/` therefore
    rejected the only path that exists, and every local write was refused as a
    symlink attack.

    Args:
        real_path: The path after `os.path.realpath`.
        ctid: The container ID the path is supposed to belong to.

    Returns:
        True when the path is `/etc/pve/lxc/<ctid>.conf` or
        `/etc/pve/nodes/<node>/lxc/<ctid>.conf`.
    """
    expected_name = f"{ctid}.conf"
    if os.path.basename(real_path) != expected_name:
        return False
    parent = os.path.dirname(real_path)
    if parent == "/etc/pve/lxc":
        return True
    prefix, _, node_dir = parent.rpartition("/lxc")
    if node_dir or not prefix.startswith("/etc/pve/nodes/"):
        return False
    # /etc/pve/nodes/<node>/lxc — exactly one path element for the node name.
    node = prefix[len("/etc/pve/nodes/"):]
    return bool(node) and "/" not in node


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

    conf_path = _container_conf_path(ctid)

    cfg = get_app_config()
    if cfg.defaults.use_remote_proxmox:
        # Remote: read the file, rewrite it in Python, write it back through
        # tee's stdin. Never pass user-controlled data through sed or sh -c.
        current = await run_command(["cat", conf_path])
        if current is None:
            logger.error("Cannot read config file %s", conf_path)
            return False

        # run_command strips its output, so the trailing newline of the file is
        # gone by the time it arrives here. Appending to it without restoring
        # one produced `swap: 512lxc.cgroup2.cpuset.cpus: 0-3`, corrupting the
        # last key of the live section.
        if current and not current.endswith("\n"):
            current += "\n"

        new_content, changed = _set_cpuset_line(current, cpu_range)
        if not changed:
            _applied_pinning[ctid] = cpu_range
            return True

        # The write has to happen on the node that holds the container. The
        # previous version built the content correctly and then handed it to a
        # local `tee`, so the remote config was never touched, and on a daemon
        # host that happens to have /etc/pve/lxc the remote container's config
        # was written into the local node's directory.
        if not await run_command_with_input(["tee", conf_path], new_content):
            logger.error("Failed to set CPU pinning for container %s", ctid)
            return False
    else:
        # Local: native Python file I/O — no shell, no injection risk
        try:
            real_conf = os.path.realpath(conf_path)
            if not _is_expected_conf_path(real_conf, ctid):
                logger.error("Unexpected config path for container %s: %s -> %s",
                             ctid, conf_path, real_conf)
                return False
            with open(real_conf, 'r', encoding='utf-8') as f:
                current = f.read()

            new_content, changed = _set_cpuset_line(current, cpu_range)
            if not changed:
                _applied_pinning[ctid] = cpu_range
                return True

            with open(real_conf, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except OSError as e:
            logger.error("Failed to set CPU pinning for container %s: %s", ctid, e)
            return False

    _applied_pinning[ctid] = cpu_range
    logger.info("Container %s: CPU pinning set to %s", ctid, cpu_range)
    return True


# ---------------------------------------------------------------------------
# #2 + #3: CPU measurement — zero-sleep, core count passed from collector
# ---------------------------------------------------------------------------

_cgroup_path_cache = _state.cgroup_cpu_paths
_prev_cpu_readings = _state.prev_cpu_readings
_cgroup_negative_cache = _state.cpu_negative
_NEGATIVE_CACHE_TTL = _state.NEGATIVE_CACHE_TTL

_core_count_cache = _state.core_counts


def evict_stale_caches(active_ctids: set) -> None:
    """Remove cache entries for containers no longer in the active set.

    Delegates to ContainerStateCache.evict_stale() which handles all
    per-container caches and locks in one pass.
    """
    _state.evict_stale(active_ctids)


def set_cached_core_count(ctid: str, cores: int) -> None:
    """Store core count from the collector so CPU calc doesn't re-query."""
    _state.set_core_count(ctid, cores)


async def _get_num_cpus(ctid: str) -> int:
    """Get core count — use cache first, fall back to pct config. Never returns 0."""
    cached = _core_count_cache.get(ctid)
    if cached:
        return cached
    validate_container_id(ctid)
    config_output = await run_command(["pct", "config", ctid])
    if config_output:
        for line in config_output.splitlines():
            if line.startswith("cores:"):
                cores = max(1, int(line.split()[1]))
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

async def pvesh_stat_method(ctid: str) -> float:
    """Calculate CPU usage using pvesh cluster resources (non‑blocking)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pvesh", "get", "/cluster/resources", "--output-format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"pvesh failed: {stderr.decode()}")

        data = json.loads(stdout)
        full_id = f"lxc/{ctid}"
        target = next((item for item in data if item.get('id') == full_id), None)

        if target and 'cpu' in target:
            return round(float(target['cpu']) * 100, 2)
        return 0.0

    except Exception as e:
        raise RuntimeError(f"pvesh resource method failed: {e}") from e

async def get_cpu_usage(ctid: str) -> float:
    """Get CPU usage. Returns 0.0 on first cycle (no delta yet)."""
    validate_container_id(ctid)
    methods = [
        ("pvesh", pvesh_stat_method),
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

_cgroup_mem_path_cache = _state.cgroup_mem_paths
_cgroup_mem_negative_cache = _state.mem_negative

# Keys in memory.stat, per cgroup version: the file-backed total, and the part
# of it that is shared memory. Only their difference is genuinely reclaimable.
# "file" and "total_cache" both include tmpfs, /dev/shm and shm segments, and
# those pages are swap-backed: with no swap the kernel cannot free them at all.
# Discounting them reports an almost-full container as empty, and the daemon
# then shrinks it until the OOM killer intervenes.
_V2_CACHE_KEY = "file"
_V2_SHMEM_KEY = "shmem"
_V1_CACHE_KEY = "total_cache"
_V1_SHMEM_KEY = "total_shmem"


def _exclude_page_cache() -> bool:
    """Whether reclaimable page cache counts as used memory (see issue #51)."""
    return bool(get_config_value('DEFAULT', 'memory_exclude_cache', True))


async def _read_cgroup_memory(ctid: str) -> Optional[Tuple[int, int]]:
    """Read memory usage from host-side cgroup. Returns (used_bytes, total_bytes).

    Page cache is subtracted from the raw counter by default so the reported
    usage matches the Proxmox UI: cgroup's memory.current / usage_in_bytes
    counts reclaimable file cache, which would otherwise pin containers near
    100% forever and block downscaling.
    """
    validate_container_id(ctid)
    neg = _cgroup_mem_negative_cache.get(ctid, 0)
    if neg > 0:
        _cgroup_mem_negative_cache[ctid] = neg - 1
        return None

    cached = _cgroup_mem_path_cache.get(ctid)
    if cached:
        usage_p, limit_p, stat_p, cache_key = cached
        used = await _read_mem_file(usage_p)
        limit = await _read_mem_limit(limit_p)
        if used is not None and limit is not None:
            shmem_key = (_V1_SHMEM_KEY if cache_key == _V1_CACHE_KEY
                         else _V2_SHMEM_KEY)
            return await _apply_cache_exclusion(
                used, stat_p, cache_key, shmem_key), limit
        del _cgroup_mem_path_cache[ctid]

    # cgroup v2 candidates
    v2_bases = [
        f"/sys/fs/cgroup/lxc.payload.{ctid}",
        f"/sys/fs/cgroup/lxc/{ctid}",
    ]
    for base in v2_bases:
        current_p = f"{base}/memory.current"
        max_p = f"{base}/memory.max"
        stat_p = f"{base}/memory.stat"
        used = await _read_mem_file(current_p)
        limit = await _read_mem_file(max_p)
        if used is not None and limit is not None and limit > 0:
            _cgroup_mem_path_cache[ctid] = (current_p, max_p, stat_p, _V2_CACHE_KEY)
            return await _apply_cache_exclusion(
                used, stat_p, _V2_CACHE_KEY, _V2_SHMEM_KEY), limit

    # cgroup v1 fallback
    v1_base = f"/sys/fs/cgroup/memory/lxc/{ctid}"
    v1_usage = f"{v1_base}/memory.usage_in_bytes"
    v1_limit = f"{v1_base}/memory.limit_in_bytes"
    v1_stat = f"{v1_base}/memory.stat"
    used = await _read_mem_file(v1_usage)
    limit = await _read_mem_file(v1_limit)
    if used is not None and limit is not None and limit > 0:
        _cgroup_mem_path_cache[ctid] = (v1_usage, v1_limit, v1_stat, _V1_CACHE_KEY)
        return await _apply_cache_exclusion(
            used, v1_stat, _V1_CACHE_KEY, _V1_SHMEM_KEY), limit

    _cgroup_mem_negative_cache[ctid] = _NEGATIVE_CACHE_TTL
    return None


async def _apply_cache_exclusion(used: int, stat_path: str, cache_key: str,
                                 shmem_key: str) -> int:
    """Subtract reclaimable page cache from a raw cgroup memory counter.

    Shared memory is deliberately NOT subtracted. It is reported inside the
    file-backed total but it is swap-backed, so on a container with no swap it
    cannot be reclaimed by any means short of the OOM killer. Proxmox's own
    interface subtracts the file total whole, so a shmem-heavy container is
    reported here as fuller than the Proxmox UI shows it. That difference is
    intended: the UI is describing the machine, this number decides whether to
    take memory away from it.
    """
    if not _exclude_page_cache():
        return used
    stats = await _read_mem_stat(stat_path)
    cache = stats.get(cache_key)
    if cache is None:
        # memory.stat unreadable: keep the raw counter rather than guessing.
        return used
    # An older kernel without the shmem key falls back to subtracting nothing
    # for it, which errs toward reporting more memory in use, not less.
    reclaimable = cache - stats.get(shmem_key, 0)
    return max(used - max(reclaimable, 0), 0)


async def _read_mem_stat(path: str) -> Dict[str, int]:
    """Parse a cgroup memory.stat file into a {key: bytes} mapping."""
    output = await run_command(["cat", path])
    if not output:
        return {}
    stats: Dict[str, int] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            stats[parts[0]] = int(parts[1])
        except ValueError:
            continue
    return stats


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
            mem_free = None
            for line in meminfo_output.splitlines():
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_available = int(line.split()[1])
                elif line.startswith("MemFree:"):
                    mem_free = int(line.split()[1])
            # MemAvailable already excludes reclaimable cache; MemFree does not.
            unused = mem_available if _exclude_page_cache() else mem_free
            if total and unused is not None:
                pct = ((total - unused) * 100) / total
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


# Matches the address in a net0 line: "name=eth0,bridge=vmbr0,ip=10.0.0.5/24".
# "ip=dhcp" and "ip=manual" do not match, which is what we want.
_NET_IPV4_RE = re.compile(r'\bip=(\d{1,3}(?:\.\d{1,3}){3})(?:/\d{1,2})?')


async def get_container_ipv4(ctid: str) -> Optional[str]:
    """Return the static IPv4 configured on net0, without prefix.

    Returns None when the container uses DHCP, has no net0, or cannot be read.
    """
    validate_container_id(ctid)
    output = await run_command(["pct", "config", ctid])
    if not output:
        return None
    for line in output.splitlines():
        if line.startswith("net0:"):
            match = _NET_IPV4_RE.search(line)
            if match:
                return match.group(1)
    return None


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
