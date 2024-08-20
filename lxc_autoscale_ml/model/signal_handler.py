import signal
import logging
import sys

def setup_signal_handlers(cleanup_function=None):
    """
    Sets up signal handlers to handle termination signals (SIGINT and SIGTERM) gracefully.

    :param cleanup_function: A function to be called for cleanup before exiting (optional).
    """
    def signal_handler(signum, frame):
        """
        Handles received signals, logs them, and exits the program gracefully.

        :param signum: The signal number received.
        :param frame: The current stack frame (not used).
        """
        signal_name = signal.Signals(signum).name  # Get a more descriptive signal name
        logging.info(f"Received {signal_name} ({signum}). Exiting gracefully.")
        
        # Call the cleanup function if provided
        if cleanup_function:
            logging.info("Performing cleanup before exiting...")
            try:
                cleanup_function()
            except Exception as e:
                logging.error(f"Error during cleanup: {e}")
        
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logging.info("Signal handlers for SIGINT and SIGTERM are set up.")
