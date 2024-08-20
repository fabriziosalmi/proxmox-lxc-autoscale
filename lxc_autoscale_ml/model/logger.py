import logging
from logging.handlers import RotatingFileHandler

import logging

def setup_logging(log_file, log_level="INFO"):
    """
    Set up logging to log to both a file and the console.

    :param log_file: Path to the log file.
    :param log_level: The logging level (default is "INFO").
    """
    # Convert log level string to logging level
    log_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # Define log format
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
