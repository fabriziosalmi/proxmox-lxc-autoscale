# This Python script generates fake metrics data for containers. 
# It can simulate various metrics such as CPU usage, memory usage, network activity, etc., with options to introduce randomness and spikes in the data. 
# The script supports generating data for multiple containers over a specified period and saving the output in JSON format.
# Example use: 
# python3 generate_metrics.py --num-containers 5 --num-entries 100000 --interval-seconds 60 --randomness 1.0 --spike-likelihood 0.2 --spike-magnitude 1.0 --output-file fake_metrics.json


import json
import argparse
import datetime
import random

def generate_metrics(container_id, base_time, interval_seconds, randomness_factor, spike_likelihood, spike_magnitude, base_metrics):
    """
    Generate a single set of metrics for a container, with optional spikes.

    Args:
        container_id (str): The ID of the container.
        base_time (datetime): The base timestamp to start from.
        interval_seconds (int): Time interval between each data point.
        randomness_factor (float): Factor to introduce variability in metrics.
        spike_likelihood (float): Probability of a spike occurring (0 to 1).
        spike_magnitude (float): Magnitude of the spike when it occurs.
        base_metrics (dict): Base metrics with initial values and variability ranges.

    Returns:
        dict: A dictionary containing the generated metrics.
        datetime: The updated base_time after the interval.
    """
    # Base metrics with added randomness and optional spikes
    cpu_usage_percent = base_metrics["cpu_usage_percent"] + (randomness_factor * base_metrics["cpu_variability"])
    memory_usage_mb = base_metrics["memory_usage_mb"] + (randomness_factor * base_metrics["memory_variability"])
    swap_usage_mb = base_metrics["swap_usage_mb"]
    swap_total_mb = base_metrics["swap_total_mb"]
    process_count = base_metrics["process_count"]
    io_reads = base_metrics["io_reads"] + int(randomness_factor * base_metrics["io_variability"])
    io_writes = base_metrics["io_writes"] + int(randomness_factor * base_metrics["io_variability"])
    network_rx_bytes = base_metrics["network_rx_bytes"] + int(randomness_factor * base_metrics["network_variability"])
    network_tx_bytes = base_metrics["network_tx_bytes"] + int(randomness_factor * base_metrics["network_variability"])
    filesystem_usage_gb = base_metrics["filesystem_usage_gb"]
    filesystem_total_gb = base_metrics["filesystem_total_gb"]
    filesystem_free_gb = base_metrics["filesystem_free_gb"]

    # Apply spikes based on the spike likelihood
    if random.random() < spike_likelihood:
        cpu_usage_percent *= (1 + spike_magnitude)
        memory_usage_mb *= (1 + spike_magnitude)
        io_reads *= (1 + spike_magnitude)
        io_writes *= (1 + spike_magnitude)
        network_rx_bytes *= (1 + spike_magnitude)
        network_tx_bytes *= (1 + spike_magnitude)

    timestamp = base_time + datetime.timedelta(seconds=interval_seconds)
    base_time = timestamp

    metrics = {
        container_id: {
            "timestamp": timestamp.isoformat(),
            "cpu_usage_percent": cpu_usage_percent,
            "memory_usage_mb": memory_usage_mb,
            "swap_usage_mb": swap_usage_mb,
            "swap_total_mb": swap_total_mb,
            "process_count": process_count,
            "io_stats": {
                "reads": io_reads,
                "writes": io_writes
            },
            "network_usage": {
                "rx_bytes": network_rx_bytes,
                "tx_bytes": network_tx_bytes
            },
            "filesystem_usage_gb": filesystem_usage_gb,
            "filesystem_total_gb": filesystem_total_gb,
            "filesystem_free_gb": filesystem_free_gb
        },
        "summary": {
            "collection_start_time": (timestamp - datetime.timedelta(seconds=6)).isoformat(),
            "collection_end_time": timestamp.isoformat(),
            "total_containers": 1,
            "total_duration_seconds": 6.0,
            "monitor_cpu_percent": cpu_usage_percent,
            "monitor_memory_usage_mb": memory_usage_mb
        }
    }

    return metrics, base_time

def generate_dataset(container_ids, num_entries, interval_seconds, randomness_factor, spike_likelihood, spike_magnitude, base_metrics):
    """
    Generate a dataset of fake metrics for multiple containers, with optional spikes.

    Args:
        container_ids (list of str): List of container IDs.
        num_entries (int): Number of metric entries to generate for each container.
        interval_seconds (int): Time interval between each data point.
        randomness_factor (float): Factor to introduce variability in metrics.
        spike_likelihood (float): Probability of a spike occurring (0 to 1).
        spike_magnitude (float): Magnitude of the spike when it occurs.
        base_metrics (dict): Base metrics with initial values and variability ranges.

    Returns:
        list of dict: The generated dataset.
    """
    base_time = datetime.datetime.now()
    dataset = []

    for _ in range(num_entries):
        for container_id in container_ids:
            metrics, base_time = generate_metrics(
                container_id, base_time, interval_seconds, randomness_factor, spike_likelihood, spike_magnitude, base_metrics
            )
            dataset.append(metrics)

    return dataset

def main():
    """
    Main function to parse arguments and generate the fake metrics dataset.
    """
    parser = argparse.ArgumentParser(description="Generate fake metrics data with optional spikes.")
    parser.add_argument(
        '--container-id', nargs='*', type=str,
        help="Container ID(s). If not provided, IDs from 100 to 999 will be used."
    )
    parser.add_argument(
        '--num-containers', type=int, default=1,
        help="Number of container IDs to generate (only used if --container-id is not provided)"
    )
    parser.add_argument(
        '--num-entries', type=int, default=10,
        help="Number of metric entries to generate for each container"
    )
    parser.add_argument(
        '--interval-seconds', type=int, default=60,
        help="Interval between data points in seconds"
    )
    parser.add_argument(
        '--randomness', type=float, default=1.0,
        help="Randomness factor for metric generation"
    )
    parser.add_argument(
        '--spike-likelihood', type=float, default=0.1,
        help="Likelihood of a spike occurring (0 to 1)"
    )
    parser.add_argument(
        '--spike-magnitude', type=float, default=0.5,
        help="Magnitude of the spike (as a percentage increase)"
    )
    parser.add_argument(
        '--output-file', type=str, default="fake_metrics.json",
        help="Output file to save the generated dataset"
    )

    # Default base metrics with variability ranges
    base_metrics = {
        "cpu_usage_percent": 5.0,
        "cpu_variability": 0.5,
        "memory_usage_mb": 96.0,
        "memory_variability": 0.8,
        "swap_usage_mb": 94.3359375,
        "swap_total_mb": 512.0,
        "process_count": 27,
        "io_reads": 19500000,
        "io_writes": 6900000,
        "io_variability": 50000,
        "network_rx_bytes": 950000,
        "network_tx_bytes": 57000,
        "network_variability": 10000,
        "filesystem_usage_gb": 1.5947265625,
        "filesystem_total_gb": 18.5341796875,
        "filesystem_free_gb": 16.0048828125
    }

    args = parser.parse_args()

    if args.container_id:
        container_ids = args.container_id
    else:
        start_id = 100
        end_id = start_id + args.num_containers
        end_id = min(end_id, 1000)
        container_ids = [str(i) for i in range(start_id, end_id)]

    dataset = generate_dataset(
        container_ids, args.num_entries, args.interval_seconds, args.randomness,
        args.spike_likelihood, args.spike_magnitude, base_metrics
    )

    with open(args.output_file, 'w', encoding='utf-8') as output_file:
        json.dump(dataset, output_file, indent=4)

    print(f"Generated {args.num_entries} entries of fake metrics data for "
          f"{len(container_ids)} containers with {args.interval_seconds}s intervals "
          f"and saved to {args.output_file}")

if __name__ == "__main__":
    main()
