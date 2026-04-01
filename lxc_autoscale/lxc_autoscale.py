"""Main module for LXC autoscaling daemon (async)."""

import argparse
import asyncio
import logging
from typing import Optional

from config import DEFAULTS, LOG_FILE
from logging_setup import setup_logging
from lock_manager import acquire_lock
from lxc_utils import get_containers, rollback_container_settings
from resource_manager import main_loop


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments to configure the daemon's behavior."""
    parser = argparse.ArgumentParser(description="LXC Resource Management Daemon")
    parser.add_argument(
        "--poll_interval", type=int,
        default=DEFAULTS.get('poll_interval', 300),
        help="Polling interval in seconds",
    )
    parser.add_argument(
        "--energy_mode", action="store_true",
        default=DEFAULTS.get('energy_mode', False),
        help="Enable energy efficiency mode during off-peak hours",
    )
    parser.add_argument(
        "--rollback", action="store_true",
        help="Rollback to previous container configurations",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


async def async_main(args: argparse.Namespace) -> None:
    """Async entry point for the daemon."""
    if args.rollback:
        logging.info("Starting rollback process...")
        for ctid in await get_containers():
            await rollback_container_settings(ctid)
        logging.info("Rollback process completed.")
    else:
        await main_loop(args.poll_interval, args.energy_mode)


if __name__ == "__main__":
    args = parse_arguments()
    setup_logging(LOG_FILE, args.debug)
    logging.info("Starting LXC autoscaling daemon")

    with acquire_lock() as lock_file:
        try:
            asyncio.run(async_main(args))
        except (KeyboardInterrupt, SystemExit):
            logging.info("Daemon shutting down.")
        except (ValueError, OSError) as e:
            logging.exception("Error during main execution: %s", e)
        finally:
            logging.info("Releasing lock and exiting.")
