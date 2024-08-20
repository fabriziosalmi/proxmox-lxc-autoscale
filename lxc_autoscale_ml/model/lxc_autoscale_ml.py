#!/usr/bin/env python3

import sys
import time
import logging
import pandas as pd

# Ensure all modules in the lxc_autoscale_ml directory are accessible
sys.path.append('/usr/local/bin/lxc_autoscale_ml')

# Import custom modules
from logger import setup_logging
from lock_manager import create_lock_file, remove_lock_file
from config_manager import load_config
from data_manager import load_data, preprocess_data
from model import train_anomaly_models, predict_anomalies
from scaling import determine_scaling_action, apply_scaling
from signal_handler import setup_signal_handlers


def main():
    config = load_config("/etc/lxc_autoscale_ml/lxc_autoscale_ml.yaml")
    setup_logging(config.get("log_file", "/var/log/lxc_autoscale_ml.log"))

    logging.info("Starting the LXC auto-scaling script...")

    create_lock_file(config.get("lock_file", "/tmp/lxc_autoscale_ml.lock"))

    try:
        while True:
            # Load and preprocess data
            df = load_data(config.get("data_file", "/var/log/lxc_metrics.json"))
            if df is None:
                logging.error("Exiting due to data loading error.")
                return

            df = preprocess_data(df, config)

            # Train anomaly detection models
            model, features_to_use = train_anomaly_models(df, config)
            if model is None:
                logging.error("Model training failed. Exiting.")
                return

            logging.info("Processing containers for scaling decisions...")

            # Iterate over each container and make scaling decisions
            for container_id in df["container_id"].unique():
                container_data = df[df["container_id"] == container_id]
                latest_metrics = container_data.iloc[-1]

                logging.debug(f"Latest metrics for container {container_id}: {latest_metrics.to_dict()}")

                scaling_decision = predict_anomalies(model, latest_metrics, features_to_use, config)

                if scaling_decision is not None:
                    cpu_action, ram_action, new_cores, new_ram = determine_scaling_action(latest_metrics, scaling_decision, config)
                    logging.debug(f"Scaling decision for container {container_id}: CPU - {cpu_action}, RAM - {ram_action}")

                    if cpu_action != "No Scaling" or ram_action != "No Scaling":
                        logging.info(f"Applying scaling actions for container {container_id}: CPU - {cpu_action}, RAM - {ram_action}")
                        apply_scaling(container_id, new_cores, new_ram, config)
                    else:
                        logging.info(f"No scaling needed for container {container_id}.")
                else:
                    logging.warning(f"Skipping scaling for container {container_id} due to lack of prediction.")

            # Sleep until the next interval
            logging.info(f"Sleeping for {config.get('interval_seconds', 60)} seconds before the next run.")
            time.sleep(config.get("interval_seconds", 60))

    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        remove_lock_file(config.get("lock_file", "/tmp/lxc_autoscale_ml.lock"))
        logging.info("Script execution completed.")

if __name__ == "__main__":
    # Setup signal handlers to ensure graceful shutdown
    setup_signal_handlers()
    main()
