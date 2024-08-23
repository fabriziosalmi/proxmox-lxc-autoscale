# LXC AutoScale ML Documentation

**LXC AutoScale ML** is an advanced service that leverages machine learning to intelligently scale LXC containers based on detected anomalies in resource usage patterns. Using an Isolation Forest model, it identifies unusual spikes in CPU and memory usage, and automatically adjusts container resources to maintain optimal performance. The service offers extensive customization options, enabling fine-tuning of scaling behavior to suit specific needs.

## Summary

- **[Overview](#overview)**: Introduction to LXC AutoScale ML and its core functionality.
- **[Features](#features)**: Key features of the service, including anomaly detection and automated scaling.
- **[Quick Start](#quick-start)**: Step-by-step guide to installing and configuring LXC AutoScale ML.
- **[Configuration](#configuration)**: Detailed instructions on configuring LXC AutoScale ML to suit your environment.
- **[Usage](#usage)**: Instructions on how to start, stop, and manage the LXC AutoScale ML service.
- **[Logging and Outputs](#logging-and-outputs)**: Information on logging and interpreting scaling suggestions.
- **[Error Handling](#error-handling)**: Explanation of the error handling mechanisms implemented in the service.
- **[Autoscaling](#autoscaling)**: Explanation of the autoscaling logic and the role of the machine learning model.
- **[Best Practices and Tips](#best-practices-and-tips)**: Recommendations for optimizing the performance and reliability of LXC AutoScale ML.

---

## Overview

**LXC AutoScale ML** is designed to provide automated scaling for LXC containers using machine learning techniques. The service detects anomalies in resource usage, such as unexpected spikes in CPU or memory consumption, and automatically adjusts the container’s resources to mitigate performance issues. By integrating an Isolation Forest model, LXC AutoScale ML can differentiate between normal and abnormal usage patterns, allowing for more intelligent and responsive scaling decisions.

> See LXC AutoScale ML in action:
```bash
2024-08-20 13:07:56,393 [INFO] Data loaded successfully from /var/log/lxc_metrics.json.
2024-08-20 13:07:56,399 [INFO] Data preprocessed successfully.
2024-08-20 13:07:56,416 [INFO] Feature engineering, spike detection, and trend detection completed.
2024-08-20 13:07:56,417 [INFO] Features used for training: ['cpu_memory_ratio', 'cpu_per_process', 'cpu_trend', 'cpu_usage_percent', 'filesystem_free_gb', 'filesystem_total_gb', 'filesystem_usage_gb', 'io_reads', 'io_writes', 'max_cpu', 'max_memory', 'memory_per_process', 'memory_trend', 'memory_usage_mb', 'min_cpu', 'min_memory', 'network_rx_bytes', 'network_tx_bytes', 'process_count', 'rolling_mean_cpu', 'rolling_mean_memory', 'rolling_std_cpu', 'rolling_std_memory', 'swap_total_mb', 'swap_usage_mb', 'time_diff']
2024-08-20 13:07:56,549 [INFO] IsolationForest model training completed.
2024-08-20 13:07:56,549 [INFO] Processing containers for scaling decisions...
2024-08-20 13:07:56,600 [INFO] Applying scaling actions for container 104: CPU - Scale Up, RAM - Scale Up | Confidence: 87.41%
2024-08-20 13:07:57,257 [INFO] Successfully scaled CPU for LXC ID 104 to 4 CPU units.
2024-08-20 13:07:57,916 [INFO] Successfully scaled RAM for LXC ID 104 to 8192 RAM units.
2024-08-20 13:07:57,916 [INFO] Sleeping for 60 seconds before the next run.
```

---

## Features

LXC AutoScale ML offers a suite of powerful features designed to enhance the management and performance of LXC containers:

- **Anomaly Detection**: Utilizes an Isolation Forest model to detect abnormal resource usage patterns, identifying when a container's resource consumption deviates significantly from the norm.
- **Automated Scaling**: Automatically adjusts CPU cores and RAM allocations based on current usage, predefined thresholds, and the machine learning model’s predictions, ensuring containers always have the right amount of resources.
- **Confidence Score**: Includes a confidence score with each scaling suggestion, indicating the certainty of the scaling action. This helps in making informed decisions on whether to proceed with scaling.
- **Customizable Parameters**: Offers extensive customization of model parameters, scaling thresholds, and operational settings, enabling you to tailor the service to your specific environment.
- **Logging and Monitoring**: Provides detailed logs of operations and scaling decisions, with JSON logs that are easy to parse and analyze, facilitating in-depth monitoring and review.

---

## Quick Start

Getting started with LXC AutoScale ML on your Proxmox host is quick and simple:

```bash
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/install.sh | bash
```

Select option 2 and you're done.

---

## Configuration

The `lxc_autoscale_ml.yaml` configuration file allows you to customize various aspects of the LXC AutoScale ML service. Below is an example configuration file with explanations:

```yaml
# Logging Configuration
log_file: "/var/log/lxc_autoscale_ml.log"  # Path to the log file
log_level: "DEBUG"  # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

# Lock File Configuration
lock_file: "/tmp/lxc_autoscale_ml.lock"  # Path to the lock file to prevent multiple instances

# Data File Configuration
data_file: "/var/log/lxc_metrics.json"  # Path to the metrics file containing container data produced by LXC AutoScale API

# Model Configuration
model:
  contamination: 0.05  # Contamination level for IsolationForest (fraction of outliers)
  n_estimators: 100  # Number of trees in IsolationForest
  max_samples: 64  # Number of samples to draw for training each tree
  random_state: 42  # Random seed for reproducibility

# Spike Detection Configuration
spike_detection:
  spike_threshold: 2  # Number of standard deviations for spike detection
  rolling_window: 5  # Window size for rolling mean and standard deviation

# Scaling Configuration
scaling:
  total_cores: 4  # Total number of CPU cores available on the server
  total_ram_mb: 16384  # Total RAM available on the server in MB
  target_cpu_load_percent: 50  # Target CPU load percentage after scaling
  max_cpu_cores: 4  # Maximum number of CPU cores to maintain per container
  max_ram_mb: 8192  # Maximum RAM to maintain per container in MB
  min_cpu_cores: 2  # Minimum number of CPU cores to maintain per container
  min_ram_mb: 1024  # Minimum RAM to maintain per container in MB
  cpu_scale_up_threshold: 75  # CPU usage percentage to trigger scale-up
  cpu_scale_down_threshold: 30  # CPU usage percentage to trigger scale-down
  ram_scale_up_threshold: 75  # RAM usage percentage to trigger scale-up
  ram_scale_down_threshold: 30  # RAM usage percentage to trigger scale-down
  ram_chunk_size: 50  # Minimum RAM scaling chunk size in MB
  ram_upper_limit: 1024  # Maximum RAM scaling limit in one step in MB
  dry_run: false  # If true, perform a dry run without making actual API calls

# API Configuration
api:
  api_url: "http://127.0.0.1:5000"  # Base URL for the API used for scaling actions
  cores_endpoint: "/scale/cores"  # Endpoint for scaling CPU cores
  ram_endpoint: "/scale/ram"  # Endpoint for scaling RAM

# Retry Logic for API Calls
retry_logic:
  max_retries: 3  # Maximum number of retries for API calls
  retry_delay: 2  # Delay between retries in seconds

# Interval Configuration
interval_seconds: 60  # Time interval between consecutive script runs in seconds

# Feature Engineering Configuration
feature_engineering:
  include_io_activity: true  # Include IO activity as a feature in the model
  include_network_activity: true  # Include network activity as a feature in the model

# Prediction Configuration
prediction:
  use_latest_only: true  # If true, use only the latest data point for prediction
  include_rolling_features: true  # Include rolling mean and std features for prediction

# Ignored Containers
ignore_lxc:
  - "101"  # List of container IDs to ignore from scaling
  - "102"
```

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

- **Check the service status**:
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
  "confidence": 87.41,
  "reason": "Anomaly detected in CPU and memory usage"
}
```

This example shows a suggested action to increase CPU and RAM for a specific container due to detected anomalies, along with the confidence score.

---

## Error Handling

LXC AutoScale ML is designed with robust error handling to ensure continuous operation even when issues arise. The service logs any encountered errors, providing detailed information for troubleshooting. If a problem occurs during data loading, model training, or scaling actions, the service will attempt to continue running while logging the error for later review.

### Example:

If an error occurs while loading data, the service will log the issue but will continue to monitor other containers. This approach ensures that a single failure does not disrupt the entire service.

---

## Autoscaling

The autoscaling logic in this application is designed to dynamically adjust the CPU and RAM resources allocated to each container based on real-time metrics and the detection of anomalous behavior. This section is critical for ensuring that containers operate efficiently, without under-provisioning (which could lead to performance issues) or over-provisioning (which would waste resources).

### **Key Components of Autoscaling:**

1. **Metrics Monitoring:**
   - The autoscaling system continuously monitors various performance metrics of each container. These metrics include CPU usage percentage, memory usage in megabytes (MB), and possibly other custom metrics like `cpu_memory_ratio` or `io_ops_per_second`.
   - The metrics data is collected in near real-time and is used both for anomaly detection and for making scaling decisions.

2. **Anomaly Detection Trigger:**
   - The first line of decision-making in the autoscaling logic is anomaly detection. By identifying unusual patterns in container behavior, the system can preemptively scale resources before standard thresholds (like CPU or RAM usage) are breached.
   - If an anomaly is detected (based on the model’s prediction), the system may trigger an immediate scale-up action, as this often indicates an unexpected spike in demand or a potential fault condition.

3. **Threshold-Based Scaling:**
   - In addition to anomaly detection, the system uses predefined thresholds to determine when to scale resources.
     - **CPU Scaling:** If CPU usage exceeds a specified upper threshold (`cpu_scale_up_threshold`), the system decides to scale up CPU resources. Conversely, if usage falls below a lower threshold (`cpu_scale_down_threshold`), it considers scaling down the CPU.
     - **RAM Scaling:** Similarly, if memory usage exceeds the upper threshold (`ram_scale_up_threshold`), RAM resources are scaled up. If usage is below the lower threshold (`ram_scale_down_threshold`), the system considers scaling down the RAM.
   - These thresholds are configurable, allowing users to tailor the scaling behavior to their specific workload requirements.

4. **Action Determination:**
   - The scaling decision is refined by ensuring that any scaling actions are within the allowed resource limits.
     - **Scaling Up:** When scaling up, the system checks that the new resource allocation does not exceed the maximum limits specified (`max_cpu_cores` for CPU and `max_ram_mb` for RAM).
     - **Scaling Down:** When scaling down, the system ensures that resources do not drop below the minimum limits (`min_cpu_cores` for CPU and `min_ram_mb` for RAM).
   - The final decision is whether to "Scale Up", "Scale Down", or take "No Scaling" action.

5. **Scaling Execution:**
   - Once a decision is made, the system sends requests to adjust the container’s resources. This is done through API calls to an external system or service that manages the containers.
   - The system includes a retry mechanism to handle transient errors in the API requests, ensuring that scaling actions are reliable.

### **Considerations for Effective Autoscaling:**
- **Customization:** Users should configure the thresholds and limits based on their specific use cases. For example, a high-performance web server might need aggressive scaling policies, while a background processing container might tolerate higher resource utilization before scaling.
- **Anomaly Sensitivity:** The sensitivity of anomaly detection can be adjusted through the model's contamination parameter. A lower contamination level will make the model more sensitive to anomalies, potentially triggering more frequent scale-up actions.
- **Resource Limits:** Users should carefully set the minimum and maximum resource limits to prevent the system from over-provisioning (wasting resources) or under-provisioning (causing performance degradation).
- **Monitoring:** It’s essential to monitor the scaling actions and adjust the configuration as needed based on observed behavior. Logs and metrics should be reviewed regularly to ensure that the autoscaling logic aligns with the application's performance requirements.

### The model

The application leverages an Isolation Forest model, which is a machine learning algorithm specifically designed for anomaly detection. The model is a crucial component of the autoscaling system, as it helps identify when a container's behavior deviates from the norm, potentially indicating the need for scaling.

#### **Key Aspects of the Model:**

1. **Feature Selection:**
   - The model only uses numerical features from the dataset, excluding identifiers like `container_id` and `timestamp`. This ensures that the model focuses solely on the metrics that influence container performance, such as CPU and memory usage.
   - Users should be aware that the choice of features can significantly impact the model's effectiveness. Including too many irrelevant features could lead to overfitting, while omitting critical metrics might reduce the model's ability to detect anomalies.

2. **Isolation Forest Overview:**
   - **Isolation Forest** is an ensemble-based algorithm that isolates observations by randomly selecting a feature and then randomly selecting a split value between the maximum and minimum values of the selected feature. The idea is that anomalies are few and different, so they are easier to isolate.
   - The model works by constructing multiple decision trees and calculating the path length of each observation. Shorter paths correspond to anomalies, as they are easier to isolate.

3. **Configurable Parameters:**
   - **Contamination (`contamination`)**: This parameter sets the expected proportion of anomalies in the dataset. A lower contamination level makes the model more conservative (i.e., it will classify fewer points as anomalies). Users should adjust this based on the expected frequency of anomalies in their system.
   - **Number of Trees (`n_estimators`)**: This parameter controls how many trees are built in the ensemble. More trees generally improve the model's robustness but also increase computational cost.
   - **Max Samples (`max_samples`)**: This parameter limits the number of samples to draw from the dataset to train each tree. It helps in controlling overfitting and can be set based on the size of the dataset.
   - **Random State (`random_state`)**: This is a seed for the random number generator to ensure reproducibility of the model's results. It’s particularly useful in a production environment where consistency between runs is important.

4. **Pipeline Integration:**
   - The model is integrated into a pipeline that includes a `StandardScaler` for data normalization. This step ensures that all features contribute equally to the model by scaling them to have zero mean and unit variance.
   - The pipeline approach allows for seamless integration of preprocessing steps and the model, making it easier to manage and extend the model in the future.

5. **Anomaly Prediction:**
   - During prediction, the model generates an anomaly score for each container based on the latest metrics. This score is then converted into a confidence level, which represents the certainty that a container is behaving anomalously.
   - A high confidence level indicates that the container's behavior is significantly different from the norm, prompting the autoscaling logic to potentially increase resources.

6. **Scalability and Efficiency:**
   - The model is designed to be efficient, even with a large number of containers. The use of a limited number of samples (`max_samples`) and decision trees (`n_estimators`) ensures that the model can make predictions in real-time without significant computational overhead.

### **Considerations for Effective Model Use:**
- **Model Training Frequency:** The model should be retrained periodically to adapt to changes in the workload patterns. If the nature of the container's tasks changes over time, the model might need to be retrained more frequently to maintain its accuracy.
- **Feature Engineering:** Users may need to experiment with different sets of features to find the combination that best captures the conditions leading to anomalies. Feature importance can be assessed using various techniques to refine the model.
- **Model Validation:** Before deploying the model in a production environment, it should be validated using historical data to ensure it accurately detects anomalies and does not produce too many false positives or negatives.

By understanding and configuring these aspects, users can ensure that the autoscaling logic and anomaly detection model work effectively to maintain the optimal performance of their containers. Proper tuning and monitoring of the model and scaling logic will help in achieving a balanced system that adapts dynamically to changing workloads.


---

## Best Practices and Tips

### 1. Regularly Review Logs

Reviewing logs regularly is crucial for understanding how LXC AutoScale ML is performing and identifying any potential issues. The logs provide insights into the decisions made by the service, allowing you to fine-tune its behavior.

### 2. Fine-Tune the Model Parameters

Adjusting the Isolation Forest model parameters, such as `contamination`, `n_estimators`, and `max_samples`, can significantly impact the model’s performance. Experiment with different settings to find the best fit for your environment.

### 3. Use Dry-Run Mode for Testing

When making significant configuration changes, use the `--dry-run` option to test the service without affecting live containers. This allows you to verify that the service behaves as expected before applying changes.

### 4. Balance Smoothing and Responsiveness

The `smoothing-factor` parameter helps balance quick responses to changes in resource usage and more gradual adjustments. Fine-tuning this parameter ensures that your containers are scaled efficiently without overreacting to temporary spikes.

### 5. Monitor Disk Space for Logs and Model Files

Ensure that the system has sufficient disk space for storing logs and the trained model file. Regularly check the size of these files and consider rotating logs if they grow too large.
