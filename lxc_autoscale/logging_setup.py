import logging  # Import the logging module to handle logging throughout the application
import os  # Import os module to handle directory operations

def setup_logging(log_file: str = '/var/log/lxc_autoscale.log') -> None:
    """
    Set up the logging configuration for the application.
    This function configures logging to write to both a log file and the console.
    
    Log messages will include timestamps and the severity level of the message.
    """
    
    # Ensure the directory for the log file exists
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Configure the logging to write to a file with the specified format and date format
    logging.basicConfig(
        filename=log_file,  # Log file path
        level=logging.INFO,  # Log level: INFO (this can be adjusted to DEBUG, WARNING, etc.)
        format='%(asctime)s - %(levelname)s - %(message)s',  # Format of log messages
        datefmt='%Y-%m-%d %H:%M:%S'  # Date format for timestamps
    )

    # Debug: Verify that the log file is writable
    try:
        with open(log_file, 'a') as f:
            f.write("# Log file initialized successfully.\n")
    except Exception as err:
        print(f"Error writing to log file ({log_file}): {err}")

    # Create a console handler to output log messages to the console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)  # Set the logging level for the console output

    # Define the format for console log messages
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console.setFormatter(formatter)  # Apply the format to the console handler

    # Add the console handler to the root logger, so it outputs to both file and console
    logging.getLogger().addHandler(console)

    # Ensure that log messages are flushed immediately to the file.
    logging.info("Logging is set up. Log file: %s", log_file)
    for handler in logging.getLogger().handlers:
        if hasattr(handler, 'flush'):
            handler.flush()
