# Security

LXC AutoScale v2.0 includes several security hardening measures that are enabled by default.

## SSH host key verification

By default, the daemon refuses connections to SSH hosts whose keys are not in the system's `known_hosts` file. This prevents Man-in-the-Middle attacks during remote execution.

### Configuration

```yaml
DEFAULT:
  ssh_host_key_policy: reject   # default, recommended
```

| Value | Behavior |
|-------|----------|
| `reject` | Refuse unknown host keys. Requires the Proxmox host key to be present in `~/.ssh/known_hosts`. |
| `system` | Load system known_hosts and warn on unknown keys, but allow the connection. |
| `auto` | Accept any host key. **Deprecated.** Equivalent to `StrictHostKeyChecking=no`. Will be removed in a future version. |

### Adding host keys

On the machine running the daemon:

```bash
ssh-keyscan -H <proxmox_host> >> ~/.ssh/known_hosts
```

In Docker, mount a `known_hosts` file into the container or set the `KNOWN_HOSTS_PATH` environment variable. On first boot, the entrypoint will attempt to run `ssh-keyscan` automatically if no file is found.

## Secret masking in logs

All log output (console and file) is processed by a masking filter that redacts values matching common secret patterns before writing to disk. This prevents accidental exposure of credentials in log files.

### What is masked

- Key-value pairs: `password=...`, `token:...`, `api_key=...`
- Bearer tokens: `Authorization: Bearer ...`
- Command-line passwords: `sshpass -p ...`
- Long hex or base64 strings (32+ characters) that resemble tokens or keys

### How it works

The `SecretMaskingFilter` is attached to the root Python logger at startup. It intercepts all log records and replaces matched patterns with `***REDACTED***` before the message reaches any handler (console, file, or JSON).

No configuration is needed. The filter is always active.

## Environment variable expansion in YAML

Configuration values can reference environment variables using `${VAR}` or `${VAR:-default}` syntax. This avoids storing secrets in plaintext in the YAML file.

```yaml
DEFAULT:
  ssh_password: ${SSH_PASSWORD}
  proxmox_api:
    token_value: ${PROXMOX_TOKEN:-not-configured}
```

If the variable is not set and no default is provided, the literal `${VAR}` string is preserved unchanged.

Additionally, these environment variables override specific config keys directly, regardless of what the YAML file contains:

| Environment variable | Overrides |
|---------------------|-----------|
| `LXC_AUTOSCALE_SSH_PASSWORD` | `ssh_password` |
| `LXC_AUTOSCALE_SMTP_PASSWORD` | `smtp_password` |
| `LXC_AUTOSCALE_GOTIFY_TOKEN` | `gotify_token` |
| `LXC_AUTOSCALE_UPTIME_KUMA_WEBHOOK` | `uptime_kuma_webhook_url` |

## Configuration file permissions

On startup, the daemon checks the permissions of the YAML configuration file. If it is readable by group or other users, a warning is logged:

```
Config file /etc/lxc_autoscale/lxc_autoscale.yaml is readable by group/others (mode 644).
Recommend chmod 0600 to protect secrets.
```

Set restrictive permissions:

```bash
chmod 600 /etc/lxc_autoscale/lxc_autoscale.yaml
```

## Docker non-root execution

When using the REST API backend (no local `pct` commands), the Docker container can run as a non-root user to reduce the attack surface.

Set the `LXC_RUN_AS_ROOT` environment variable to `false`:

```bash
docker run -d \
  -e LXC_RUN_AS_ROOT=false \
  -v /path/to/config.yaml:/app/lxc_autoscale.yaml \
  lxc-autoscale
```

This requires `backend: api` in the configuration. The CLI backend needs root for `pct` commands and will not work in non-root mode.

## Proxmox API token permissions

When using the REST API backend, create a dedicated API token with minimal permissions rather than using root credentials.

In the Proxmox web UI:

1. Go to **Datacenter > Permissions > API Tokens**
2. Create a token for a user with only the permissions needed:
   - `VM.Audit` (read container status and config)
   - `VM.Config.CPU` (modify CPU settings)
   - `VM.Config.Memory` (modify memory settings)

Store the token value in an environment variable and reference it in the YAML:

```yaml
DEFAULT:
  backend: api
  proxmox_api:
    host: 192.168.1.1
    user: autoscale@pve
    token_name: scaling
    token_value: ${PROXMOX_API_TOKEN}
    verify_ssl: true
```

## Configuration validation

All configuration is validated at startup using Pydantic models. Invalid values cause the daemon to exit with a clear error message rather than running with broken settings.

Validated constraints include:

- `cpu_lower_threshold` must be less than `cpu_upper_threshold`
- `memory_lower_threshold` must be less than `memory_upper_threshold`
- `min_cores` must be less than or equal to `max_cores`
- `behaviour` must be one of `normal`, `conservative`, `aggressive`
- `backend` must be one of `cli`, `api`
- `ssh_host_key_policy` must be one of `reject`, `system`, `auto`
