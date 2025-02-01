"""Main module for LXC autoscaling daemon."""

import argparse
import logging
import os  # Added import for directory operations
from typing import Optional

import paramiko  # Import the paramiko library

from config import DEFAULTS, get_config_value, IGNORE_LXC, LOG_FILE, PROXMOX_HOSTNAME, BACKUP_DIR  # Import configuration constants and utility functions
from logging_setup import setup_logging  # Import the logging setup function
from lock_manager import acquire_lock  # Function to acquire a lock, ensuring only one instance of the script runs
from lxc_utils import get_containers, rollback_container_settings  # Utility functions for managing LXC containers
from resource_manager import main_loop  # Main loop function that handles the resource allocation and scaling process



def parse_arguments() -> argparse.Namespace:
    """
    Parses command-line arguments to configure the daemon's behavior.

    Returns:
        argparse.Namespace: The parsed arguments with options for poll interval, energy mode, and rollback.
    """
    parser = argparse.ArgumentParser(description="LXC Resource Management Daemon")

    # Polling interval argument
    parser.add_argument(
        "--poll_interval",
        type=int,
        default=DEFAULTS.get('poll_interval', 300),
        help="Polling interval in seconds"  # How often the main loop should run
    )

    # Energy mode argument for off-peak hours
    parser.add_argument(
        "--energy_mode",
        action="store_true",
        default=DEFAULTS.get('energy_mode', False),
        help="Enable energy efficiency mode during off-peak hours"  # Reduces resource allocation during low-usage periods
    )

    # Rollback argument to revert container configurations
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback to previous container configurations"  # Option to revert containers to their backed-up settings
    )

    return parser.parse_args()


# Entry point of the script
if __name__ == "__main__":
    # Parse command-line arguments
    args: argparse.Namespace = parse_arguments()

    # Remove automatic creation of log directory and file

    # Setup logging based on the configuration
    setup_logging()

    # Acquire a lock to ensure that only one instance of the script runs at a time
    with acquire_lock() as lock_file:
        try:
            if args.rollback:
                # If the rollback argument is provided, start the rollback process
                logging.info("Starting rollback process...")
                for ctid in get_containers():
                    # Rollback settings for each container
                    rollback_container_settings(ctid)
                logging.info("Rollback process completed.")
            else:
                # If not rolling back, enter the main loop to manage resources
                main_loop(args.poll_interval, args.energy_mode)
        except Exception as e:
            logging.exception(f"An error occurred during main execution: {e}")

        finally:
            # Ensure that the lock is released and the script exits cleanly
            logging.info("Releasing lock and exiting.")