from flask import jsonify, current_app
import logging

# Centralized error handler
def handle_error(exception, status_code=500):
    error_handling_config = current_app.config.get('ERROR_HANDLING', {})

    # Log the error if logging is enabled
    if error_handling_config.get('log_errors', True):
        logging.error(f"Error occurred: {str(exception)}")

    # Optionally notify on critical errors
    if status_code >= 500 and error_handling_config.get('notify_on_critical_errors', False):
        notify_on_critical_error(exception)

    # Optionally show stack traces (in non-production environments)
    if error_handling_config.get('show_stack_traces', False):
        response = {
            "status": "error",
            "message": str(exception),
            "stack_trace": repr(exception)
        }
    else:
        response = {
            "status": "error",
            "message": "An internal error occurred. Please contact support if the issue persists."
        }

    return jsonify(response), status_code

# Function to notify admins of critical errors (stub function)
def notify_on_critical_error(exception):
    error_handling_config = current_app.config['ERROR_HANDLING']
    recipients = error_handling_config.get('notification_recipients', [])

    # Log the notification action
    logging.info(f"Notifying recipients of critical error: {', '.join(recipients)}")

    # Implement actual notification logic (e.g., send an email or post to a Slack channel)
    # This is a placeholder for demonstration purposes
    for recipient in recipients:
        logging.info(f"Notified {recipient} of the error: {str(exception)}")
