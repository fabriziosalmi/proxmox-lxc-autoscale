# LXC AutoScale ML Documentation

**LXC AutoScale ML** is an advanced service that leverages machine learning to intelligently scale LXC containers based on detected anomalies in resource usage patterns. By employing an Isolation Forest model, it identifies unusual spikes in CPU and memory usage and automatically adjusts container resources to maintain optimal performance. The service offers extensive customization options, enabling fine-tuning of scaling behavior to suit specific needs.

## Summary

- **[Overview](#overview)**: Introduction to LXC AutoScale ML and its core functionality.
- **[Features](#features)**: Key features of the service, including anomaly detection and automated scaling.
- **[Installation and Setup](#installation-and-setup)**: Step-by-step guide to installing and configuring LXC AutoScale ML.
  - [Prerequisites](#1-prerequisites)
  - [Configuration](#2-configuration)
  - [Service Configuration](#3-service-configuration)
  - [Installation](#4-installation)
- **[Usage](#usage)**: Instructions on how to start, stop, and manage the LXC AutoScale ML service.
- **[Logging and Outputs](#logging-and-outputs)**: Information on logging and how to interpret the scaling suggestions.
- **[Core Functions](#core-functions)**: Detailed descriptions of the key functions used in the LXC AutoScale ML service.
- **[Error Handling](#error-handling)**: Explanation of the error handling mechanisms implemented in the service.
- **[Best Practices and Tips](#best-practices-and-tips)**: Recommendations for optimizing the performance and reliability of LXC AutoScale ML.

---

## Overview

**LXC AutoScale ML** is designed to provide automated scaling for LXC containers using machine learning techniques. The service detects anomalies in resource usage, such as unexpected spikes in CPU or memory consumption, and automatically adjusts the container’s resources to mitigate performance issues. By integrating an Isolation Forest model, LXC AutoScale ML can differentiate between normal and abnormal usage patterns, allowing for more intelligent and responsive scaling decisions.

---

## Features

LXC AutoScale ML offers a suite of powerful features designed to enhance the management and performance of LXC containers:

- **Anomaly Detection**: Uses an Isolation Forest model to detect abnormal resource usage patterns, identifying when a container's resource consumption deviates significantly from the norm.
- **Automated Scaling**: Automatically adjusts CPU cores and RAM allocations based on current usage, predefined thresholds, and the machine learning model’s predictions, ensuring containers always have the right amount of resources.
- **Customizable Parameters**: Allows for extensive customization of model parameters, scaling thresholds, and operational settings, enabling you to tailor the service to your specific environment.
- **Logging and Monitoring**: Provides detailed logs of operations and scaling decisions, with JSON logs that are easy to parse and analyze, facilitating in-depth monitoring and review.

---

## Installation and Setup

Setting up LXC AutoScale ML involves ensuring your system meets the prerequisites, configuring the service, and installing it. Below is a detailed guide to help you get started.

### 1. Prerequisites

Before installing LXC AutoScale ML, make sure your system meets the following requirements:

- **Python 3.7+**: Ensure that Python is installed on your system. You can check the installed version with:
  ```bash
  python3 --version
  ```
- **LXC**: LXC (Linux Containers) must be installed and properly configured on your server. Ensure that your containers are running and accessible.
- **Required Python Packages**: Install the necessary Python packages using `pip` or the package manager on Proxmox hosts:
  ```bash
  pip install pandas numpy scikit-learn joblib requests gunicorn
  ```
  Or, on Proxmox hosts:
  ```bash
  apt install git python3-flask python3-requests python3-gunicorn -y
  ```

### 2. Configuration

Create the main configuration file at `/etc/lxc_autoscale/lxc_autoscale_ml.yaml`. This file will define key parameters for the service, including paths for logs, model storage, and metrics data.

#### Example Configuration:

```yaml
# Configuration options for the LXC AutoScale ML service
model_save_path: "scaling_model.pkl"
data_file: "/var/log/lxc_metrics.json"
log_file: "/var/log/lxc_autoscale_ml.log"
json_log_file: "/var/log/lxc_autoscale_suggestions.json"
```

#### Explanation of Configuration Options:

- **model_save_path**: Path where the trained machine learning model is saved. This file will be used for future scaling predictions.
- **data_file**: Path to the JSON file containing container metrics data. This file is crucial for training the model and making predictions.
- **log_file**: Path to the log file where the service logs its operations, including model training and scaling actions.
- **json_log_file**: Path to the JSON log file where scaling suggestions are recorded. This file allows for easy analysis of the decisions made by the service.

### 3. Service Configuration

To run LXC AutoScale ML as a systemd service, you'll need to create a service configuration file. This file instructs systemd on how to manage the LXC AutoScale ML service.

#### Example Service Configuration:

Create the file `/etc/systemd/system/lxc_autoscale_ml.service` with the following content:

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

- **ExecStart**: Specifies the command to start the service, pointing to the Python script that runs LXC AutoScale ML.
- **WorkingDirectory**: Sets the working directory for the service.
- **StandardOutput** and **StandardError**: Ensure that output and errors are properly handled by systemd.
- **Restart**: Configures the service to automatically restart if it encounters a failure.
- **EnvironmentFile**: Points to the configuration file for environment variables.

### 4. Installation

To install LXC AutoScale ML, follow these steps:

1. **Place the Python Script**: Move the `lxc_autoscale_ml.py` script to `/usr/local/bin/`:
   ```bash
   sudo cp lxc_autoscale_ml.py /usr/local/bin/
   ```

2. **Reload systemd**: Reload systemd to recognize the new service:
   ```bash
   sudo systemctl daemon-reload
   ```

3. **Enable and Start the Service**: Enable the service to start at boot and start it immediately:
   ```bash
   sudo systemctl enable lxc_autoscale_ml.service
   sudo systemctl start lxc_autoscale_ml.service
   ```

This completes the installation process, and the service should now be running, monitoring your LXC containers and making scaling decisions based on real-time data.

---

## Usage

LXC AutoScale ML offers flexibility in how it operates, with various command-line arguments available to customize its behavior.

### Command-Line Arguments

The service can be run with several command-line arguments, allowing you to adjust its operation without modifying the configuration file:

- **--force-save**: Forces the model to save regardless of its performance during training.
- **--verbosity [0, 1, 2]**: Sets the verbosity level of the output. Use `0` for minimal output, `1` for standard output, and `2` for detailed output.
- **--ram-chunk-size**: Defines the minimum amount of RAM (in MB) to adjust during a scaling operation.
- **--ram-upper-limit**: Sets the maximum amount of RAM (in MB) that can be added or removed in a single scaling step.
- **--smoothing-factor**: Adjusts the smoothing factor, which helps balance aggressive scaling actions and more gradual adjustments.
- **--spike-threshold**: Sets the sensitivity for spike detection in standard deviations. A lower value makes the service more sensitive to changes in resource usage.
- **--dry-run**: Performs a trial run without making any actual API calls. This is useful for testing configuration changes without affecting the running containers.
- **--contamination**: Sets the contamination parameter for the Isolation Forest model, which determines the proportion of outliers in the data.
- **--n_estimators**: Defines the number of trees in the Isolation Forest model. More trees can improve model accuracy but increase training time.
- **--max_samples**: Specifies the number of samples to draw from the dataset to train each base estimator. This controls the balance between model performance and computational efficiency.
- **--random_state**: Sets the seed for the random number generator, ensuring reproducible results when training the model.

### Starting the Service

Once installed, the LXC AutoScale ML service should start automatically. However, you can manage the service manually using the following commands:

- **Start the service**:
  ```bash
  sudo systemctl start lxc_autoscale_ml.service
  ```

- **Stop the service**:
  ```bash
  sudo systemctl stop lxc_autoscale_ml.service
  ```

- **Restart the service**:
  ```bash
  sudo systemctl restart lxc_autoscale_ml.service
  ```

- **Check the service status

**:
  ```bash
  sudo systemctl status lxc_autoscale_ml.service
  ```

These commands allow you to control the service, ensuring it is running smoothly and making scaling decisions as expected.

---

## Logging and Outputs

LXC AutoScale ML provides detailed logs and outputs to help you monitor its operation and scaling decisions.

### Logs

- **Log File**: `/var/log/lxc_autoscale_ml.log`
- **Log Content**: The log file contains detailed information about the service’s operation, including model training, predictions, and scaling actions. This log is essential for troubleshooting and understanding how the service is making decisions.

### Scaling Suggestions

- **JSON Log File**: `/var/log/lxc_autoscale_suggestions.json`
- **Log Content**: This JSON file records the scaling suggestions made by the service, including the predicted need for scaling and the suggested actions. The format is easily parsable for further analysis or integration with other monitoring tools.

Example JSON entry:

```json
{
  "timestamp": "2024-08-14T22:04:45Z",
  "container_id": "101",
  "cpu_action": "increase",
  "cpu_amount": 1,
  "ram_action": "increase",
  "ram_amount": 512,
  "reason": "Anomaly detected in CPU and memory usage"
}
```

This example shows a suggested action to increase CPU and RAM for a specific container due to detected anomalies.

---

## Core Functions

LXC AutoScale ML uses a set of core functions to process data, train the model, and make scaling decisions. Below is a detailed explanation of each key function:

- **`load_data(file_path)`**: Loads container metrics data from a JSON file and preprocesses it into a Pandas DataFrame. This data is essential for training the machine learning model and making predictions.

- **`feature_engineering(df, spike_threshold)`**: Performs feature engineering on the data, including calculating rolling means and standard deviations. It also detects spikes in resource usage based on the defined spike threshold, helping the model to identify anomalies.

- **`train_anomaly_model(X_train)`**: Trains an Isolation Forest model using the preprocessed data. This model is used to detect anomalies in resource usage, guiding scaling decisions.

- **`save_best_model(model)`**: Saves the trained machine learning model to a file. This allows the model to be reused for future predictions without retraining.

- **`predict_scaling(model, X, container_id)`**: Predicts whether scaling is needed for a specific container based on the current data and the trained model’s output. This function is central to the service’s ability to make intelligent scaling decisions.

- **`suggest_scaling(cpu_usage, memory_usage, target_cpu, target_memory, ram_chunk_size, ram_upper_limit, smoothing_factor, ml_prediction)`**: Generates scaling suggestions based on current resource usage, target allocations, and machine learning predictions. It determines whether to increase or decrease CPU and RAM and by how much.

- **`log_scaling_suggestion(lxc_id, cpu_amount, cpu_action, ram_amount, ram_action)`**: Logs the scaling suggestion to the JSON log file, providing a record of the decisions made by the service.

- **`apply_scaling(lxc_id, cpu_action, cpu_amount, ram_action, ram_amount)`**: Executes the scaling actions by making API calls to adjust the container’s CPU cores and RAM. This function applies the changes suggested by the model and recorded in the logs.

---

## Error Handling

LXC AutoScale ML is designed with robust error handling to ensure continuous operation even when issues arise. The service logs any encountered errors, providing detailed information for troubleshooting. If a problem occurs during data loading, model training, or scaling actions, the service will attempt to continue running while logging the error for later review.

### Example:

If an error occurs while loading data, the service will log the issue but will continue to monitor other containers. This approach ensures that a single failure does not disrupt the entire service.

---

## Best Practices and Tips

### 1. Regularly Review Logs
Reviewing logs regularly is crucial for understanding how LXC AutoScale ML is performing and identifying any potential issues. The logs provide insights into the decisions made by the service, allowing you to fine-tune its behavior.

### 2. Fine-Tune the Model Parameters
Adjusting the Isolation Forest model parameters, such as `contamination`, `n_estimators`, and `max_samples`, can significantly impact the model’s performance. Experiment with different settings to find the best fit for your environment.

### 3. Use Dry-Run Mode for Testing
When making significant configuration changes, use the `--dry-run` option to test the service without affecting live containers. This allows you to verify that the service behaves as expected before applying changes.

### 4. Balance Smoothing and Responsiveness
The `smoothing-factor` parameter helps balance between quick responses to changes in resource usage and more gradual adjustments. Fine-tuning this parameter ensures that your containers are scaled efficiently without overreacting to temporary spikes.

### 5. Monitor Disk Space for Logs and Model Files
Ensure that the system has sufficient disk space for storing logs and the trained model file. Regularly check the size of these files and consider rotating logs if they grow too large.
