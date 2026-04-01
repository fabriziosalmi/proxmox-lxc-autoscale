"""Security-focused tests for LXC autoscale."""

import asyncio
import os
import re
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))


class TestContainerIdValidation(unittest.TestCase):
    """Container IDs that contain shell metacharacters must be rejected."""

    def test_rejects_shell_injection(self):
        from lxc_utils import validate_container_id
        for bad_id in ['$(reboot)', '100; rm -rf /', '100\nreboot', '', 'abc']:
            with self.assertRaises(ValueError, msg=f"Should reject {bad_id!r}"):
                validate_container_id(bad_id)

    def test_valid_numeric(self):
        from lxc_utils import validate_container_id
        for good_id in ['0', '100', '999999']:
            validate_container_id(good_id)  # should not raise


class TestHostnameSanitisation(unittest.TestCase):
    """Cloned hostnames must be RFC-1123 safe."""

    def test_normal_name(self):
        from lxc_utils import generate_cloned_hostname
        self.assertEqual(generate_cloned_hostname('web', 1), 'web-cloned-1')

    def test_strips_special_chars(self):
        from lxc_utils import generate_cloned_hostname
        result = generate_cloned_hostname('bad;name$(cmd)', 2)
        self.assertFalse(any(c in result for c in ';$()'))
        self.assertTrue(re.match(r'^[a-zA-Z0-9-]+$', result))

    def test_empty_fallback(self):
        from lxc_utils import generate_cloned_hostname
        result = generate_cloned_hostname(';;;', 3)
        self.assertTrue(result.startswith('container-cloned-'))


class TestPerContainerLocking(unittest.TestCase):
    """Per-container locks should be independent."""

    def test_same_container_returns_same_lock(self):
        from lxc_utils import _get_container_lock
        a = _get_container_lock('100')
        b = _get_container_lock('100')
        self.assertIs(a, b)

    def test_different_containers_get_different_locks(self):
        from lxc_utils import _get_container_lock
        a = _get_container_lock('100')
        b = _get_container_lock('200')
        self.assertIsNot(a, b)


class TestRunLocalCommandShellFalse(unittest.TestCase):
    """Local commands must run with shell=False (async)."""

    @patch('lxc_utils.asyncio.create_subprocess_exec')
    def test_list_cmd_uses_shell_false(self, mock_exec):
        """List command should use create_subprocess_exec (inherently shell=False)."""
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"output", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        from lxc_utils import run_local_command
        result = asyncio.run(run_local_command(["echo", "hello"]))
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0]
        self.assertEqual(call_args, ("echo", "hello"))

    @patch('lxc_utils.asyncio.create_subprocess_exec')
    def test_string_cmd_uses_shell_false(self, mock_exec):
        """String command should be split and use create_subprocess_exec."""
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"output", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        from lxc_utils import run_local_command
        result = asyncio.run(run_local_command("echo hello"))
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0]
        self.assertEqual(call_args, ("echo", "hello"))


class TestSecretEnvOverrides(unittest.TestCase):
    """Environment variables should override secrets in config."""

    def test_env_vars_injected(self):
        raw = {'DEFAULT': {}}
        os.environ['LXC_AUTOSCALE_SSH_PASSWORD'] = 'from_env'
        try:
            from config import _apply_env_overrides
            _apply_env_overrides(raw)
            self.assertEqual(raw['DEFAULT']['ssh_password'], 'from_env')
        finally:
            del os.environ['LXC_AUTOSCALE_SSH_PASSWORD']


class TestConfigPermissionWarning(unittest.TestCase):
    """Config file with world-readable permissions should warn."""

    def test_warns_on_world_readable(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('DEFAULT: {}')
            f.flush()
            os.chmod(f.name, 0o644)
            try:
                from config import _check_config_permissions
                with self.assertLogs(level='WARNING') as cm:
                    _check_config_permissions(f.name)
                self.assertTrue(any('readable by group' in m for m in cm.output))
            finally:
                os.unlink(f.name)


class TestTierContainerIdValidation(unittest.TestCase):
    """Verify invalid container IDs are skipped during tier loading."""

    def test_invalid_ctid_skipped(self):
        raw = {
            'TIER_test': {
                'lxc_containers': ['100', '$(evil)', '200'],
                'cpu_upper_threshold': 80,
                'cpu_lower_threshold': 20,
                'memory_upper_threshold': 80,
                'memory_lower_threshold': 20,
                'min_cores': 1,
                'max_cores': 4,
                'min_memory': 512,
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(raw, f)
            f.flush()
            try:
                from config import load_config
                app_cfg = load_config(f.name)
                tiers = app_cfg.tier_associations
                self.assertIn('100', tiers)
                self.assertIn('200', tiers)
                self.assertNotIn('$(evil)', tiers)
            finally:
                os.unlink(f.name)


if __name__ == '__main__':
    unittest.main()
