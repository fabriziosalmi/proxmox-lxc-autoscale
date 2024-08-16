import subprocess
import shlex
from flask import current_app
import logging

class LXCManager:
    def __init__(self, node=None):
        self.node = node or current_app.config['LXC_NODE']
        self.timeout = current_app.config['TIMEOUT']

    def _run_command(self, command):
        try:
            logging.info(f"Running command: {command}")
            result = subprocess.run(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                universal_newlines=True
            )
            result.check_returncode()
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logging.error(f"Command failed: {e.stderr}")
            raise Exception(f"Command failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            logging.error("Command timed out")
            raise Exception("Command timed out")


    def stop_container(self, vm_id):
        command = f"pct stop {vm_id}"
        return self._run_command(command)

    def destroy_container(self, vm_id):
        command = f"pct destroy {vm_id}"
        return self._run_command(command)

    def create_temporary_snapshot(self, vm_id):
        snapshot_name = f"migrate-snapshot-{vm_id}"
        command = f"pct snapshot {vm_id} {snapshot_name}"
        self._run_command(command)
        return snapshot_name

    def delete_snapshot(self, vm_id, snapshot_name):
        command = f"pct delsnapshot {vm_id} {snapshot_name}"
        self._run_command(command)

    def migrate_container(self, vm_id, target_node):
        # Check for non-migratable snapshots or create a new one for migration
        snapshot_name = self.create_temporary_snapshot(vm_id)
        
        try:
            command = f"pct migrate {vm_id} {target_node}"
            self._run_command(command)
        finally:
            # Clean up the temporary snapshot after migration
            self.delete_snapshot(vm_id, snapshot_name)

    def scale_cpu(self, vm_id, cores):
        command = f"pct set {vm_id} -cores {cores}"
        return self._run_command(command)

    def scale_ram(self, vm_id, memory):
        command = f"pct set {vm_id} -memory {memory}"
        return self._run_command(command)

    def get_current_disk_size(self, vm_id):
        # Retrieve the current size of the root filesystem in GB
        command = f"pct config {vm_id}"
        output = self._run_command(command)
        for line in output.splitlines():
            if line.startswith("rootfs:"):
                current_size = line.split(",")[1].replace("size=", "").replace("G", "").strip()
                return int(current_size)
        raise Exception("Failed to retrieve current disk size")

    def resize_storage(self, vm_id, disk_size):
        current_size = self.get_current_disk_size(vm_id)
        new_size = current_size + disk_size
        command = f"pct resize {vm_id} rootfs {new_size}G"
        return self._run_command(command)

    def create_snapshot(self, vm_id, snapshot_name):
        command = f"pct snapshot {vm_id} {snapshot_name}"
        return self._run_command(command)

    def clone_container(self, vm_id, new_vm_id, new_vm_name, snapshot_name):
        command = f"pct clone {vm_id} {new_vm_id} --hostname {new_vm_name} --snapname {snapshot_name}"
        return self._run_command(command)

    def start_container(self, vm_id):
        command = f"pct start {vm_id}"
        return self._run_command(command)

    def list_snapshots(self, vm_id):
        command = f"pct listsnapshot {vm_id}"
        return self._run_command(command)

    def rollback_snapshot(self, vm_id, snapshot_name):
        command = f"pct rollback {vm_id} {snapshot_name}"
        return self._run_command(command)

    def clone(self, vm_id, new_vm_id, new_vm_name):
        command = f"pct clone {vm_id} {new_vm_id} --hostname {new_vm_name} --full"
        return self._run_command(command)

    def delete_container(self, vm_id):
        command = f"pct stop {vm_id} && pct destroy {vm_id}"
        return self._run_command(command)

    def migrate(self, vm_id, target_node):
        command = f"pct migrate {vm_id} {target_node}"
        return self._run_command(command)
