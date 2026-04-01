"""Tests for lock_manager — exclusive file locking."""

import os
import sys
import tempfile
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))


class TestAcquireLock:
    def test_lock_and_release(self, tmp_path):
        lock_file = str(tmp_path / "test.lock")
        with patch('lock_manager.LOCK_FILE', lock_file):
            from lock_manager import acquire_lock
            with acquire_lock() as lf:
                assert lf is not None
                assert not lf.closed
            # After context exit, file should be closed
            assert lf.closed

    def test_lock_creates_file(self, tmp_path):
        lock_file = str(tmp_path / "new.lock")
        with patch('lock_manager.LOCK_FILE', lock_file):
            from lock_manager import acquire_lock
            with acquire_lock():
                assert os.path.exists(lock_file)

    def test_lock_file_is_writable(self, tmp_path):
        lock_file = str(tmp_path / "writable.lock")
        with patch('lock_manager.LOCK_FILE', lock_file):
            from lock_manager import acquire_lock
            with acquire_lock() as lf:
                # Should be open for writing
                lf.write("locked\n")
                lf.flush()
                assert os.path.getsize(lock_file) > 0
