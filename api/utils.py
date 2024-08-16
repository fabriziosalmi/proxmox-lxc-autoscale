from flask import jsonify, current_app
import logging

def create_response(data=None, message=None, status_code=200):
    response = {
        'status': 'success' if status_code < 400 else 'error',
        'message': message,
        'data': data
    }
    return jsonify(response), status_code

def handle_error(exception, status_code=500):
    error_handling_config = current_app.config.get('ERROR_HANDLING', {})
    if error_handling_config.get('log_errors', True):
        logging.error(f"Error occurred: {str(exception)}")

    response = {
        "status": "error",
        "message": str(exception) if error_handling_config.get('show_stack_traces', False) else "An internal error occurred."
    }
    return jsonify(response), status_code
