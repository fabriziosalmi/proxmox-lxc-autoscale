"""LXC AutoScale web UI — read-only dashboard for scaling events and logs.

Optional component. Hardened with:
- JSON parse error handling (no crash on malformed lines)
- Explicit file encoding
- Debug mode removed (never enable Flask debugger in production)
- Log size limit (last 1000 lines max)
- Symlink-safe file reads
"""

import json
import os

from flask import Flask, jsonify, render_template

app = Flask(__name__)

# Log file paths (same as daemon defaults)
_JSON_LOG = '/var/log/lxc_autoscale.json'
_TEXT_LOG = '/var/log/lxc_autoscale.log'
_MAX_LOG_LINES = 1000


def _safe_path(path: str, allowed_dir: str = '/var/log') -> str:
    """Resolve symlinks and verify the path stays within allowed_dir."""
    real = os.path.realpath(path)
    if not real.startswith(os.path.realpath(allowed_dir) + os.sep):
        raise ValueError(f"Path escapes allowed directory: {path}")
    return real


@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')


@app.route('/get_scaling_log')
def get_scaling_log():
    """Return recent scaling events as JSON (last N entries)."""
    try:
        path = _safe_path(_JSON_LOG)
        if not os.path.exists(path):
            return jsonify([])
        events = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue  # skip malformed lines
        # Return only the last N events to prevent memory issues
        return jsonify(events[-_MAX_LOG_LINES:])
    except (OSError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 500


@app.route('/get_full_log')
def get_full_log():
    """Return the last N lines of the text log."""
    try:
        path = _safe_path(_TEXT_LOG)
        if not os.path.exists(path):
            return jsonify({"log": ""})
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # Limit output to prevent serving multi-MB responses
        tail = lines[-_MAX_LOG_LINES:]
        return jsonify({"log": "".join(tail)})
    except (OSError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(
        host=os.environ.get('LXC_AUTOSCALE_UI_HOST', '127.0.0.1'),
        port=int(os.environ.get('LXC_AUTOSCALE_UI_PORT', '5000')),
        debug=False,  # never enable in production
    )
