#!/usr/bin/env python3

import json
import pandas as pd
import numpy as np
import os
import argparse
from datetime import datetime
import time
import requests
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from joblib import dump, load
import logging
import signal  # For handling termination signals
import sys  # For exiting the script

# Constants
TOTAL_CORES = 4  # Total number of CPU cores available on the server
TOTAL_RAM_MB = 16384  # Total RAM available on the server in MB (e.g., 128 GB)
TARGET_CPU_LOAD_PERCENT = 50  # Target CPU load percentage after scaling
DEFAULT_RAM_CHUNK_SIZE = 50
DEFAULT_RAM_UPPER_LIMIT = 1024
MIN_CPU_CORES = 2  # Minimum CPU cores to maintain
MIN_RAM_MB = 1024  # Minimum RAM in MB to maintain
CPU_SCALE_UP_THRESHOLD = 75  # CPU usage percentage to trigger scale-up
CPU_SCALE_DOWN_THRESHOLD = 30  # CPU usage percentage to trigger scale-down
RAM_SCALE_UP_THRESHOLD = 75  # RAM usage percentage to trigger scale-up
RAM_SCALE_DOWN_THRESHOLD = 30  # RAM usage percentage to trigger scale-down
MODEL_SAVE_PATH = "scaling_model.pkl"
DATA_FILE = "/var/log/lxc_metrics.json"
LOG_FILE = "/var/log/lxc_autoscale_ml.log"
JSON_LOG_FILE = "/var/log/lxc_autoscale_suggestions.json"
LOCK_FILE = "/tmp/lxc_autoscale_ml.lock"  # Lock file path

# Interval between script runs in seconds
INTERVAL_SECONDS = 60  # Adjust this to your desired interval (e.g., 300 seconds = 5 minutes)

# Initialize Logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Initialize JSON log
scaling_suggestions = []

# Load existing JSON log
if os.path.exists(JSON_LOG_FILE):
    with open(JSON_LOG_FILE, 'r') as json_log_file:
        scaling_suggestions = json.load(json_log_file)

# Define CLI Arguments
parser = argparse.ArgumentParser(description="LXC Auto-Scaling ML Script")
parser.add_argument('--force-save', action='store_true', help="Force save the model regardless of performance")
parser.add_argument('--verbosity', type=int, choices=[0, 1, 2], default=1, help="Set the verbosity level (0 = minimal, 1 = normal, 2 = verbose)")
parser.add_argument('--ram-chunk-size', type=int, default=DEFAULT_RAM_CHUNK_SIZE, help="Set the minimal RAM scaling chunk size (in MB)")
parser.add_argument('--ram-upper-limit', type=int, default=DEFAULT_RAM_UPPER_LIMIT, help="Set the maximum RAM scaling limit in one step (in MB)")
parser.add_argument('--smoothing-factor', type=float, default=0.1, help="Set the smoothing factor to balance scaling")
parser.add_argument('--spike-threshold', type=float, default=2, help="Set the sensitivity for spike detection (in standard deviations)")
parser.add_argument('--dry-run', action='store_true', help="If true, perform a dry run without making actual API calls.")

# Customizable Isolation Forest Parameters
parser.add_argument('--contamination', type=float, default='0.05', help="The amount of contamination of the data set, i.e., the proportion of outliers in the data set.")
parser.add_argument('--n_estimators', type=int, default=100, help="The number of base estimators in the ensemble.")
parser.add_argument('--max_samples', type=int, default=64, help="The number of samples to draw from X to train each base estimator.")
parser.add_argument('--random_state', type=int, default=42, help="The seed used by the random number generator.")

args = parser.parse_args()

def create_lock_file(lock_file):
    """Create a lock file to prevent multiple instances."""
    if os.path.exists(lock_file):
        logging.error("Another instance of the script is already running. Exiting.")
        sys.exit(1)
    else:
        with open(lock_file, 'w') as lf:
            lf.write(str(os.getpid()))
        logging.info(f"Lock file created at {lock_file}.")

def remove_lock_file(lock_file):
    """Remove the lock file upon script completion or termination."""
    if os.path.exists(lock_file):
        os.remove(lock_file)
        logging.info(f"Lock file {lock_file} removed.")
    else:
        logging.warning(f"Lock file {lock_file} was not found.")

def signal_handler(signum, frame):
    """Handle termination signals to ensure the lock file is removed."""
    logging.info(f"Received signal {signum}. Exiting gracefully.")
    remove_lock_file(LOCK_FILE)
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def load_data(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        logging.info("Data loaded successfully from the metrics file.")
    except FileNotFoundError:
        logging.error(f"Error: File {file_path} not found.")
        return None
    except json.JSONDecodeError:
        logging.error(f"Error: Failed to decode JSON from {file_path}.")
        return None

    records = []
    for snapshot in data:
        for container_id, metrics in snapshot.items():
            if container_id == "summary":
                continue  # Skip the summary, focus on container data

            record = {
                "container_id": container_id,
                "timestamp": metrics["timestamp"],
                "cpu_usage_percent": metrics["cpu_usage_percent"],
                "memory_usage_mb": metrics["memory_usage_mb"],
                "swap_usage_mb": metrics.get("swap_usage_mb", 0),
                "swap_total_mb": metrics.get("swap_total_mb", 0),
                "process_count": metrics["process_count"],
                "io_reads": metrics["io_stats"]["reads"],
                "io_writes": metrics["io_stats"]["writes"],
                "network_rx_bytes": metrics["network_usage"]["rx_bytes"],
                "network_tx_bytes": metrics["network_usage"]["tx_bytes"],
                "filesystem_usage_gb": metrics["filesystem_usage_gb"],
                "filesystem_total_gb": metrics["filesystem_total_gb"],
                "filesystem_free_gb": metrics["filesystem_free_gb"],
            }
            records.append(record)

    df = pd.DataFrame(records)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    logging.info("Data preprocessed successfully.")
    return df


def feature_engineering(df, spike_threshold):
    df['cpu_per_process'] = df['cpu_usage_percent'] / df['process_count']
    df['memory_per_process'] = df['memory_usage_mb'] / df['process_count']
    df['time_diff'] = df.groupby('container_id')['timestamp'].diff().dt.total_seconds().fillna(0)

    # Rolling statistics for spike detection
    df['rolling_mean_cpu'] = df.groupby('container_id')['cpu_usage_percent'].transform(lambda x: x.rolling(window=5, min_periods=1).mean())
    df['rolling_std_cpu'] = df.groupby('container_id')['cpu_usage_percent'].transform(lambda x: x.rolling(window=5, min_periods=1).std()).fillna(0)
    df['rolling_mean_memory'] = df.groupby('container_id')['memory_usage_mb'].transform(lambda x: x.rolling(window=5, min_periods=1).mean())
    df['rolling_std_memory'] = df.groupby('container_id')['memory_usage_mb'].transform(lambda x: x.rolling(window=5, min_periods=1).std()).fillna(0)

    # Spike detection
    df['cpu_spike'] = np.abs(df['cpu_usage_percent'] - df['rolling_mean_cpu']) > (spike_threshold * df['rolling_std_cpu'])
    df['memory_spike'] = np.abs(df['memory_usage_mb'] - df['rolling_mean_memory']) > (spike_threshold * df['rolling_std_memory'])

    # Add more features based on other metrics
    df['io_activity'] = df['io_reads'] + df['io_writes']
    df['network_activity'] = df['network_rx_bytes'] + df['network_tx_bytes']

    logging.info("Feature engineering and spike detection completed.")
    return df



def train_anomaly_model(X_train):
    try:
        model = IsolationForest(
            contamination=args.contamination,
            n_estimators=args.n_estimators,
            max_samples=args.max_samples,
            random_state=args.random_state
        )
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('isolation_forest', model)
        ])

        pipeline.fit(X_train.values)  # Use .values to convert DataFrame to array
        logging.info("Anomaly detection model training completed.")

        # Return the model and training scores
        return pipeline, model.decision_function(X_train.values)
    except Exception as e:
        logging.error(f"Error during model training: {e}")
        return None, None

def save_best_model(model):
    try:
        dump(model, MODEL_SAVE_PATH)
        logging.info(f"Anomaly detection model saved to {MODEL_SAVE_PATH}.")
    except Exception as e:
        logging.error(f"Error saving model: {e}")

def predict_scaling(model, X, container_id):
    try:
        prediction = model.named_steps['isolation_forest'].predict(X.values)  # Use .values to convert DataFrame to array
        if prediction[0] == -1:
            return 1, container_id  # Anomaly detected: Scaling likely needed
        else:
            return 0, container_id  # No scaling needed
    except Exception as e:
        logging.error(f"Error during prediction for container {container_id}: {e}")
        return None, container_id


def suggest_scaling(cpu_usage, memory_usage, target_cpu, target_memory, ram_chunk_size, ram_upper_limit, smoothing_factor, ml_prediction, min_cpu_cores=MIN_CPU_CORES, min_ram_mb=MIN_RAM_MB):
    # Initialize scaling suggestion variables
    cpu_amount = max(cpu_usage / 100 * TOTAL_CORES, min_cpu_cores)  # Ensure at least min_cpu_cores are maintained
    ram_amount = max(memory_usage, min_ram_mb)  # Ensure at least min_ram_mb is maintained
    final_cpu_action = "No Scaling"
    final_ram_action = "No Scaling"

    # Determine if CPU scaling is needed
    if cpu_amount < min_cpu_cores:
        cpu_amount = min_cpu_cores
        final_cpu_action = "Scale Up"
    elif cpu_usage > CPU_SCALE_UP_THRESHOLD:
        target_cores = TOTAL_CORES * (TARGET_CPU_LOAD_PERCENT / 100)
        cpu_amount = max(target_cores, min_cpu_cores)
        final_cpu_action = "Scale Up"
    elif cpu_usage < CPU_SCALE_DOWN_THRESHOLD:
        target_cores = TOTAL_CORES * (TARGET_CPU_LOAD_PERCENT / 100)
        cpu_amount = max(min_cpu_cores, int(np.floor(target_cores)))
        final_cpu_action = "Scale Down"

    # Determine if RAM scaling is needed
    if memory_usage < min_ram_mb:
        ram_amount = min_ram_mb
        final_ram_action = "Scale Up"
    elif memory_usage > RAM_SCALE_UP_THRESHOLD:
        ram_amount = min(TOTAL_RAM_MB, max(ram_chunk_size, int(np.ceil(memory_usage - target_memory))))
        final_ram_action = "Scale Up"
    elif memory_usage < RAM_SCALE_DOWN_THRESHOLD:
        ram_amount = max(min_ram_mb, int(np.floor(target_memory - memory_usage)))
        final_ram_action = "Scale Down"

    # Adjust decisions based on machine learning prediction
    if ml_prediction == 1:  # Anomaly detected
        if final_cpu_action == "No Scaling":
            final_cpu_action = "Scale Up"
        if final_ram_action == "No Scaling":
            final_ram_action = "Scale Up"

    return final_cpu_action, min(cpu_amount, TOTAL_CORES), final_ram_action, min(ram_amount, TOTAL_RAM_MB)



def log_scaling_suggestion(lxc_id, cpu_amount, cpu_action, ram_amount, ram_action):
    suggestion = {
        "timestamp": datetime.now().isoformat(),
        "lxc_id": lxc_id,
        "cpu_action": cpu_action,
        "cpu_amount": cpu_amount,
        "ram_action": ram_action,
        "ram_amount": ram_amount
    }

    # Log the scaling suggestion
    logging.info(f"Logging scaling suggestion for LXC ID {lxc_id}: CPU - {cpu_action} to {cpu_amount} core(s), RAM - {ram_action} to {ram_amount} MB.")

    # Avoid duplicates by checking if a similar suggestion already exists
    if not any(
        s.get("lxc_id") == suggestion["lxc_id"] and
        s.get("cpu_action") == suggestion["cpu_action"] and
        s.get("cpu_amount") == suggestion["cpu_amount"] and
        s.get("ram_action") == suggestion["ram_action"] and
        s.get("ram_amount") == suggestion["ram_amount"]
        for s in scaling_suggestions
    ):
        scaling_suggestions.append(suggestion)
        logging.info(f"Scaling suggestion added for LXC ID {lxc_id}.")
    else:
        logging.info(f"Duplicate scaling suggestion detected for LXC ID {lxc_id}; suggestion not added.")


def apply_scaling(lxc_id, cpu_action, cpu_amount, ram_action, ram_amount, max_retries=3, retry_delay=2):
    def perform_request(url, data, resource_type, lxc_id):
        resource_key = "cores" if resource_type == "CPU" else "memory"
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=data)
                response.raise_for_status()
                logging.info(f"Successfully scaled {resource_type} for LXC ID {lxc_id} to {data[resource_key]} {resource_type} units.")
                return True
            except requests.RequestException as e:
                logging.error(f"Attempt {attempt + 1} failed to scale {resource_type} for LXC ID {lxc_id}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Scaling {resource_type} for LXC ID {lxc_id} failed after {max_retries} attempts.")
                    return False

    # Apply CPU scaling if necessary
    if cpu_action in ["Scale Up", "Scale Down"]:
        cpu_data = {"vm_id": lxc_id, "cores": cpu_amount}
        cpu_url = "http://127.0.0.1:5000/scale/cores"
        if not perform_request(cpu_url, cpu_data, "CPU", lxc_id):
            logging.error(f"Scaling operation aborted for LXC ID {lxc_id} due to CPU scaling failure.")

    # Apply RAM scaling if necessary
    if ram_action in ["Scale Up", "Scale Down"]:
        ram_data = {"vm_id": lxc_id, "memory": ram_amount}
        ram_url = "http://127.0.0.1:5000/scale/ram"
        if not perform_request(ram_url, ram_data, "RAM", lxc_id):
            logging.error(f"Scaling operation aborted for LXC ID {lxc_id} due to RAM scaling failure.")




def main():
    logging.info("Starting the scaling prediction script...")

    create_lock_file(LOCK_FILE)  # Create a lock file to prevent multiple instances

    try:
        while True:  # Run indefinitely
            df = load_data(DATA_FILE)
            if df is None:
                logging.error("Exiting due to data loading error.")
                return

            df = feature_engineering(df, args.spike_threshold)

            X = df[['cpu_usage_percent', 'memory_usage_mb', 'cpu_per_process', 'memory_per_process', 'time_diff']]

            model, train_scores = train_anomaly_model(X)
            if model:
                save_best_model(model)

                # Evaluate and log the anomaly score distribution
                logging.info(f"Anomaly scores distribution:\n{pd.Series(train_scores).describe()}")

                unique_containers = df['container_id'].unique()
                for container_id in unique_containers:
                    container_data = df[df['container_id'] == container_id]
                    latest_metrics = container_data.iloc[-1:][['cpu_usage_percent', 'memory_usage_mb', 'cpu_per_process', 'memory_per_process', 'time_diff']]
                    scaling_decision, lxc_id = predict_scaling(model, latest_metrics, container_id)
                    if scaling_decision is not None:
                        final_cpu_action, cpu_amount, final_ram_action, ram_amount = suggest_scaling(
                            latest_metrics['cpu_usage_percent'].values[0],
                            latest_metrics['memory_usage_mb'].values[0],
                            CPU_SCALE_UP_THRESHOLD,
                            RAM_SCALE_UP_THRESHOLD,
                            args.ram_chunk_size,
                            args.ram_upper_limit,
                            args.smoothing_factor,
                            scaling_decision
                        )
                        if final_cpu_action != "No Scaling" or final_ram_action != "No Scaling":
                            logging.info(f"Scaling suggestion for LXC ID {lxc_id}: {final_cpu_action} {cpu_amount} CPU core(s), {final_ram_action} {ram_amount} MB RAM")
                            log_scaling_suggestion(lxc_id, cpu_amount, final_cpu_action, ram_amount, final_ram_action)
                            if not args.dry_run:
                                apply_scaling(lxc_id, final_cpu_action, cpu_amount, final_ram_action, ram_amount)
                    else:
                        logging.info(f"No scaling needed for LXC ID {lxc_id}")

            # Write JSON log at the end of each iteration
            with open(JSON_LOG_FILE, 'w') as json_log_file:
                json.dump(scaling_suggestions, json_log_file, indent=4)

            # Wait for the next iteration
            logging.info(f"Sleeping for {INTERVAL_SECONDS} seconds before next run.")
            time.sleep(INTERVAL_SECONDS)
    finally:
        remove_lock_file(LOCK_FILE)  # Ensure the lock file is removed

if __name__ == "__main__":
    main()
