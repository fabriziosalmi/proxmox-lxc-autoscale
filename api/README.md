# LXC AutoScale API

## Installation

The easiest way to install LXC AutoScale API is by using the following `curl` command:

```
curl -sSL https://raw.githubusercontent.com/fabriziosalmi/proxmox-lxc-autoscale/main/api/install.sh | bash
```

## Routes

Here are the routes available to interact with your Proxmox host, 

> [!NOTE]  
> More routes will be added here :)

| Endpoint                    | Methods | Description                                                      | Example                                                                                               |
|-----------------------------|---------|------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| `/scale/cores`              | POST    | Set the exact number of CPU cores for an LXC container.          | `curl -X POST http://proxmox:5000/scale/cores -H "Content-Type: application/json" -d '{"vm_id": 104, "cores": 4}'` |
| `/scale/ram`                | POST    | Set the exact amount of RAM for an LXC container.                | `curl -X POST http://proxmox:5000/scale/ram -H "Content-Type: application/json" -d '{"vm_id": 104, "memory": 4096}'` |
| `/scale/storage/increase`   | POST    | Increase the storage size of an LXC container's root filesystem. | `curl -X POST http://proxmox:5000/scale/storage/increase -H "Content-Type: application/json" -d '{"vm_id": 104, "disk_size": 2}'` |
| `/snapshot/create`          | POST    | Create a snapshot for an LXC container.                          | `curl -X POST http://proxmox:5000/snapshot/create -H "Content-Type: application/json" -d '{"vm_id": 104, "snapshot_name": "my_snapshot"}'` |
| `/snapshot/list`            | GET     | List all snapshots for an LXC container.                         | `curl -X GET "http://proxmox:5000/snapshot/list?vm_id=104"`                                           |
| `/snapshot/rollback`        | POST    | Rollback to a specific snapshot.                                 | `curl -X POST http://proxmox:5000/snapshot/rollback -H "Content-Type: application/json" -d '{"vm_id": 104, "snapshot_name": "my_snapshot"}'` |
| `/clone/create`             | POST    | Clone an LXC container.                                          | `curl -X POST http://proxmox:5000/clone/create -H "Content-Type: application/json" -d '{"vm_id": 104, "new_vm_id": 105, "new_vm_name": "cloned_container"}'` |
| `/clone/delete`             | DELETE  | Delete a cloned LXC container.                                   | `curl -X DELETE http://proxmox:5000/clone/delete -H "Content-Type: application/json" -d '{"vm_id": 105}'` |
| `/resource/vm/status`       | GET     | Check the resource allocation and usage for an LXC container.    | `curl -X GET "http://proxmox:5000/resource/vm/status?vm_id=104"`                                      |
| `/resource/node/status`     | GET     | Check the resource usage of a specific node.                     | `curl -X GET "http://proxmox:5000/resource/node/status?node_name=proxmox4"`                           |
| `/health/check`             | GET     | Perform a health check on the API server.                        | `curl -X GET http://proxmox:5000/health/check`                                                        |
| `/routes`                   | GET     | List all available routes.                                       | `curl -X GET http://proxmox:5000/routes`                                                              |
## Logs

As default option all log files are available at the following paths:

- `/var/log/autoscaleapi.log` (api)
- `/var/log/autoscaleapi_access.log` (gunicorn)
- `/var/log/autoscaleapi_error.log` (gunicorn)
