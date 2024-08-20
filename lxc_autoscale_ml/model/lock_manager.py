import os
import sys
import logging

def create_lock_file(lock_file):
    if os.path.exists(lock_file):
        logging.error("Another instance of the script is already running. Exiting.")
        sys.exit(1)
    else:
        with open(lock_file, 'w') as lf:
            lf.write(str(os.getpid()))
        logging.info(f"Lock file created at {lock_file}.")

def remove_lock_file(lock_file):
    if os.path.exists(lock_file):
        os.remove(lock_file)
        logging.info(f"Lock file {lock_file} removed.")
    else:
        logging.warning(f"Lock file {lock_file} was not found.")
