"""Tests for logging_setup — SecretMaskingFilter and setup_logging."""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

from logging_setup import SecretMaskingFilter, setup_logging


class TestSetupLogging:
    """Test logging configuration."""

    def test_setup_with_file(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        setup_logging(log_file, debug=False)
        root = logging.getLogger()
        assert root.level == logging.INFO
        # Should have at least console + file handler
        assert len(root.handlers) >= 2
        # Cleanup
        for h in list(root.handlers):
            root.removeHandler(h)

    def test_setup_debug_mode(self, tmp_path):
        log_file = str(tmp_path / "debug.log")
        setup_logging(log_file, debug=True)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        for h in list(root.handlers):
            root.removeHandler(h)

    def test_setup_no_file(self):
        setup_logging(log_file=None, debug=False)
        root = logging.getLogger()
        # Should work without a file handler
        assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
        for h in list(root.handlers):
            root.removeHandler(h)

    def test_masking_filter_attached(self):
        setup_logging(log_file=None, debug=False)
        root = logging.getLogger()
        assert any(isinstance(f, SecretMaskingFilter) for f in root.filters)
        for h in list(root.handlers):
            root.removeHandler(h)
        for f in list(root.filters):
            root.removeFilter(f)

    def test_paramiko_logging_suppressed(self):
        setup_logging(log_file=None, debug=False)
        assert logging.getLogger('paramiko').level == logging.WARNING
        for h in list(logging.getLogger().handlers):
            logging.getLogger().removeHandler(h)
        for f in list(logging.getLogger().filters):
            logging.getLogger().removeFilter(f)
