"""Exclusive file locking to prevent concurrent daemon instances."""

import fcntl
import logging
import os
import sys
from contextlib import contextmanager

from config import get_config_value

LOCK_FILE = get_config_value('DEFAULT', 'lock_file', '/var/lock/lxc_autoscale.lock')


@contextmanager
def acquire_lock():
    """Context manager to acquire an exclusive lock on the lock file.

    Prevents multiple daemon instances from running concurrently.
    The lock is released when the context manager exits.
    """
    fd = os.open(LOCK_FILE, os.O_WRONLY | os.O_CREAT, 0o600)
    lock_file = os.fdopen(fd, 'w')
    try:
        logging.info("Acquiring lock on %s", LOCK_FILE)
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logging.info("Lock acquired on %s", LOCK_FILE)
        yield lock_file
    except IOError:
        logging.error(
            "Another instance is already running. Exiting."
        )
        sys.exit(1)
    finally:
        logging.info("Lock released on %s", LOCK_FILE)
        lock_file.close()
