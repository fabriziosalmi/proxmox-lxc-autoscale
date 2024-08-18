import subprocess
from utils import create_response, handle_error

def check_vm_status(vm_id):
    try:
        result = subprocess.run(f"pct status {vm_id}", shell=True, capture_output=True, text=True)
        return create_response(data=result.stdout.strip(), message=f"Resource status retrieved for container {vm_id}")
    except Exception as e:
        return handle_error(e)

def check_node_status(node_name):
    try:
        result = subprocess.run(f"pvesh get /nodes/{node_name}/status", shell=True, capture_output=True, text=True)
        return create_response(data=result.stdout.strip(), message=f"Resource status retrieved for node '{node_name}'")
    except Exception as e:
        return handle_error(e)

def check_cluster_status():
    try:
        result = subprocess.run("pvecm status", shell=True, capture_output=True, text=True)
        return create_response(data=result.stdout.strip(), message="Cluster resource status retrieved successfully")
    except Exception as e:
        return handle_error(e)
