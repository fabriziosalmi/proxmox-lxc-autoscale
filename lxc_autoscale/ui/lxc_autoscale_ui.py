from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import json
import os

app = Flask(__name__)
socketio = SocketIO(app)

json_log_file_path = '/var/log/lxc_autoscale.json'
log_file_path = '/var/log/lxc_autoscale.log'

@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')

@app.route('/get_scaling_log')
def get_scaling_log():
    """Return the scaling actions log as JSON."""
    if os.path.exists(json_log_file_path):
        with open(json_log_file_path, 'r') as f:
            scaling_logs = [json.loads(line) for line in f if line.strip()]
        return jsonify(scaling_logs)
    return jsonify([])  # Return empty list if the file does not exist

@app.route('/get_full_log')
def get_full_log():
    """Return the full log content as a JSON response."""
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as f:
            full_log = f.read()
        return jsonify({"log": full_log})
    return jsonify({"log": ""})  # Return empty log if file does not exist

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
