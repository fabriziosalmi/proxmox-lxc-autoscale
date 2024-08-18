import json
import pandas as pd
import numpy as np
import os
import argparse
from datetime import datetime
import requests
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from joblib import dump, load
import logging

# Constants
TOTAL_CORES = 48  # Total number of CPU cores available on the server
TOTAL_RAM_MB = 128000  # Total RAM available on the server in MB (e.g., 128 GB)
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
parser.add_argument('--max_samples', type=int, default=256, help="The number of samples to draw from X to train each base estimator.")
parser.add_argument('--random_state', type=int, default=42, help="The seed used by the random number generator.")

args = parser.parse_args()

def load_data(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        logging.info("Data loaded successfully from lxc_metrics.json")
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
                continue
            record = {
                "container_id": container_id,
                "timestamp": metrics["timestamp"],
                "cpu_usage_percent": metrics["cpu_usage_percent"],
                "memory_usage_mb": metrics["memory_usage_mb"],
                "swap_usage_mb": metrics["swap_usage_mb"],
                "process_count": metrics["process_count"]
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

    df['rolling_mean_cpu'] = df.groupby('container_id')['cpu_usage_percent'].transform(lambda x: x.rolling(window=5, min_periods=1).mean())
    df['rolling_std_cpu'] = df.groupby('container_id')['cpu_usage_percent'].transform(lambda x: x.rolling(window=5, min_periods=1).std()).fillna(0)
    df['rolling_mean_memory'] = df.groupby('container_id')['memory_usage_mb'].transform(lambda x: x.rolling(window=5, min_periods=1).mean())
    df['rolling_std_memory'] = df.groupby('container_id')['memory_usage_mb'].transform(lambda x: x.rolling(window=5, min_periods=1).std()).fillna(0)

    df['cpu_spike'] = np.abs(df['cpu_usage_percent'] - df['rolling_mean_cpu']) > (spike_threshold * df['rolling_std_cpu'])
    df['memory_spike'] = np.abs(df['memory_usage_mb'] - df['rolling_mean_memory']) > (spike_threshold * df['rolling_std_memory'])

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
    cpu_amount = 0
    ram_amount = 0
    final_cpu_action = "No Scaling"
    final_ram_action = "No Scaling"

    # Calculate the number of cores needed to keep CPU usage under the target load
    current_cores = TOTAL_CORES * (cpu_usage / 100)  # Estimate current cores based on usage
    target_cores = current_cores / (TARGET_CPU_LOAD_PERCENT / 100)
    additional_cores = max(0, int(np.ceil(target_cores - current_cores)))

    # Ensure we don't exceed the total available cores
    if cpu_usage > CPU_SCALE_UP_THRESHOLD and additional_cores > 0:
        cpu_amount = min(additional_cores, TOTAL_CORES)
        final_cpu_action = "Scale Up"
    elif cpu_usage < CPU_SCALE_DOWN_THRESHOLD:
        cpu_amount = max(min_cpu_cores, int(np.floor(current_cores - target_cores)))
        final_cpu_action = "Scale Down"

    # Calculate RAM scaling suggestion
    if memory_usage > RAM_SCALE_UP_THRESHOLD:
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

def apply_scaling(lxc_id, cpu_action, cpu_amount, ram_action, ram_amount):
    if cpu_action in ["Scale Up", "Scale Down"]:
        # Make API call to adjust CPU cores
        try:
            response = requests.post("http://127.0.0.1:5000/scale/cores", json={"vm_id": lxc_id, "cores": cpu_amount})
            response.raise_for_status()
            logging.info(f"Successfully scaled CPU for LXC ID {lxc_id} to {cpu_amount} cores.")
        except requests.RequestException as e:
            logging.error(f"Failed to scale CPU for LXC ID {lxc_id}: {e}")
    
    if ram_action in ["Scale Up", "Scale Down"]:
        # Make API call to adjust RAM
        try:
            response = requests.post("http://127.0.0.1:5000/scale/ram", json={"vm_id": lxc_id, "memory": ram_amount})
            response.raise_for_status()
            logging.info(f"Successfully scaled RAM for LXC ID {lxc_id} to {ram_amount} MB.")
        except requests.RequestException as e:
            logging.error(f"Failed to scale RAM for LXC ID {lxc_id}: {e}")

def main():
    logging.info("Starting the scaling prediction script...")

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

    # Write JSON log at the end of processing
    with open(JSON_LOG_FILE, 'w') as json_log_file, open(JSON_LOG_FILE, 'w') as json_log_file:
        json.dump(scaling_suggestions, json_log_file, indent=4)

if __name__ == "__main__":
    main()
