import logging
from flask import Flask, jsonify, request
from config import create_app
from scaling import scale_cpu, scale_ram, resize_storage
from snapshot_management import create_snapshot, list_snapshots, rollback_snapshot
from cloning_management import create_clone, delete_clone
from cluster_management import migrate_vm
from resource_checking import check_vm_status, check_node_status, check_cluster_status
from health_check import health_check
from rate_limiting import rate_limit
from error_handling import handle_error
from lxc_management import LXCManager
from utils import create_response

# Setup logging
log_file = "/var/log/autoscaleapi.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=5)
    ]
)

app = create_app()

# Home route

@app.route('/', methods=['GET'])
def home():
    documentation = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <title>AutoScaleAPI Documentation</title>
        <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { padding-top: 50px; }
            table { margin-top: 20px; }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-light bg-light fixed-top">
            <a class="navbar-brand" href="#">AutoScaleAPI</a>
        </nav>

        <div class="container">
            <h1 class="mt-5">AutoScaleAPI Documentation</h1>
            <p class="lead">Welcome to the AutoScaleAPI. Below is a list of available API routes with descriptions and example usage.</p>

            <table class="table table-hover table-bordered">
                <thead class="thead-dark">
                    <tr>
                        <th>Endpoint</th>
                        <th>Methods</th>
                        <th>Description</th>
                        <th>Example</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>/scale/cores</td>
                        <td>POST</td>
                        <td>Set the exact number of CPU cores for an LXC container.</td>
                        <td><code>curl -X POST http://proxmox:5000/scale/cores -H "Content-Type: application/json" -d '{"vm_id": 104, "cores": 4}'</code></td>
                    </tr>
                    <tr>
                        <td>/scale/ram</td>
                        <td>POST</td>
                        <td>Set the exact amount of RAM for an LXC container.</td>
                        <td><code>curl -X POST http://proxmox:5000/scale/ram -H "Content-Type: application/json" -d '{"vm_id": 104, "memory": 4096}'</code></td>
                    </tr>
                    <tr>
                        <td>/scale/storage/increase</td>
                        <td>POST</td>
                        <td>Increase the storage size of an LXC container's root filesystem.</td>
                        <td><code>curl -X POST http://proxmox:5000/scale/storage/increase -H "Content-Type: application/json" -d '{"vm_id": 104, "disk_size": 2}'</code></td>
                    </tr>
                    <tr>
                        <td>/snapshot/create</td>
                        <td>POST</td>
                        <td>Create a snapshot for an LXC container.</td>
                        <td><code>curl -X POST http://proxmox:5000/snapshot/create -H "Content-Type: application/json" -d '{"vm_id": 104, "snapshot_name": "my_snapshot"}'</code></td>
                    </tr>
                    <tr>
                        <td>/snapshot/list</td>
                        <td>GET</td>
                        <td>List all snapshots for an LXC container.</td>
                        <td><code>curl -X GET "http://proxmox:5000/snapshot/list?vm_id=104"</code></td>
                    </tr>
                    <tr>
                        <td>/snapshot/rollback</td>
                        <td>POST</td>
                        <td>Rollback to a specific snapshot.</td>
                        <td><code>curl -X POST http://proxmox:5000/snapshot/rollback -H "Content-Type: application/json" -d '{"vm_id": 104, "snapshot_name": "my_snapshot"}'</code></td>
                    </tr>
                    <tr>
                        <td>/clone/create</td>
                        <td>POST</td>
                        <td>Clone an LXC container.</td>
                        <td><code>curl -X POST http://proxmox:5000/clone/create -H "Content-Type: application/json" -d '{"vm_id": 104, "new_vm_id": 105, "new_vm_name": "cloned_container"}'</code></td>
                    </tr>
                    <tr>
                        <td>/clone/delete</td>
                        <td>DELETE</td>
                        <td>Delete a cloned LXC container.</td>
                        <td><code>curl -X DELETE http://proxmox:5000/clone/delete -H "Content-Type: application/json" -d '{"vm_id": 105}'</code></td>
                    </tr>
                    <tr>
                        <td>/resource/vm/status</td>
                        <td>GET</td>
                        <td>Check the resource allocation and usage for an LXC container.</td>
                        <td><code>curl -X GET "http://proxmox:5000/resource/vm/status?vm_id=104"</code></td>
                    </tr>
                    <tr>
                        <td>/resource/node/status</td>
                        <td>GET</td>
                        <td>Check the resource usage of a specific node.</td>
                        <td><code>curl -X GET "http://proxmox:5000/resource/node/status?node_name=proxmox4"</code></td>
                    </tr>
                    <tr>
                        <td>/health/check</td>
                        <td>GET</td>
                        <td>Perform a health check on the API server.</td>
                        <td><code>curl -X GET http://proxmox:5000/health/check</code></td>
                    </tr>
                    <tr>
                        <td>/routes</td>
                        <td>GET</td>
                        <td>List all available routes.</td>
                        <td><code>curl -X GET http://proxmox:5000/routes</code></td>
                    </tr>
                </tbody>
            </table>
        </div>

        <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.3/dist/umd/popper.min.js"></script>
        <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
    </body>
    </html>
    """.replace("<host>", "proxmox")

    return documentation


# Define routes

@app.route('/scale/cores', methods=['POST'])
@rate_limit
def set_cores():
    data = request.json
    vm_id = data['vm_id']
    cores = data['cores']
    logging.info(f"Setting {cores} cores for VM {vm_id}")
    return scale_cpu(vm_id, cores)

@app.route('/scale/ram', methods=['POST'])
@rate_limit
def set_ram():
    data = request.json
    vm_id = data['vm_id']
    memory = data['memory']
    logging.info(f"Setting {memory} MB RAM for VM {vm_id}")
    return scale_ram(vm_id, memory)

@app.route('/scale/storage/increase', methods=['POST'])
@rate_limit
def increase_storage():
    data = request.json
    vm_id = data['vm_id']
    disk_size = data['disk_size']
    logging.info(f"Increasing storage by {disk_size} GB for VM {vm_id}")
    return resize_storage(vm_id, disk_size)

@app.route('/snapshot/create', methods=['POST'])
@rate_limit
def create_snapshot_route():
    data = request.json
    vm_id = data['vm_id']
    snapshot_name = data['snapshot_name']
    logging.info(f"Creating snapshot '{snapshot_name}' for VM {vm_id}")
    return create_snapshot(vm_id, snapshot_name)

@app.route('/snapshot/list', methods=['GET'])
@rate_limit
def list_snapshots_route():
    vm_id = request.args.get('vm_id')
    return list_snapshots(vm_id)

@app.route('/snapshot/rollback', methods=['POST'])
@rate_limit
def rollback_snapshot_route():
    data = request.json
    vm_id = data['vm_id']
    snapshot_name = data['snapshot_name']
    return rollback_snapshot(vm_id, snapshot_name)

@app.route('/clone/create', methods=['POST'])
@rate_limit
def create_clone():
    data = request.json
    vm_id = data['vm_id']
    new_vm_id = data['new_vm_id']
    new_vm_name = data['new_vm_name'].replace('_', '-')  # Replace underscores with hyphens
    snapshot_name = f"snapshot-{new_vm_id}"  # Create a unique snapshot name

    try:
        lxc_manager = LXCManager()

        # Step 1: Create a snapshot
        lxc_manager.create_snapshot(vm_id, snapshot_name)
        logging.info(f"Creating snapshot of VM {vm_id} with name '{snapshot_name}'")

        # Step 2: Clone the container from the snapshot
        lxc_manager.clone_container(vm_id, new_vm_id, new_vm_name, snapshot_name)
        logging.info(f"Cloning VM {vm_id} to new VM {new_vm_id} with name '{new_vm_name}'")

        # Step 3: Start the cloned container
        lxc_manager.start_container(new_vm_id)
        logging.info(f"Starting clone VM {new_vm_id} with name '{new_vm_name}'")

        # Step 4: Delete the snapshot
        lxc_manager.delete_snapshot(vm_id, snapshot_name)
        logging.info(f"Deleting snapshot of VM {vm_id} with name '{snapshot_name}'")

        return create_response(
            data=f"Container {new_vm_id} cloned from {vm_id} and started successfully. Snapshot {snapshot_name} removed.",
            message="Clone operation completed successfully.",
            status_code=200
        )
    except Exception as e:
        return handle_error(e)


@app.route('/clone/delete', methods=['DELETE'])
@rate_limit
def delete_clone_route():
    vm_id = request.json['vm_id']

    try:
        lxc_manager = LXCManager()

        # Step 1: Stop the container
        lxc_manager.stop_container(vm_id)
        logging.info(f"Stopping VM {new_vm_id}")

        # Step 2: Destroy the container
        lxc_manager.destroy_container(vm_id)
        logging.info(f"Destroying VM {new_vm_id}")

        return create_response(
            data=f"Container {vm_id} stopped and destroyed successfully.",
            message="Delete operation completed successfully.",
            status_code=200
        )
    except Exception as e:
        return handle_error(e)


@app.route('/resource/vm/status', methods=['GET'])
@rate_limit
def check_vm_status_route():
    vm_id = request.args.get('vm_id')
    logging.info(f"Checking status for VM {vm_id}")
    return check_vm_status(vm_id)

@app.route('/resource/node/status', methods=['GET'])
@rate_limit
def check_node_status_route():
    node_name = request.args.get('node_name')
    logging.info(f"Checking status for node {node_name}")
    return check_node_status(node_name)

@app.route('/health/check', methods=['GET'])
def health_check_route():
    logging.info("Health check endpoint accessed")
    return health_check()

@app.route('/routes', methods=['GET'])
def list_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        route = {
            "endpoint": rule.endpoint,
            "methods": methods,
            "url": str(rule)
        }
        routes.append(route)
    logging.info("Routes list endpoint accessed")
    return jsonify(routes), 200


# Setup logging
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
