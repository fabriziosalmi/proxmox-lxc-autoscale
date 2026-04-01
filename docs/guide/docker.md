# Docker

LXC AutoScale can run inside a Docker container, connecting to a Proxmox host remotely via SSH or the REST API.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/fabriziosalmi/proxmox-lxc-autoscale.git
cd proxmox-lxc-autoscale/lxc_autoscale
```

### 2. Configure environment variables (optional)

```bash
cp .env.example .env
nano .env
```

::: warning
Never commit `.env` files containing passwords or sensitive information to version control.
:::

### 3. Build the Docker image

```bash
docker build -t lxc-autoscale .
```

### 4. Configure the backend

#### Option A: SSH backend (default)

Edit `lxc_autoscale.yaml` with the remote Proxmox host parameters:

```yaml
DEFAULT:
  use_remote_proxmox: true
  ssh_user: "root"
  ssh_key_path: "/root/.ssh/id_rsa"
  proxmox_host: "192.168.1.100"
  ssh_port: 22
  ssh_host_key_policy: reject
```

::: tip
Use SSH keys instead of passwords. Set `ssh_key_path` and leave `ssh_password` empty.
:::

The container requires a `known_hosts` file for host key verification. Mount one into the container or let the entrypoint generate it on first boot via `ssh-keyscan`:

```bash
docker run -d --name lxc_autoscale \
  -v /path/to/known_hosts:/root/.ssh/known_hosts:ro \
  -v /path/to/config.yaml:/app/lxc_autoscale.yaml:ro \
  lxc-autoscale
```

#### Option B: REST API backend

```yaml
DEFAULT:
  backend: api
  proxmox_api:
    host: 192.168.1.100
    user: autoscale@pve
    token_name: scaling
    token_value: ${PROXMOX_API_TOKEN}
    verify_ssl: true
```

```bash
docker run -d --name lxc_autoscale \
  -e PROXMOX_API_TOKEN=your-token-value \
  -e LXC_RUN_AS_ROOT=false \
  -v /path/to/config.yaml:/app/lxc_autoscale.yaml:ro \
  lxc-autoscale
```

### 5. Run the container

Using the default config:

```bash
docker run -d --name lxc_autoscale lxc-autoscale
```

Using a custom config file:

```bash
docker run -d --name lxc_autoscale \
  -v /path/to/your/lxc_autoscale.yaml:/app/lxc_autoscale.yaml \
  lxc-autoscale
```

### 6. Check logs

```bash
docker logs lxc_autoscale
```

## Non-root execution

When using the REST API backend, the container does not need root privileges. Set `LXC_RUN_AS_ROOT=false` to run the daemon as the `autoscale` user:

```bash
docker run -d \
  -e LXC_RUN_AS_ROOT=false \
  -v /path/to/config.yaml:/app/lxc_autoscale.yaml:ro \
  lxc-autoscale
```

This reduces the attack surface in case of container escape. The CLI backend requires root for `pct` commands and cannot run in non-root mode.

## Environment variables

| Variable | Description |
|----------|-------------|
| `USER_CONF_PATH` | Path to a custom YAML config file inside the container. |
| `SSH_USER` | SSH username (overrides YAML). |
| `SSH_PASS` | SSH password (overrides YAML). |
| `PROXMOX_HOST` | Proxmox host IP/hostname (overrides YAML). |
| `SSH_KEY_PATH` | Path to SSH key inside the container (overrides YAML). |
| `KNOWN_HOSTS_PATH` | Path to the SSH known_hosts file. Default: `/root/.ssh/known_hosts`. |
| `LXC_RUN_AS_ROOT` | Set to `false` to run as non-root user. Default: `true`. |
| `PROXMOX_API_TOKEN` | API token value for REST API backend. |
| `LXC_AUTOSCALE_SSH_PASSWORD` | SSH password (direct env override). |
| `LXC_AUTOSCALE_SMTP_PASSWORD` | SMTP password for email notifications. |
| `LXC_AUTOSCALE_GOTIFY_TOKEN` | Gotify API token. |
| `LXC_AUTOSCALE_UPTIME_KUMA_WEBHOOK` | Uptime Kuma webhook URL. |
