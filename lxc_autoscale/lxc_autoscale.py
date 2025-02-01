"""Main module for LXC autoscaling daemon."""

import argparse
import logging
from typing import Optional

from config import DEFAULTS, LOG_FILE
from logging_setup import setup_logging
from lock_manager import acquire_lock
from lxc_utils import get_containers, rollback_container_settings
from resource_manager import main_loop



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

    args = parser.parse_args()
    logging.debug(f"Parsed arguments: {args}")
    return args


# Entry point of the script
if __name__ == "__main__":
    # Setup logging with the configured log file
    setup_logging(LOG_FILE)

    # Parse command-line arguments
    args: argparse.Namespace = parse_arguments()

    logging.info("Starting LXC autoscaling daemon with arguments: %s", args)

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