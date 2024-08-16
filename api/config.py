import os
import yaml
from flask import Flask

def load_config(config_file='/etc/autoscaleapi.yaml'):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

def create_app(config=None):
    app = Flask(__name__)

    if config is None:
        config = load_config()

    app.config['LXC_NODE'] = config['lxc']['node']
    app.config['DEFAULT_STORAGE'] = config['lxc']['default_storage']
    app.config['TIMEOUT'] = config['lxc']['timeout_seconds']
    
    # Load the rate limiting configuration
    app.config['RATE_LIMITING'] = config.get('rate_limiting', {})

    # Flask settings
    app.secret_key = os.urandom(24)
    app.config['DEBUG'] = False
    app.config['LOGGING'] = config['logging']
    app.config['ERROR_HANDLING'] = config['error_handling']

    return app

