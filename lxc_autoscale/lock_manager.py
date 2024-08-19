import fcntl  # Provides file control and I/O control operations
import sys  # Used to exit the script
import os  # Provides a way of using operating system dependent functionality
import logging  # Used for logging errors and other messages
from contextlib import contextmanager  # Allows the creation of a context manager
from config import get_config_value  # Import configuration utility

# Retrieve the lock file path from the configuration
LOCK_FILE = get_config_value('DEFAULT', 'lock_file', '/var/lock/lxc_autoscale.lock')

@contextmanager
def acquire_lock():
    """
    Context manager to acquire a lock on the lock file.
    This prevents multiple instances of the script from running concurrently.
    
    The lock is achieved by opening a file in write mode and applying an exclusive lock.
    If the lock is already held by another instance, an IOError is raised,
    which causes the script to exit.
    
    The lock is automatically released when the context manager exits.
    """
    # Open the lock file for writing
    lock_file = open(LOCK_FILE, 'w')
    try:
        # Try to acquire an exclusive lock on the file (non-blocking)
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Yield control back to the calling context, keeping the lock in place
        yield lock_file
    except IOError:
        # If the lock is already held by another process, log an error and exit
        logging.error("Another instance of the script is already running. Exiting to avoid overlap.")
        sys.exit(1)
    finally:
        # Ensure the lock file is closed when done, releasing the lock
        lock_file.close()
