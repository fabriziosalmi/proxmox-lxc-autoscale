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

    def test_secrets_from_a_module_logger_are_masked(self):
        """The filter used to sit on the root logger, where it saw almost nothing.

        A filter attached to a logger runs only for records emitted through that
        logger; records from child loggers reach an ancestor's handlers without
        passing its filters. Every module here uses getLogger(__name__), so the
        thing to assert is behaviour through a child logger, not attachment.
        """
        import io
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
        for f in list(root.filters):
            root.removeFilter(f)

        setup_logging(log_file=None, debug=False)
        buf = io.StringIO()
        captured = logging.StreamHandler(buf)
        captured.setFormatter(logging.Formatter("%(message)s"))
        for h in root.handlers:
            for f in h.filters:
                captured.addFilter(f)
        root.addHandler(captured)

        logging.getLogger("lxc_utils").info("ssh_password=hunter2")
        logging.getLogger("notification").error("token: abcdef123456")

        out = buf.getvalue()
        assert "hunter2" not in out
        assert "abcdef123456" not in out
        assert "REDACTED" in out

        for h in list(root.handlers):
            root.removeHandler(h)

    def test_masking_filter_is_on_the_handlers(self):
        for h in list(logging.getLogger().handlers):
            logging.getLogger().removeHandler(h)
        setup_logging(log_file=None, debug=False)
        handlers = logging.getLogger().handlers
        assert handlers, "setup_logging installed no handler"
        assert all(
            any(isinstance(f, SecretMaskingFilter) for f in h.filters)
            for h in handlers
        ), "a handler would write unmasked output"
        for h in list(handlers):
            logging.getLogger().removeHandler(h)

    def test_paramiko_logging_suppressed(self):
        setup_logging(log_file=None, debug=False)
        assert logging.getLogger('paramiko').level == logging.WARNING
        for h in list(logging.getLogger().handlers):
            logging.getLogger().removeHandler(h)
        for f in list(logging.getLogger().filters):
            logging.getLogger().removeFilter(f)
