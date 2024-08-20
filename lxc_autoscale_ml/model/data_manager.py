import pandas as pd
import logging
import json
import numpy as np
from sklearn.preprocessing import StandardScaler

def load_data(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        logging.info(f"Data loaded successfully from {file_path}.")
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"JSON decoding failed: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error loading data: {e}")
        return None

    if not data:
        logging.error(f"No data found in {file_path}.")
        return None

    records = []
    for snapshot in data:
        for container_id, metrics in snapshot.items():
            if container_id == "summary":
                continue  # Skip the summary, focus on container data

            try:
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
            except KeyError as e:
                logging.warning(f"Missing expected metric {e} in container {container_id}. Skipping.")
                continue

    if not records:
        logging.error("No valid records found in the data.")
        return None

    df = pd.DataFrame(records)
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    except Exception as e:
        logging.error(f"Error converting timestamps: {e}")
        return None

    logging.info("Data preprocessed successfully.")
    return df

def preprocess_data(df, config):
    if df.empty:
        logging.error("DataFrame is empty. Skipping preprocessing.")
        return df

    try:
        spike_threshold = config.get('spike_detection', {}).get('spike_threshold', 2)
        rolling_window_size = config.get('rolling_window', 5)
        
        df['cpu_per_process'] = df['cpu_usage_percent'] / df['process_count']
        df['memory_per_process'] = df['memory_usage_mb'] / df['process_count']
        df['time_diff'] = df.groupby('container_id')['timestamp'].diff().dt.total_seconds().fillna(0)

        # Rolling statistics for spike detection and trend analysis
        df['rolling_mean_cpu'] = df.groupby('container_id')['cpu_usage_percent'].transform(
            lambda x: x.rolling(window=rolling_window_size, min_periods=1).mean())
        df['rolling_std_cpu'] = df.groupby('container_id')['cpu_usage_percent'].transform(
            lambda x: x.rolling(window=rolling_window_size, min_periods=1).std()).fillna(0)
        df['rolling_mean_memory'] = df.groupby('container_id')['memory_usage_mb'].transform(
            lambda x: x.rolling(window=rolling_window_size, min_periods=1).mean())
        df['rolling_std_memory'] = df.groupby('container_id')['memory_usage_mb'].transform(
            lambda x: x.rolling(window=rolling_window_size, min_periods=1).std()).fillna(0)

        # Spike detection
        df['cpu_spike'] = np.abs(df['cpu_usage_percent'] - df['rolling_mean_cpu']) > (spike_threshold * df['rolling_std_cpu'])
        df['memory_spike'] = np.abs(df['memory_usage_mb'] - df['rolling_mean_memory']) > (spike_threshold * df['rolling_std_memory'])

        # Trend detection using the slope of the rolling window
        df['cpu_trend'] = df.groupby('container_id')['cpu_usage_percent'].transform(
            lambda x: np.polyfit(np.arange(len(x)), x.rolling(window=rolling_window_size, min_periods=1).mean(), 1)[0])
        df['memory_trend'] = df.groupby('container_id')['memory_usage_mb'].transform(
            lambda x: np.polyfit(np.arange(len(x)), x.rolling(window=rolling_window_size, min_periods=1).mean(), 1)[0])

        # Aggregated features
        df['max_cpu'] = df.groupby('container_id')['cpu_usage_percent'].transform(
            lambda x: x.rolling(window=rolling_window_size, min_periods=1).max())
        df['min_cpu'] = df.groupby('container_id')['cpu_usage_percent'].transform(
            lambda x: x.rolling(window=rolling_window_size, min_periods=1).min())
        df['max_memory'] = df.groupby('container_id')['memory_usage_mb'].transform(
            lambda x: x.rolling(window=rolling_window_size, min_periods=1).max())
        df['min_memory'] = df.groupby('container_id')['memory_usage_mb'].transform(
            lambda x: x.rolling(window=rolling_window_size, min_periods=1).min())

        # Feature scaling
        scaler = StandardScaler()
        features_to_scale = ['cpu_usage_percent', 'memory_usage_mb', 'cpu_per_process', 'memory_per_process', 'time_diff',
                             'cpu_trend', 'memory_trend', 'max_cpu', 'min_cpu', 'max_memory', 'min_memory']
        df[features_to_scale] = scaler.fit_transform(df[features_to_scale])

        logging.info("Feature engineering, spike detection, and trend detection completed.")
    except Exception as e:
        logging.error(f"Error during data preprocessing: {e}")
        return df

    return df
