"""Red team tests — verify security hardening holds under adversarial input."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))


class TestTimezoneValidation:
    """Config must reject invalid timezone strings at load time."""

    def test_valid_timezone(self):
        from config import DefaultsConfig
        cfg = DefaultsConfig(timezone="Europe/Rome")
        assert cfg.timezone == "Europe/Rome"

    def test_invalid_timezone_rejected(self):
        from config import DefaultsConfig
        with pytest.raises(ValueError, match="Invalid timezone"):
            DefaultsConfig(timezone="Mars/Olympus_Mons")

    def test_utc_default(self):
        from config import DefaultsConfig
        cfg = DefaultsConfig()
        assert cfg.timezone == "UTC"


class TestOffPeakHourValidation:
    """off_peak_start and off_peak_end must be 0-23."""

    def test_valid_hours(self):
        from config import DefaultsConfig
        cfg = DefaultsConfig(off_peak_start=0, off_peak_end=23)
        assert cfg.off_peak_start == 0

    def test_start_too_high(self):
        from config import DefaultsConfig
        with pytest.raises(ValueError, match="off_peak_start must be 0-23"):
            DefaultsConfig(off_peak_start=25)

    def test_end_negative(self):
        from config import DefaultsConfig
        with pytest.raises(ValueError, match="off_peak_end must be 0-23"):
            DefaultsConfig(off_peak_end=-1)


class TestHorizontalGroupCtidValidation:
    """Container IDs in horizontal scaling groups must be numeric."""

    def test_valid_ids(self):
        from config import HorizontalScalingGroup
        g = HorizontalScalingGroup(lxc_containers={"100", "200"})
        assert "100" in g.lxc_containers

    def test_invalid_id_rejected(self):
        from config import HorizontalScalingGroup
        with pytest.raises(ValueError, match="Invalid container ID"):
            HorizontalScalingGroup(lxc_containers={"100", "$(evil)"})

    def test_base_snapshot_must_be_numeric(self):
        from config import HorizontalScalingGroup
        with pytest.raises(ValueError, match="Invalid base_snapshot_name"):
            HorizontalScalingGroup(base_snapshot_name="not_numeric")

    def test_base_snapshot_numeric_ok(self):
        from config import HorizontalScalingGroup
        g = HorizontalScalingGroup(base_snapshot_name="100")
        assert g.base_snapshot_name == "100"

    def test_base_snapshot_empty_ok(self):
        from config import HorizontalScalingGroup
        g = HorizontalScalingGroup(base_snapshot_name="")
        assert g.base_snapshot_name == ""


class TestSSRFPrevention:
    """Webhook URLs pointing to internal addresses must be rejected."""

    def test_localhost_rejected(self):
        from notification import _is_safe_url
        assert _is_safe_url("http://localhost:8080/hook") is False

    def test_127_rejected(self):
        from notification import _is_safe_url
        assert _is_safe_url("http://127.0.0.1/msg") is False

    def test_ipv6_loopback_rejected(self):
        from notification import _is_safe_url
        assert _is_safe_url("http://[::1]/msg") is False

    def test_private_ip_rejected(self):
        from notification import _is_safe_url
        assert _is_safe_url("http://10.0.0.1:9090/hook") is False
        assert _is_safe_url("http://192.168.1.1/hook") is False
        assert _is_safe_url("http://172.16.0.1/hook") is False

    def test_link_local_rejected(self):
        from notification import _is_safe_url
        # AWS metadata endpoint
        assert _is_safe_url("http://169.254.169.254/latest/meta-data") is False

    def test_public_ip_allowed(self):
        from notification import _is_safe_url
        assert _is_safe_url("https://gotify.example.com/message") is True

    def test_hostname_allowed(self):
        from notification import _is_safe_url
        assert _is_safe_url("https://hooks.slack.com/services/T/B/x") is True

    def test_empty_url_rejected(self):
        from notification import _is_safe_url
        assert _is_safe_url("") is False

    def test_malformed_url_rejected(self):
        from notification import _is_safe_url
        assert _is_safe_url("not a url") is False

    def test_zero_ip_rejected(self):
        from notification import _is_safe_url
        assert _is_safe_url("http://0.0.0.0/hook") is False


class TestSedInjectionRemoved:
    """The remote CPU pinning path must not use sed with user data."""

    def test_no_sed_in_pinning(self):
        import lxc_utils
        import inspect
        source = inspect.getsource(lxc_utils.apply_cpu_pinning)
        # sed should not appear in the pinning function anymore
        assert '"sed"' not in source, "sed still used in apply_cpu_pinning"
