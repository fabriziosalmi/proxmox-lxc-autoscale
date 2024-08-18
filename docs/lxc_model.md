# LXC AutoScale ML

The service can be customized through various parameters, including spike detection sensitivity and the size of scaling steps.

## Features

- **Anomaly Detection**: Uses an Isolation Forest model to detect abnormal resource usage patterns.
- **Automated Scaling**: Automatically adjusts CPU cores and RAM for LXC containers based on current usage and predefined thresholds.
- **Customizable Parameters**: Allows customization of model parameters, scaling thresholds, and operational settings.
- **Logging and Monitoring**: Provides detailed logs of operations and scaling decisions, with a JSON log for easy analysis.

## Installation and Setup

### 1. Prerequisites

- **Python 3.7+**: Ensure Python is installed on your system.
- **LXC**: LXC (Linux Containers) must be installed and configured on your server.
- **Required Python Packages**: Install the necessary Python packages using `pip`:
  ```bash
  pip install pandas numpy scikit-learn joblib requests gunicorn
  ```
  or, on Proxmox hosts:
  ```
  apt install git python3-flask python3-requests python3-gunicorn -y
  ```

### 2. Configuration

Create the configuration file at `/etc/lxc_autoscale/lxc_autoscale_ml.yaml` with the following content:

```yaml
# Configuration options for the LXC AutoScale ML service
model_save_path: "scaling_model.pkl"
data_file: "/var/log/lxc_metrics.json"
log_file: "/var/log/lxc_autoscale_ml.log"
json_log_file: "/var/log/lxc_autoscale_suggestions.json"
```

### 3. Service Configuration

Create a systemd service file at `/etc/systemd/system/lxc_autoscale_ml.service`:

```ini
[Unit]
Description=LXC AutoScale ML Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/lxc_autoscale_ml.py
WorkingDirectory=/usr/local/bin/
StandardOutput=inherit
StandardError=inherit
Restart=on-failure
User=root

# Logging configuration
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/etc/lxc_autoscale/lxc_autoscale_ml.yaml

[Install]
WantedBy=multi-user.target
```

### 4. Installation

1. **Place the Python script** (`lxc_autoscale_ml.py`) in `/usr/local/bin/`.
2. **Reload systemd** to recognize the new service:
   ```bash
   sudo systemctl daemon-reload
   ```
3. **Enable and start the service**:
   ```bash
   sudo systemctl enable lxc_autoscale_ml.service
   sudo systemctl start lxc_autoscale_ml.service
   ```

## Usage

### Command-Line Arguments

The script can be configured via command-line arguments for custom operation. Below are the key arguments:

- **--force-save**: Force save the model regardless of performance.
- **--verbosity [0, 1, 2]**: Set the verbosity level (0 = minimal, 1 = normal, 2 = verbose).
- **--ram-chunk-size**: Set the minimal RAM scaling chunk size (in MB).
- **--ram-upper-limit**: Set the maximum RAM scaling limit in one step (in MB).
- **--smoothing-factor**: Set the smoothing factor to balance scaling decisions.
- **--spike-threshold**: Set the sensitivity for spike detection (in standard deviations).
- **--dry-run**: Perform a dry run without making actual API calls (useful for testing).
- **--contamination**: Set the contamination parameter for the Isolation Forest model (default: 0.05).
- **--n_estimators**: Set the number of base estimators in the Isolation Forest model (default: 100).
- **--max_samples**: Set the number of samples to draw from X to train each base estimator (default: 256).
- **--random_state**: Set the seed used by the random number generator (default: 42).

### Starting the Service

The LXC AutoScale ML Service starts automatically after installation. You can also manage it manually using systemd:

- **Start the service**: `sudo systemctl start lxc_autoscale_ml.service`
- **Stop the service**: `sudo systemctl stop lxc_autoscale_ml.service`
- **Restart the service**: `sudo systemctl restart lxc_autoscale_ml.service`
- **Check the service status**: `sudo systemctl status lxc_autoscale_ml.service`

### Logging and Outputs

- **Logs**: The service logs its operations in `/var/log/lxc_autoscale_ml.log`. It provides detailed information about the model training, scaling decisions, and any encountered errors.
- **Scaling Suggestions**: Suggestions for scaling actions are logged in JSON format at `/var/log/lxc_autoscale_suggestions.json`.

## Core Functions

- `load_data(file_path)`

Loads the container metrics data from a JSON file and preprocesses it into a Pandas DataFrame for further analysis.

- `feature_engineering(df, spike_threshold)`

Performs feature engineering, including calculating rolling means and standard deviations, and detecting spikes in resource usage.

- `train_anomaly_model(X_train)`

Trains an Isolation Forest model to detect anomalies in the data. The model is used to predict when scaling actions may be needed.

- `save_best_model(model)`

Saves the trained machine learning model to a file for future use.

- `predict_scaling(model, X, container_id)`

Predicts whether scaling is needed for a specific container based on the trained model.

- `suggest_scaling(cpu_usage, memory_usage, target_cpu, target_memory, ram_chunk_size, ram_upper_limit, smoothing_factor, ml_prediction)`

Generates scaling suggestions (up/down) for CPU and RAM based on the container's current resource usage and the machine learning model's predictions.

- `log_scaling_suggestion(lxc_id, cpu_amount, cpu_action, ram_amount, ram_action)`

Logs the scaling suggestion to the JSON log file to keep a history of scaling decisions.

- `apply_scaling(lxc_id, cpu_action, cpu_amount, ram_action, ram_amount)`

Executes the scaling actions by making API calls to adjust the container's CPU cores and RAM.

## Error Handling

The service includes robust error handling, with logs providing detailed information about any issues encountered during data loading, model training, and scaling actions. If an error occurs, the service will attempt to continue operation and log the error for further analysis.
