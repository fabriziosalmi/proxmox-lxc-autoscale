import logging  # Import the logging module to handle logging throughout the application
from config import get_config_value  # Import the get_config_value function to retrieve configuration settings

# Retrieve the log file path from the configuration
LOG_FILE = get_config_value('DEFAULT', 'log_file', '/var/log/lxc_autoscale.log')

def setup_logging():
    """
    Set up the logging configuration for the application.
    This function configures logging to write to both a log file and the console.
    
    Log messages will include timestamps and the severity level of the message.
    """
    
    # Configure the logging to write to a file with the specified format and date format
    logging.basicConfig(
        filename=LOG_FILE,  # Log file path
        level=logging.INFO,  # Log level: INFO (this can be adjusted to DEBUG, WARNING, etc.)
        format='%(asctime)s - %(levelname)s - %(message)s',  # Format of log messages
        datefmt='%Y-%m-%d %H:%M:%S'  # Date format for timestamps
    )

    # Create a console handler to output log messages to the console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)  # Set the logging level for the console output

    # Define the format for console log messages
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console.setFormatter(formatter)  # Apply the format to the console handler

    # Add the console handler to the root logger, so it outputs to both file and console
    logging.getLogger().addHandler(console)
