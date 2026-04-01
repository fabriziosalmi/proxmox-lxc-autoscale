"""Notification system supporting Email, Gotify, and Uptime Kuma.

Performance optimizations:
- #6: ``send_notification_async`` dispatches HTTP/SMTP in a thread via
  ``asyncio.to_thread``, never blocking the event loop.
- #9: Shared ``requests.Session`` with connection pooling for HTTP notifiers.
"""

import asyncio
import logging
import smtplib
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from typing import Dict

import requests

from config import DEFAULTS

logger = logging.getLogger(__name__)

# #9: Shared HTTP session with connection pooling
_http_session: requests.Session = None


def _get_session() -> requests.Session:
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        # Connection pool for keep-alive reuse
        adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=4)
        _http_session.mount("http://", adapter)
        _http_session.mount("https://", adapter)
    return _http_session


class NotificationProxy(ABC):
    @abstractmethod
    def send_notification(self, title: str, message: str, priority: int = 5):
        pass


class GotifyNotification(NotificationProxy):
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token

    def send_notification(self, title: str, message: str, priority: int = 5):
        payload = {'title': title, 'message': message, 'priority': priority}
        headers = {'X-Gotify-Key': self.token}
        try:
            resp = _get_session().post(f"{self.url}/message", json=payload,
                                       headers=headers, timeout=10)
            resp.raise_for_status()
            logger.info("Gotify notification sent: %s", title)
        except requests.RequestException as e:
            logger.error("Gotify notification failed: %s", e)


class EmailNotification(NotificationProxy):
    def __init__(self, smtp_server: str, port: int, username: str,
                 password: str, from_addr: str, to_addrs: list):
        self.smtp_server = smtp_server
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    def send_notification(self, title: str, message: str, priority: int = 5):
        msg = MIMEText(message)
        msg['Subject'] = title
        msg['From'] = self.from_addr
        msg['To'] = ', '.join(self.to_addrs)
        try:
            with smtplib.SMTP(self.smtp_server, self.port, timeout=10) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            logger.info("Email sent: %s", title)
        except (smtplib.SMTPException, OSError) as e:
            logger.error("Failed to send email: %s", e)


class UptimeKumaNotification(NotificationProxy):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_notification(self, title: str, message: str, priority: int = 5):
        try:
            resp = _get_session().post(self.webhook_url,
                                       json={'title': title, 'message': message,
                                             'priority': priority},
                                       timeout=10)
            resp.raise_for_status()
            logger.info("Uptime Kuma notification sent")
        except requests.RequestException as e:
            logger.error("Failed to send Uptime Kuma notification: %s", e)


_notifiers_cache = None


def _get_notifiers():
    """Initialize notifiers once, cache for reuse."""
    global _notifiers_cache
    if _notifiers_cache is not None:
        return _notifiers_cache
    notifiers = []
    if DEFAULTS.get('smtp_server') and DEFAULTS.get('smtp_username') and DEFAULTS.get('smtp_password'):
        try:
            notifiers.append(EmailNotification(
                smtp_server=DEFAULTS['smtp_server'],
                port=DEFAULTS.get('smtp_port', 587),
                username=DEFAULTS['smtp_username'],
                password=DEFAULTS['smtp_password'],
                from_addr=DEFAULTS['smtp_from'],
                to_addrs=DEFAULTS['smtp_to'],
            ))
        except (KeyError, TypeError) as e:
            logger.error("Failed to initialize Email notifier: %s", e)
    if DEFAULTS.get('gotify_url') and DEFAULTS.get('gotify_token'):
        notifiers.append(GotifyNotification(DEFAULTS['gotify_url'], DEFAULTS['gotify_token']))
    if DEFAULTS.get('uptime_kuma_webhook_url'):
        notifiers.append(UptimeKumaNotification(DEFAULTS['uptime_kuma_webhook_url']))
    _notifiers_cache = notifiers
    return notifiers


# #10: Consecutive failure tracking for backoff
_failure_counts: Dict[str, int] = {}  # notifier class name -> consecutive failures
_BACKOFF_THRESHOLD = 3  # suppress after N consecutive failures
_BACKOFF_RESET = 10  # try again after N suppressions


def send_notification(title, message, priority=5):
    """Send notification with consecutive-failure backoff."""
    notifiers = _get_notifiers()
    for notifier in notifiers:
        name = notifier.__class__.__name__
        fails = _failure_counts.get(name, 0)

        # Backoff: if too many consecutive failures, skip (but retry periodically)
        if fails >= _BACKOFF_THRESHOLD:
            if fails < _BACKOFF_THRESHOLD + _BACKOFF_RESET:
                _failure_counts[name] = fails + 1
                if fails == _BACKOFF_THRESHOLD:
                    logger.warning("%s: %d consecutive failures, backing off", name, fails)
                continue
            else:
                # Reset and retry
                logger.info("%s: retrying after backoff period", name)
                _failure_counts[name] = 0

        try:
            notifier.send_notification(title, message, priority)
            _failure_counts[name] = 0  # success resets counter
        except (OSError, requests.RequestException) as e:
            _failure_counts[name] = _failure_counts.get(name, 0) + 1
            logger.error("Failed to send via %s (failure #%d): %s",
                         name, _failure_counts[name], e)


async def send_notification_async(title, message, priority=5):
    """Send notification in a background thread — never blocks the event loop."""
    await asyncio.to_thread(send_notification, title, message, priority)
