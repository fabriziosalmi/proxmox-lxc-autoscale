## LXC AutoScale API examples

The LXC AutoScale API offers powerful capabilities for managing and automating LXC containers on a Proxmox server. By leveraging this API, you can dynamically adjust resources, automate routine tasks, and ensure your containers are running optimally based on real-time conditions. Below are practical examples of how you can use the API to enhance your container management. Each example provides a detailed command that you can implement directly in your environment.

## Summary

- [Dynamic CPU Scaling](#dynamic-cpu-scaling): Adjust CPU cores based on time of day.
- [Automated Memory Management](#automated-memory-management): Increase or decrease RAM allocation based on workload demand.
- [Scheduled Storage Expansion](#scheduled-storage-expansion): Automatically expand storage before a large data import.
- [Daily Snapshot Creation](#daily-snapshot-creation): Create a daily snapshot for quick recovery.
- [Snapshot Rollback for Recovery](#snapshot-rollback-for-recovery): Rollback to a snapshot if issues arise.
- [On-Demand Container Cloning](#on-demand-container-cloning): Clone a container for testing purposes.
- [Clean Up Cloned Containers](#clean-up-cloned-containers): Delete a cloned container after testing.
- [Monitor Container Resources](#monitor-container-resources): Regularly check and log container resource usage.
- [Node Resource Usage Monitoring](#node-resource-usage-monitoring): Track resource usage of a Proxmox node.
- [Automated Health Check](#automated-health-check): Perform regular health checks on the API server.
- [Document Available API Routes](#document-available-api-routes): List all available API routes.
- [Temporary Resource Boost for Maintenance](#temporary-resource-boost-for-maintenance): Temporarily increase resources before maintenance.
- [Preemptive Resource Scaling](#preemptive-resource-scaling): Automatically scale resources if CPU usage exceeds a threshold.
- [Automate Cleanup Tasks](#automate-cleanup-tasks): Remove old snapshots and logs to save space.
- [Rolling Snapshot Backup](#rolling-snapshot-backup): Maintain a rolling backup by keeping only the last 7 snapshots.
- [Real-Time Traffic-Based Scaling](#real-time-traffic-based-scaling): Scale up resources dynamically based on network traffic.
- [Clone and Test Environment](#clone-and-test-environment): Automatically clone and delete a test environment.
- [Monitor and Alert on Resource Thresholds](#monitor-and-alert-on-resource-thresholds): Set up monitoring and alerting for resource usage.
- [Health Check and Restart Unresponsive Containers](#health-check-and-restart-unresponsive-containers): Automatically restart a container if it becomes unresponsive.
- [Daily Performance Reports](#daily-performance-reports): Generate and send daily container performance reports.
- [Automated Pre-Deployment Snapshots](#automated-pre-deployment-snapshots): Create a snapshot before deploying changes.
- [Automatic Node Resource Balancing](#automatic-node-resource-balancing): Rebalance resources across nodes based on usage.
- [Log Cleanup Automation](#log-cleanup-automation): Automatically clean up logs to save disk space.
- [Periodic Resource Scaling Based on Historical Data](#periodic-resource-scaling-based-on-historical-data): Scale resources based on historical usage trends.
- [Pre-Scaling for High-Traffic Events](#pre-scaling-for-high-traffic-events): Increase resources before an anticipated high-traffic event.
- [Real-Time Usage Alerts](#real-time-usage-alerts): Set up real-time alerts for CPU or memory usage thresholds.
- [Automatic Downgrade After Off-Peak](#automatic-downgrade-after-off-peak): Downgrade resources after an off-peak period.

---

## Dynamic CPU Scaling

Adjust the number of CPU cores based on time of day.

**Increase cores at 8:00 AM:**
```bash
0 8 * * * curl -X POST http://proxmox:5000/scale/cores \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "cores": 8}'
```

**Decrease cores at 8:00 PM:**
```bash
0 20 * * * curl -X POST http://proxmox:5000/scale/cores \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "cores": 4}'
```

---

## Automated Memory Management

Increase and decrease RAM allocation based on workload demand.

**Increase RAM at 9:00 AM:**
```bash
0 9 * * * curl -X POST http://proxmox:5000/scale/ram \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "memory": 8192}'
```

**Decrease RAM at 7:00 PM:**
```bash
0 19 * * * curl -X POST http://proxmox:5000/scale/ram \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "memory": 4096}'
```

---

## Scheduled Storage Expansion

Automatically expand storage when needed, such as before a large data import.

**Increase storage at midnight:**
```bash
0 0 * * * curl -X POST http://proxmox:5000/scale/storage/increase \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "disk_size": 5}'
```

---

## Daily Snapshot Creation

Create a daily snapshot of a container to ensure quick recovery.

**Create a snapshot at 6:00 AM:**
```bash
0 6 * * * curl -X POST http://proxmox:5000/snapshot/create \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "snapshot_name": "daily_snapshot_$(date +\%F)"}'
```

---

## Snapshot Rollback for Recovery

Rollback to the latest snapshot in case of issues.

**Rollback at 11:00 PM if needed:**
```bash
0 23 * * * curl -X POST http://proxmox:5000/snapshot/rollback \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "snapshot_name": "daily_snapshot_$(date +\%F)"}'
```

---

## On-Demand Container Cloning

Clone a container to test new software updates or changes.

**Create a clone:**
```bash
curl -X POST http://proxmox:5000/clone/create \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "new_vm_id": 105, "new_vm_name": "test_clone"}'
```

---

## Clean Up Cloned Containers

Delete a cloned container after testing is complete.

**Delete the clone:**
```bash
curl -X DELETE http://proxmox:5000/clone/delete \
-H "Content-Type: application/json" \
-d '{"vm_id": 105}'
```

---

## Monitor Container Resources

Regularly check and log the resource usage of a container.

**Log resource usage every hour:**
```bash
0 * * * * curl -X GET "http://proxmox:5000/resource/vm/status?vm_id=104" >> /var/log/lxc_vm_status.log
```

---

## Node Resource Usage Monitoring

Track the resource usage of the Proxmox node to identify potential issues.

**Check node status at 5-minute intervals:**
```bash
*/5 * * * * curl -X GET "http://proxmox:5000/resource/node/status?node_name=proxmox" >> /var/log/node_status.log
```

---

## Automated Health Check

Perform regular health checks on the API server.

**Health check every 5 minutes:**
```bash
*/5 * * * * curl -X GET http://proxmox:5000/health/check
```

---

## Document Available API Routes

List all available API routes for reference.

**List routes:**
```bash
curl -X GET http://proxmox:5000/routes
```

---

## Temporary Resource Boost for Maintenance

Temporarily increase resources before running a maintenance task.

**Boost resources at 11:55 PM:**
```bash
55 23 * * * curl -X POST http://proxmox:5000/scale/cores \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "cores": 8}' && \
curl -X POST http://proxmox:5000/scale/ram \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "memory": 16384}'
```

**Scale back after maintenance:**
```bash
30 0 * * * curl -X POST http://proxmox:5000/scale/cores \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "cores": 4}' && \
curl -X POST http://proxmox:5000/scale/ram \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "memory": 8192}'
```

---

## Preemptive Resource Scaling

Automatically scale resources if CPU usage exceeds 75%.

**Monitor and scale up if needed:**
```bash
* * * * * curl -X GET "http://proxmox:5000/resource/vm/status?vm_id=104" | jq '.cpu' | \
if [ $(jq '.cpu' response.json) -gt 75 ]; then curl -X POST http://proxmox:5000/scale/cores -d '{"cores": 6}'; fi
```

---

## Automate Cleanup Tasks

Remove old snapshots after a specified number of days to save space.

**Cleanup old snapshots every Sunday at midnight:**
```bash
0 0 * * 0 curl -X GET "http://proxmox:5000/snapshot/list?vm_id=104" | jq -r '.[] | select(.timestamp < (now - 7 * 86400)) | .name' | \
while read snapshot; do curl -X POST http://proxmox:5000/snapshot/delete -H "Content-Type: application/json" -d '{"vm_id": 104, "snapshot_name": "$snapshot"}'; done
```

---

## Rolling Snapshot Backup

Maintain a rolling backup by keeping only the last 7 snapshots.

**Create and manage rolling backups:**
```bash
0 2 * * * curl -X POST http://proxmox:5000/snapshot/create \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "snapshot_name": "rolling_backup_$(date +\%F)"}' && \
curl -X GET "http://proxmox:5000/snapshot/list?vm_id=104" | jq -r '.[] | select(.timestamp < (now - 7 * 86400)) | .name' | \
while read snapshot; do curl -X POST http://proxmox:5000/snapshot/delete -H "Content-Type: application/json" -d '{"vm_id": 104, "snapshot_name": "$snapshot"}'; done
```

---

## Real-Time Traffic-Based Scaling

Scale up resources dynamically based on real-time network traffic.

**Scale cores based on traffic:**
```bash
* * * * * curl -X GET "http://proxmox:5000/resource/vm/status?vm_id=104" | jq '.network.traffic' | \
if [ $(jq '.network.traffic' response.json) -gt 1000 ]; then curl -X POST http://proxmox:5000/scale/cores -d '{"cores": 8}'; fi
```

---

## Clone and Test Environment

Automatically clone the environment for testing, then delete it after use.

**Clone at midnight and delete at 4:00 AM:**
```bash
0 0 * * * curl -X POST http://proxmox:5000/clone/create \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "new_vm_id": 106, "new_vm_name": "test_clone"}'

0 4 * * * curl -X DELETE http://proxmox:5000/clone/delete \
-H "Content-Type: application/json" \
-d '{"vm_id": 106}'
```

---

## Monitor and Alert on Resource Thresholds

Set up monitoring and alerting when certain resource thresholds are exceeded.

**Monitor CPU and alert if usage exceeds 85%:**
```bash
* * * * * curl -X GET "http://proxmox:5000/resource/vm/status?vm_id=104" | \
if [ $(jq '.cpu' response.json) -gt 85 ]; then curl -X POST -d "alert: CPU usage high" http://alertmanager:9093/alert; fi
```

---

## Health Check and Restart Unresponsive Containers

Automatically restart a container if it becomes unresponsive.

**Health check and restart:**
```bash
* * * * * curl -X GET "http://proxmox:5000/health/check?vm_id=104" | \
if [ $(jq '.status' response.json) != "healthy" ]; then curl -X POST http://proxmox:5000/vm/restart -H "Content-Type: application/json" -d '{"vm_id": 104}'; fi
```

---

## Daily Performance Reports

Generate and send a daily report on container performance.

**Generate and send report at 7:00 AM:**
```bash
0 7 * * * curl -X GET "http://proxmox:5000/resource/vm/status?vm_id=104" | \
mail -s "Daily Performance Report" admin@example.com
```

---

## Automated Pre-Deployment Snapshots

Create a snapshot before deploying changes to a container.

**Snapshot before deployment:**
```bash
0 3 * * * curl -X POST http://proxmox:5000/snapshot/create \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "snapshot_name": "pre_deploy_snapshot_$(date +\%F)"}'
```

---

## Automatic Node Resource Balancing

Automatically rebalance resources across nodes when usage is high.

**Check and rebalance at 5-minute intervals:**
```bash
*/5 * * * * curl -X GET "http://proxmox:5000/resource/node/status?node_name=proxmox" | jq '.memory' | \
if [ $(jq '.memory.usage' response.json) -gt 80 ]; then curl -X POST http://proxmox:5000/scale/ram -d '{"vm_id": 104, "memory": 4096}'; fi
```

---

## Log Cleanup Automation

Automatically clean up logs to save disk space.

**Cleanup logs every week:**
```bash
0 0 * * 0 curl -X POST http://proxmox:5000/vm/execute \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "command": "find /var/log -type f -name '*.log' -mtime +7 -delete"}'
```

---

## Periodic Resource Scaling Based on Historical Data

Automatically scale resources based on historical usage trends.

**Scale resources on Monday based on last week's usage:**
```bash
0 6 * * 1 curl -X GET "http://proxmox:5000/resource/vm/status?vm_id=104" | jq '.cpu' | \
if [ $(jq '.cpu' response.json) -gt 70 ]; then curl -X POST http://proxmox:5000/scale/cores -d '{"cores": 6}'; fi
```

---

## Pre-Scaling for High-Traffic Events

Increase resources before an anticipated high-traffic event.

**Pre-scale cores at 9:55 AM:**
```bash
55 9 * * * curl -X POST http://proxmox:5000/scale/cores \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "cores": 8}'
```

---

## Real-Time Usage Alerts

Set up real-time alerts for CPU or memory usage exceeding thresholds.

**Alert if memory usage exceeds 90%:**
```bash
* * * * * curl -X GET "http://proxmox:5000/resource/vm/status?vm_id=104" | \
if [ $(jq '.memory.usage' response.json) -gt 90 ]; then curl -X POST -d "alert: High memory usage" http://alertmanager:9093/alert; fi
```

---

## Automatic Downgrade After Off-Peak

Downgrade resources after an off-peak period to save on resource allocation.

**Reduce RAM after 11:00 PM:**
```bash
0 23 * * * curl -X POST http://proxmox:5000/scale/ram \
-H "Content-Type: application/json" \
-d '{"vm_id": 104, "memory": 2048}'
```
