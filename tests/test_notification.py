"""Tests for notification system — HTTP session, notifier init, async dispatch."""

import asyncio
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

import notification


class TestSharedSession:
    """Test that HTTP notifiers use the shared requests.Session."""

    def test_session_created_once(self):
        notification._http_session = None  # reset
        s1 = notification._get_session()
        s2 = notification._get_session()
        assert s1 is s2

    def test_session_has_adapters(self):
        notification._http_session = None
        session = notification._get_session()
        assert session.get_adapter("http://") is not None
        assert session.get_adapter("https://") is not None


class TestNotifierInit:
    """Test notifier initialization from DEFAULTS."""

    def test_no_config_returns_empty(self):
        notification._notifiers_cache = None
        with patch.dict(notification.DEFAULTS, {}, clear=True):
            notifiers = notification._get_notifiers()
            assert notifiers == []

    def test_gotify_init(self):
        notification._notifiers_cache = None
        with patch.dict(notification.DEFAULTS, {
            'gotify_url': 'http://gotify.local',
            'gotify_token': 'abc123',
        }, clear=True):
            notifiers = notification._get_notifiers()
            assert len(notifiers) == 1
            assert isinstance(notifiers[0], notification.GotifyNotification)

    def test_uptime_kuma_init(self):
        notification._notifiers_cache = None
        with patch.dict(notification.DEFAULTS, {
            'uptime_kuma_webhook_url': 'http://kuma.local/push',
        }, clear=True):
            notifiers = notification._get_notifiers()
            assert len(notifiers) == 1
            assert isinstance(notifiers[0], notification.UptimeKumaNotification)

    def test_cache_reused(self):
        notification._notifiers_cache = None
        with patch.dict(notification.DEFAULTS, {
            'gotify_url': 'http://gotify.local',
            'gotify_token': 'abc123',
        }, clear=True):
            n1 = notification._get_notifiers()
            n2 = notification._get_notifiers()
            assert n1 is n2


class TestAsyncNotification:
    """Test async dispatch."""

    async def test_send_notification_async_calls_sync(self):
        with patch.object(notification, 'send_notification') as mock_sync:
            await notification.send_notification_async("title", "body", 5)
            mock_sync.assert_called_once_with("title", "body", 5)


class TestGotifyNotifier:
    def test_send_success(self):
        notifier = notification.GotifyNotification("http://gotify.local", "token")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        with patch.object(notification, '_get_session') as mock_session:
            mock_session.return_value.post.return_value = mock_resp
            notifier.send_notification("test", "msg")
            mock_session.return_value.post.assert_called_once()

    def test_send_failure_logged(self):
        import requests
        notifier = notification.GotifyNotification("http://gotify.local", "token")
        with patch.object(notification, '_get_session') as mock_session:
            mock_session.return_value.post.side_effect = requests.ConnectionError("fail")
            # Should not raise
            notifier.send_notification("test", "msg")


class TestUptimeKumaNotifier:
    def test_send_success(self):
        notifier = notification.UptimeKumaNotification("http://kuma.local/push")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        with patch.object(notification, '_get_session') as mock_session:
            mock_session.return_value.post.return_value = mock_resp
            notifier.send_notification("test", "msg")
            mock_session.return_value.post.assert_called_once()
