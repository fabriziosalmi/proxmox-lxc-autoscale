# Notifications

LXC AutoScale can send notifications on scaling events to one or more endpoints.

## Supported channels

### Email (SMTP)

```yaml
smtp_server: 'smtp.example.com'
smtp_port: 587
smtp_username: 'your-username'
smtp_password: 'your-password'
smtp_from: 'lxc-autoscale@yourdomain.com'
smtp_to:
  - 'admin@yourdomain.com'
  - 'alerts@yourdomain.com'
```

### Gotify

```yaml
gotify_url: 'http://gotify-host'
gotify_token: 'YOUR_GOTIFY_TOKEN'
```

### Uptime Kuma

```yaml
uptime_kuma_webhook_url: 'http://uptime-kuma-host:3001/api/push/YOUR_PUSH_ID?status=up&msg=OK&ping='
```

## Configuration

Add the notification settings to the `DEFAULT` section of `/etc/lxc_autoscale/lxc_autoscale.yaml`. You can enable one, multiple, or all channels. Unconfigured channels are silently skipped.

::: tip
Secrets can be overridden via environment variables instead of storing them in the YAML file:
- `LXC_AUTOSCALE_SMTP_PASSWORD`
- `LXC_AUTOSCALE_GOTIFY_TOKEN`
- `LXC_AUTOSCALE_UPTIME_KUMA_WEBHOOK`
:::
