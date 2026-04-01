# Notifications

LXC AutoScale can send notifications on scaling events to one or more endpoints. Notifications are dispatched asynchronously and never block the scaling loop.

## Supported channels

### Email (SMTP)

```yaml
smtp_server: 'smtp.example.com'
smtp_port: 587
smtp_username: 'your-username'
smtp_password: '${LXC_AUTOSCALE_SMTP_PASSWORD}'
smtp_from: 'lxc-autoscale@yourdomain.com'
smtp_to:
  - 'admin@yourdomain.com'
  - 'alerts@yourdomain.com'
```

The daemon connects via STARTTLS. Authentication is required.

### Gotify

```yaml
gotify_url: 'http://gotify-host'
gotify_token: '${LXC_AUTOSCALE_GOTIFY_TOKEN}'
```

### Uptime Kuma

```yaml
uptime_kuma_webhook_url: 'http://uptime-kuma-host:3001/api/push/YOUR_PUSH_ID?status=up&msg=OK&ping='
```

## Configuration

Add the notification settings to the `DEFAULT` section of `/etc/lxc_autoscale/lxc_autoscale.yaml`. You can enable one, multiple, or all channels. Unconfigured channels are silently skipped.

Secrets can be injected via environment variables using `${VAR}` syntax in the YAML file, or via direct env overrides:

| Environment variable | Overrides |
|---------------------|-----------|
| `LXC_AUTOSCALE_SMTP_PASSWORD` | `smtp_password` |
| `LXC_AUTOSCALE_GOTIFY_TOKEN` | `gotify_token` |
| `LXC_AUTOSCALE_UPTIME_KUMA_WEBHOOK` | `uptime_kuma_webhook_url` |

## Async dispatch

All notifications are sent in a background thread using `asyncio.to_thread`. This means:

- The scaling loop is never blocked by slow SMTP servers or HTTP endpoints.
- If a notification takes 5 seconds to deliver, the daemon continues scaling other containers without waiting.
- HTTP notifiers (Gotify, Uptime Kuma) reuse a shared `requests.Session` with connection pooling for efficient keep-alive.

## Failure backoff

If a notification channel fails repeatedly, the daemon suppresses it to avoid wasting time on a broken endpoint.

| Parameter | Value | Behavior |
|-----------|-------|----------|
| Failure threshold | 3 | After 3 consecutive failures, the channel is suppressed. |
| Backoff period | 10 cycles | The channel is skipped for 10 notification attempts. |
| Retry | Automatic | After the backoff period, the channel is retried. If it succeeds, the failure counter resets to zero. |

A warning is logged when a channel enters backoff:

```
GotifyNotification: 3 consecutive failures, backing off
```

This prevents a single broken SMTP server or unreachable Gotify instance from stalling or spamming the daemon logs.
