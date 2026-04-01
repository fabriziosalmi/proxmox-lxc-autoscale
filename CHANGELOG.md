# Changelog

## [2.0.0] - 2026-04-01

### Architecture
- **Async migration**: entire daemon now runs on `asyncio` event loop. `subprocess.check_output` replaced with `asyncio.create_subprocess_exec`, `time.sleep` replaced with `asyncio.sleep`, `ThreadPoolExecutor` replaced with `asyncio.gather`
- **Pydantic configuration**: all config validated via Pydantic v2 models (`DefaultsConfig`, `TierConfig`, `SSHConfig`, `ProxmoxAPIConfig`) with type safety and threshold validation. Fully backward-compatible with existing YAML files
- **Backend abstraction**: new `ProxmoxBackend` ABC with two implementations:
  - `CLIBackend` (default) — wraps `pct` commands, local or remote via SSH
  - `RESTBackend` — uses Proxmox REST API via `proxmoxer` (optional dependency)
- **SSH connection pool**: `AsyncSSHPool` replaces the global `ssh_client` singleton. Thread-safe, auto-recovers stale connections, supports concurrent operations

### Security
- **SSH MITM fix**: `paramiko.AutoAddPolicy()` removed from default code path. SSH now defaults to `RejectPolicy`. Users must explicitly opt-in to `auto` (deprecated with loud warning)
- **entrypoint.sh hardened**: `StrictHostKeyChecking=no` removed. Requires `known_hosts` file (auto-generated via `ssh-keyscan` on first boot). Password passed via `SSHPASS` env var instead of `-p` on command line
- **Command injection eliminated**: CPU pinning uses native Python file I/O for local operations instead of `sh -c` with f-string interpolation
- **Secret masking in logs**: `SecretMaskingFilter` on root logger redacts passwords, tokens, Bearer headers, and long hex/base64 strings from all log output
- **`${ENV_VAR}` expansion in YAML**: config values support `${VAR}` and `${VAR:-default}` syntax for secrets injection without storing plaintext
- **SSH auto policy deprecated**: loud `SECURITY WARNING` logged when `ssh_host_key_policy: auto` is configured
- **Non-root Docker user**: `autoscale` user created in Dockerfile. Set `LXC_RUN_AS_ROOT=false` for API-only deployments

### Performance
- **Zero-sleep CPU measurement**: first poll cycle stores raw cgroup sample without blocking. Delta computed on second cycle — eliminates 2s `sleep` per container
- **Cgroup memory reading**: memory usage read from host-side cgroup (`memory.current`/`memory.max`) like CPU, avoiding slow `pct exec` into containers
- **Core count cache**: core counts from `pct config` cached in-memory, not re-queried for CPU percentage calculation
- **Backup dedup**: `backup_container_settings` skips file writes when settings are unchanged since last write
- **CPU pinning cache**: pinning state tracked in-memory, `cat`/`sed` on config file only executed on actual change
- **Fire-and-forget notifications**: `send_notification_async` dispatches HTTP/SMTP in background thread via `asyncio.to_thread`, never blocking the scaling loop
- **Shared HTTP session**: `requests.Session` with connection pooling reused across Gotify and Uptime Kuma notifiers
- **Notification backoff**: consecutive failures suppress a notifier after 3 failures, retry after 10 cycles
- **JSON log rotation**: 10MB size limit with 3 backup files, persistent line-buffered file handle
- **Buffered JSON log**: single persistent file handle instead of `open()`/`close()` per event

### Error Handling
- All 16 bare `except Exception` blocks replaced with specific exception types (`OSError`, `ValueError`, `subprocess.CalledProcessError`, `smtplib.SMTPException`, `requests.RequestException`)

### Testing
- **187 tests** (was 6), all passing
- **57% coverage** overall, core modules 70-98%
- New test files: `test_config.py`, `test_scaling.py`, `test_backends.py`, `test_hardening.py`, `test_lxc_utils.py`, `test_notification.py`, `test_logging_setup.py`, `test_scaling_manager.py`, `test_resource_manager.py`

### Dependencies
- Added: `pydantic>=2.0` (required)
- Optional: `proxmoxer>=2.0` (for REST API backend)

### Breaking Changes
- Python 3.9+ required (was implicit, now enforced via `zoneinfo` import)
- SSH default policy changed from `auto` (accept all) to `reject` (verify host keys)
- Existing Docker deployments using `StrictHostKeyChecking=no` must provide a `known_hosts` file

## [1.2.0] - Previous release

- Host-side cgroup CPU measurement
- CPU core pinning for Intel hybrid CPUs
- Per-container locking
- Container ID validation (command injection fix)
