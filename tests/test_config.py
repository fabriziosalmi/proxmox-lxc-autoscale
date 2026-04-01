"""Tests for Pydantic configuration models."""

import os
import sys
import tempfile

import pytest
import yaml

# Add lxc_autoscale to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

from config import DefaultsConfig, TierConfig, SSHConfig, load_config


class TestDefaultsConfig:
    """Test DefaultsConfig Pydantic model."""

    def test_valid_defaults(self):
        cfg = DefaultsConfig()
        assert cfg.poll_interval == 300
        assert cfg.behaviour == "normal"
        assert cfg.timezone == "UTC"
        assert cfg.cpu_upper_threshold == 80
        assert cfg.cpu_lower_threshold == 20
        assert cfg.ssh_host_key_policy == "reject"

    def test_custom_values(self):
        cfg = DefaultsConfig(
            poll_interval=60,
            behaviour="aggressive",
            timezone="America/New_York",
            cpu_upper_threshold=90,
            cpu_lower_threshold=10,
        )
        assert cfg.poll_interval == 60
        assert cfg.behaviour == "aggressive"
        assert cfg.timezone == "America/New_York"

    def test_invalid_behaviour_rejected(self):
        with pytest.raises(Exception):
            DefaultsConfig(behaviour="invalid_mode")

    def test_threshold_validation_lower_ge_upper(self):
        with pytest.raises(ValueError, match="cpu_lower_threshold must be < cpu_upper_threshold"):
            DefaultsConfig(cpu_lower_threshold=80, cpu_upper_threshold=80)

    def test_threshold_validation_lower_gt_upper(self):
        with pytest.raises(ValueError):
            DefaultsConfig(cpu_lower_threshold=90, cpu_upper_threshold=80)

    def test_memory_threshold_validation(self):
        with pytest.raises(ValueError, match="memory_lower_threshold"):
            DefaultsConfig(memory_lower_threshold=85, memory_upper_threshold=80)

    def test_core_limit_validation(self):
        with pytest.raises(ValueError, match="min_cores must be <= max_cores"):
            DefaultsConfig(min_cores=8, max_cores=4)

    def test_extra_fields_allowed(self):
        """Backward compat: unknown YAML keys shouldn't crash."""
        cfg = DefaultsConfig(some_future_field="value")
        assert cfg.poll_interval == 300  # defaults still work

    def test_env_override(self):
        """Test that env vars can override secrets."""
        os.environ["LXC_AUTOSCALE_SSH_PASSWORD"] = "test_secret"
        try:
            cfg = DefaultsConfig(ssh_password="yaml_value")
            # The env override happens at load_config level, not model level
            assert cfg.ssh_password == "yaml_value"
        finally:
            del os.environ["LXC_AUTOSCALE_SSH_PASSWORD"]


class TestSSHConfig:
    """Test SSH configuration model."""

    def test_default_policy_is_reject(self):
        cfg = SSHConfig()
        assert cfg.host_key_policy == "reject"

    def test_system_policy(self):
        cfg = SSHConfig(host_key_policy="system")
        assert cfg.host_key_policy == "system"

    def test_auto_policy(self):
        cfg = SSHConfig(host_key_policy="auto")
        assert cfg.host_key_policy == "auto"

    def test_invalid_policy_rejected(self):
        with pytest.raises(Exception):
            SSHConfig(host_key_policy="yolo")

    def test_get_ssh_config_from_defaults(self):
        defaults = DefaultsConfig(
            proxmox_host="192.168.1.1",
            ssh_port=2222,
            ssh_user="admin",
            ssh_host_key_policy="system",
        )
        ssh = defaults.get_ssh_config()
        assert ssh.host == "192.168.1.1"
        assert ssh.port == 2222
        assert ssh.user == "admin"
        assert ssh.host_key_policy == "system"


class TestTierConfig:
    """Test tier configuration model."""

    def test_valid_tier(self):
        tier = TierConfig(
            lxc_containers=["101", "102"],
            cpu_upper_threshold=70,
            cpu_lower_threshold=20,
            tier_name="webservers",
        )
        assert tier.tier_name == "webservers"
        assert "101" in tier.lxc_containers

    def test_tier_threshold_validation(self):
        with pytest.raises(ValueError):
            TierConfig(cpu_lower_threshold=80, cpu_upper_threshold=70)

    def test_tier_core_validation(self):
        with pytest.raises(ValueError):
            TierConfig(min_cores=8, max_cores=2)


class TestLoadConfig:
    """Test full YAML config loading."""

    def test_load_valid_yaml(self):
        config_data = {
            'DEFAULT': {
                'poll_interval': 120,
                'behaviour': 'conservative',
                'timezone': 'Europe/London',
                'cpu_upper_threshold': 85,
                'cpu_lower_threshold': 15,
                'ignore_lxc': [104, 105],
            },
            'TIER_web': {
                'lxc_containers': [101, 102],
                'cpu_upper_threshold': 70,
                'cpu_lower_threshold': 20,
                'memory_upper_threshold': 80,
                'memory_lower_threshold': 20,
                'min_cores': 2,
                'max_cores': 8,
                'min_memory': 1024,
            },
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()
            try:
                app_cfg = load_config(f.name)
                assert app_cfg.defaults.poll_interval == 120
                assert app_cfg.defaults.behaviour == "conservative"
                assert app_cfg.defaults.timezone == "Europe/London"
                assert "104" in set(app_cfg.defaults.ignore_lxc)
                assert "101" in app_cfg.tier_associations
                assert app_cfg.tier_associations["101"].tier_name == "web"
                assert app_cfg.tier_associations["101"].max_cores == 8
            finally:
                os.unlink(f.name)

    def test_load_missing_file(self):
        """Missing file should return defaults, not crash."""
        app_cfg = load_config("/nonexistent/path.yaml")
        assert app_cfg.defaults.poll_interval == 300

    def test_get_tier_or_defaults(self):
        app_cfg = load_config("/nonexistent/path.yaml")
        result = app_cfg.get_tier_or_defaults("999")
        assert result.cpu_upper_threshold == 80  # default

    def test_backward_compat_aliases(self):
        """Check that legacy module-level aliases work."""
        from config import DEFAULTS, IGNORE_LXC, LOG_FILE, config
        assert isinstance(DEFAULTS, dict)
        assert isinstance(IGNORE_LXC, set)
        assert isinstance(LOG_FILE, str)
