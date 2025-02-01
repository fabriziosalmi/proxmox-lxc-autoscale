import logging
import os
from config import LOG_FILE  # ...existing imports...

def setup_logging():
    # ...existing code...
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # Clear any existing handlers
    logger.handlers = []
    
    # Console handler (unchanged)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Ensure log directory exists
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # File handler with append mode
    file_handler = logging.FileHandler(LOG_FILE, mode='a')
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    logging.info(f"Logging is set up. Log file: {LOG_FILE}")
