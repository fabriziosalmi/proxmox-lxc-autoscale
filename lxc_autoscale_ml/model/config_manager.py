import yaml
import logging
import os

class ConfigError(Exception):
    pass

def load_config(config_path, default_config=None):
    if not os.path.exists(config_path):
        logging.error(f"Configuration file not found: {config_path}")
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            logging.info(f"Configuration loaded from {config_path}")
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file: {e}")
        raise ConfigError(f"Error parsing YAML file: {e}")
    except Exception as e:
        logging.error(f"Unexpected error loading configuration: {e}")
        raise ConfigError(f"Unexpected error loading configuration: {e}")

    if default_config:
        config = {**default_config, **config}
        logging.debug(f"Configuration merged with default values.")

    required_keys = ['log_file', 'interval_seconds', 'api']
    for key in required_keys:
        if key not in config:
            logging.error(f"Missing required configuration key: {key}")
            raise ConfigError(f"Missing required configuration key: {key}")

    if 'api_url' not in config['api']:
        logging.error("Missing required configuration key: api_url")
        raise ConfigError("Missing required configuration key: api_url")

    logging.debug(f"Final configuration: {config}")
    return config
