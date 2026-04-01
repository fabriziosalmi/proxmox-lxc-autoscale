"""Logging configuration for LXC autoscale.

Includes a secret masking filter (#8) that redacts passwords, tokens,
and API keys from log output to prevent credential leaks to disk.
"""

import logging
import logging.handlers
import os
import re
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# #8: Secret masking filter — redacts sensitive values in log messages
# ---------------------------------------------------------------------------

# Patterns that look like secrets in log output
_SECRET_PATTERNS = [
    # password=xxx, -p xxx, sshpass -p xxx
    re.compile(r'(?i)(password|passwd|pwd|secret|token|api[_-]?key|apikey)\s*[=:]\s*\S+'),
    # Bearer tokens
    re.compile(r'(?i)Bearer\s+\S+'),
    # Generic long hex/base64 strings (32+ chars, likely tokens)
    re.compile(r'(?<![a-zA-Z0-9/])[A-Za-z0-9+/=_-]{32,}(?![a-zA-Z0-9/])'),
    # sshpass -p <password>
    re.compile(r'sshpass\s+-p\s+\S+'),
    # SSH key paths might leak in errors — not redacted, just passwords
]

_REDACTION = '***REDACTED***'


class SecretMaskingFilter(logging.Filter):
    """Logging filter that masks secret-looking strings in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._mask(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._mask(str(v)) if isinstance(v, str) else v
                               for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._mask(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True

    @staticmethod
    def _mask(text: str) -> str:
        for pattern in _SECRET_PATTERNS:
            text = pattern.sub(_REDACTION, text)
        return text


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_logging(log_file: Optional[str] = None, debug: bool = False) -> None:
    """Configure logging with console and file handlers + secret masking."""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Add secret masking filter to root logger
    root_logger.addFilter(SecretMaskingFilter())

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    logging.getLogger('paramiko').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
