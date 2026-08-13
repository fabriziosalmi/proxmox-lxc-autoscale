# Changelog

## [Unreleased]

### Fixed
- **Horizontal scaling handed the same static IP to every clone** ([#70](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/70)): the filter that was meant to skip addresses already in use compared IP strings against the list of integer container ids, so it never excluded anything and every clone received `static_ip_range[0]`. Addresses in use are now read from the live `net0` of each group member. The address is also chosen before the clone rather than after, so an exhausted range skips the scale-out instead of leaving behind a clone that could not be configured. Entries in `static_ip_range` may now carry their own prefix; bare addresses keep the documented `/24` default.

### Security
- **Documentation toolchain**: cleared all 8 open Dependabot alerts in `docs/`. postcss moved to 8.5.26 and vite to 6.4.3 through `overrides`, which also pulls esbuild out of the vulnerable range. All three advisories concern the local dev server, not the static site that is deployed, but there is no reason to keep them. VitePress stays on 1.6.4, the current stable release; forcing vite 8 or esbuild 0.28 breaks the build.

### Changed
- **paramiko range widened** to `>=2.11.0,<6.0`. Version 5.0 removes SHA-1 RSA signatures and SHA-1 key exchange; modern Proxmox hosts are unaffected, and the lower bound is unchanged so anyone talking to a legacy SSH server can still pin `<5.0`. The full test suite passes against paramiko 5.0.0, and every paramiko symbol used in `ssh.py` was verified to still exist.
- **Requirements consolidated**: the daemon dependencies are declared once in `lxc_autoscale/requirements.txt`, which is also what the Docker image installs. The root `requirements.txt` includes it and adds only the web UI extras. This is what was generating two Dependabot pull requests for every dependency.
- **Docker base image** moved from `python:3.12-slim` to `python:3.14-slim`.
- Dependabot uses `versioning-strategy: widen` for pip, so it stops proposing a higher lower bound every week for ranges that are permissive on purpose.

### CI
- New `Docker` workflow builds the image and checks that the daemon imports inside it. The image was never built in CI, so a broken Dockerfile or a base image without wheels for our dependencies would only have surfaced at run time.
- GitHub Actions updated: checkout v7, setup-python v7, setup-node v7, cache v6, configure-pages v6, upload-pages-artifact v5, deploy-pages v5.
- The VitePress workflow keys its npm cache on `package-lock.json` instead of `package.json`.

## [2.0.2] - 2026-08-13

### Fixed
- **Page cache no longer counts as used memory** ([#51](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/51)): raw cgroup counters (`memory.current` / `memory.usage_in_bytes`) include reclaimable file cache, so containers doing any I/O reported near-100% usage and were never scaled down, and were sometimes scaled up right after a manual downscale. Usage now subtracts the page cache (`memory.stat` `file` on cgroup v2, `total_cache` on v1), matching the figure shown in the Proxmox UI. Set `memory_exclude_cache: false` to restore the old accounting.
- **Installer no longer produces a broken installation**: `install.sh` downloaded 9 of the 13 modules of the package. `state.py`, `ssh.py`, `errors.py`, `boost.py` and the whole `backends/` package were missing, so a fresh install failed at startup on `from state import get_state_cache`. All modules are installed now, downloads use `curl --fail` so an HTTP error aborts the install instead of writing an error page into a `.py` file, and the result is checked with `py_compile` before the service is started.
- **Installer dependencies**: `python3-yaml` and `python3-pydantic` were never installed, and Debian 12 ships pydantic 1.x, which the config models reject. Both are installed now, with a pip fallback when the distribution does not provide pydantic 2.
- **Version string**: `__version__` was left at `2.0.0` through the 2.0.1 release.

### Changed
- `install.sh` honours `LXC_AUTOSCALE_REF` to install from a specific tag or branch instead of `main`.

### CI
- Removed the Codeflash workflow and its `pyproject.toml` configuration. It was unused and failed on every pull request touching `lxc_autoscale/`.

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
