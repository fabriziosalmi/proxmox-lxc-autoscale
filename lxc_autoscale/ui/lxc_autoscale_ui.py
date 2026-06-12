"""LXC AutoScale web UI — read-only dashboard for scaling events and logs.

Optional component. Hardened with:
- JSON parse error handling (no crash on malformed lines)
- Explicit file encoding
- Debug mode removed (never enable Flask debugger in production)
- Log size limit (last 1000 lines max)
- Symlink-safe file reads
- Input sanitization to prevent log injection via control characters
"""

import json
import os
import re

from flask import Flask, jsonify, render_template

app = Flask(__name__)

# Log file paths (same as daemon defaults)
_JSON_LOG = '/var/log/lxc_autoscale.json'
_TEXT_LOG = '/var/log/lxc_autoscale.log'
_MAX_LOG_LINES = 1000

# Regex to strip non-printable control characters (except newline/tab)
_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def _safe_path(path: str, allowed_dir: str = '/var/log') -> str:
    """Resolve symlinks and verify the path stays within allowed_dir.
    
    Explicitly rejects:
    - Relative paths (e.g., '../etc/passwd')
    - Paths containing null bytes
    - Paths resolving outside allowed_dir
    """
    # Reject null bytes in path (prevents null-byte truncation attacks)
    if '\x00' in path:
        raise ValueError(f"Path contains null byte: {repr(path)}")
    
    # Reject relative paths explicitly
    if not os.path.isabs(path):
        raise ValueError(f"Path must be absolute: {path}")
    
    # Resolve symlinks and get canonical path
    real = os.path.realpath(path)
    
    # Ensure resolved path is within allowed_dir
    allowed_real = os.path.realpath(allowed_dir)
    if not real.startswith(allowed_real + os.sep) and real != allowed_real:
        raise ValueError(f"Path escapes allowed directory: {path}")
    
    return real


def _sanitize_log_line(line: str) -> str:
    """Remove non-printable control characters to prevent log injection."""
    return _CONTROL_CHARS_RE.sub('', line)


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
                    event = json.loads(line)
                    # Sanitize string fields in the event to prevent injection
                    if isinstance(event, dict):
                        for key, value in event.items():
                            if isinstance(value, str):
                                event[key] = _sanitize_log_line(value)
                    events.append(event)
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
        # Limit output and sanitize each line to prevent log injection
        tail = [_sanitize_log_line(line) for line in lines[-_MAX_LOG_LINES:]]
        return jsonify({"log": "".join(tail)})
    except (OSError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(
        host=os.environ.get('LXC_AUTOSCALE_UI_HOST', '127.0.0.1'),
        port=int(os.environ.get('LXC_AUTOSCALE_UI_PORT', '5000')),
        debug=False,  # never enable in production
    )
