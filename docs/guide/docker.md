# Docker

LXC AutoScale can run inside a Docker container, connecting to a Proxmox host remotely via SSH.

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

### 4. Configure SSH connection

Edit `lxc_autoscale.yaml` with the remote Proxmox host parameters:

```yaml
use_remote_proxmox: true
ssh_user: "root"
ssh_key_path: "/root/.ssh/id_rsa"
proxmox_host: "192.168.1.100"
ssh_port: 22
```

::: tip
Use SSH keys instead of passwords for better security. Set `ssh_key_path` and leave `ssh_password` empty.
:::

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
