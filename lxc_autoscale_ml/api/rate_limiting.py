from functools import wraps
from flask import request, jsonify, current_app
import time

# Simple in-memory rate limiting for demonstration purposes
rate_limit_data = {}

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        rate_limiting_config = current_app.config['RATE_LIMITING']

        if client_ip not in rate_limit_data:
            rate_limit_data[client_ip] = []

        access_times = rate_limit_data[client_ip]
        current_time = time.time()

        # Filter out access times that are older than one minute
        access_times = [t for t in access_times if current_time - t < 60]
        rate_limit_data[client_ip] = access_times

        if len(access_times) >= rate_limiting_config['max_requests_per_minute']:
            return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429

        access_times.append(current_time)
        return f(*args, **kwargs)
    
    return decorated_function
