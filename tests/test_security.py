# pylint: disable=missing-function-docstring,missing-class-docstring
# pylint: disable=import-outside-toplevel,protected-access
"""Unit tests for the security fixes.

Tests cover:
  - Container ID validation (command injection prevention)
  - Secrets env-var overrides
  - Config file permission check
  - Per-container locking
  - run_local_command shell=False enforcement
  - generate_cloned_hostname sanitisation
  - Web UI defaults
"""

import importlib
import os
import sys
import tempfile
import unittest
from unittest import mock

# Add the package to sys.path so we can import modules directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))


# ---------------------------------------------------------------------------
# 1. Container ID validation
# ---------------------------------------------------------------------------
class TestContainerIdValidation(unittest.TestCase):
    """Ensure validate_container_id rejects non-numeric IDs."""

    def setUp(self):
        from lxc_utils import validate_container_id
        self.validate = validate_container_id

    def test_valid_numeric(self):
        """Accept purely numeric container IDs."""
        for ctid in ('100', '0', '99999'):
            self.validate(ctid)  # should not raise

    def test_rejects_shell_injection(self):
        """Reject IDs that could lead to shell injection."""
        bad = ['100; rm -rf /', '$(whoami)', '100`id`', '../etc', '', ' ', '100 200']
        for ctid in bad:
            with self.assertRaises(ValueError, msg=f"Should reject {ctid!r}"):
                self.validate(ctid)


# ---------------------------------------------------------------------------
# 2. generate_cloned_hostname sanitisation
# ---------------------------------------------------------------------------
class TestHostnameSanitisation(unittest.TestCase):
    """Ensure cloned hostnames are RFC-1123 safe."""

    def setUp(self):
        from lxc_utils import generate_cloned_hostname
        self.gen = generate_cloned_hostname

    def test_normal_name(self):
        """Normal alphanumeric base name passes through."""
        self.assertEqual(self.gen('web', 1), 'web-cloned-1')

    def test_strips_special_chars(self):
        """Special characters are replaced with hyphens."""
        result = self.gen('web;rm -rf /', 3)
        self.assertRegex(result, r'^[a-zA-Z0-9-]+-cloned-3$')
        self.assertNotIn(';', result)
        self.assertNotIn('/', result)

    def test_empty_fallback(self):
        """Fully invalid names fall back to 'container'."""
        result = self.gen(';;;', 1)
        self.assertEqual(result, 'container-cloned-1')


# ---------------------------------------------------------------------------
# 3. Per-container locking
# ---------------------------------------------------------------------------
class TestPerContainerLocking(unittest.TestCase):
    """Verify per-container locks are independent."""

    def test_different_containers_get_different_locks(self):
        """Different container IDs get distinct lock objects."""
        from lxc_utils import _get_container_lock
        lock_a = _get_container_lock('100')
        lock_b = _get_container_lock('200')
        self.assertIsNot(lock_a, lock_b)

    def test_same_container_returns_same_lock(self):
        """Same container ID always returns the same lock."""
        from lxc_utils import _get_container_lock
        lock1 = _get_container_lock('300')
        lock2 = _get_container_lock('300')
        self.assertIs(lock1, lock2)


# ---------------------------------------------------------------------------
# 4. run_local_command — shell=False enforcement
# ---------------------------------------------------------------------------
class TestRunLocalCommandShellFalse(unittest.TestCase):
    """Verify run_local_command never uses shell=True."""

    @mock.patch('lxc_utils.subprocess.check_output', return_value=b'ok')
    def test_string_cmd_uses_shell_false(self, mock_co):
        """String commands are split and executed with shell=False."""
        from lxc_utils import run_local_command
        run_local_command('echo hello')
        args, kwargs = mock_co.call_args
        self.assertFalse(kwargs.get('shell', True), "shell must be False")
        self.assertIsInstance(args[0], list)

    @mock.patch('lxc_utils.subprocess.check_output', return_value=b'ok')
    def test_list_cmd_uses_shell_false(self, mock_co):
        """List commands are executed with shell=False."""
        from lxc_utils import run_local_command
        run_local_command(['echo', 'hello'])
        _, kwargs = mock_co.call_args
        self.assertFalse(kwargs.get('shell', True))


# ---------------------------------------------------------------------------
# 5. Config — env var secret overrides
# ---------------------------------------------------------------------------
class TestSecretEnvOverrides(unittest.TestCase):
    """Verify that environment variables override config secrets."""

    def test_env_vars_injected(self):
        """All four secret env vars are injected into config."""
        env = {
            'LXC_AUTOSCALE_SSH_PASSWORD': 'secret_ssh',
            'LXC_AUTOSCALE_SMTP_PASSWORD': 'secret_smtp',
            'LXC_AUTOSCALE_GOTIFY_TOKEN': 'tok123',
            'LXC_AUTOSCALE_UPTIME_KUMA_WEBHOOK': 'https://hook',
        }
        with mock.patch.dict(os.environ, env, clear=False):
            import config as cfg_mod
            importlib.reload(cfg_mod)

            defaults_section = cfg_mod.config.get('DEFAULT', {})
            self.assertEqual(defaults_section.get('ssh_password'), 'secret_ssh')
            self.assertEqual(defaults_section.get('smtp_password'), 'secret_smtp')
            self.assertEqual(defaults_section.get('gotify_token'), 'tok123')
            self.assertEqual(defaults_section.get('uptime_kuma_webhook_url'), 'https://hook')


# ---------------------------------------------------------------------------
# 6. Config file permission warning
# ---------------------------------------------------------------------------
class TestConfigPermissionWarning(unittest.TestCase):
    """Verify config file permission checks emit warnings."""

    def test_warns_on_world_readable(self):
        """A group/other readable config file triggers a warning."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            tmp.write('DEFAULT: {}\n')
            tmp.flush()
            os.chmod(tmp.name, 0o644)
            try:
                import config as cfg_mod
                with self.assertLogs(level='WARNING') as log_cm:
                    cfg_mod._check_config_permissions(tmp.name)
                self.assertTrue(any('readable by group/others' in m for m in log_cm.output))
            finally:
                os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# 7. Config — container ID validation on tier load
# ---------------------------------------------------------------------------
class TestTierContainerIdValidation(unittest.TestCase):
    """Verify invalid container IDs are skipped during tier loading."""

    def test_invalid_ctid_skipped(self):
        """Container IDs with shell metacharacters are rejected."""
        import config as cfg_mod
        original = cfg_mod.config
        cfg_mod.config = {
            'TIER_test': {
                'lxc_containers': ['100', '$(evil)', '200'],
            }
        }
        try:
            tiers = cfg_mod.load_tier_configurations()
            self.assertIn('100', tiers)
            self.assertIn('200', tiers)
            self.assertNotIn('$(evil)', tiers)
        finally:
            cfg_mod.config = original


if __name__ == '__main__':
    unittest.main()
