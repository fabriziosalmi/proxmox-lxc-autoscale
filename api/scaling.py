from lxc_management import LXCManager
from utils import create_response, handle_error

def scale_cpu(vm_id, cores):
    try:
        lxc_manager = LXCManager()
        result = lxc_manager.scale_cpu(vm_id, cores)
        return create_response(data=result, message=f"CPU cores set to {cores} for container {vm_id}")
    except Exception as e:
        return handle_error(e)

def scale_ram(vm_id, memory):
    try:
        lxc_manager = LXCManager()
        result = lxc_manager.scale_ram(vm_id, memory)
        return create_response(data=result, message=f"RAM set to {memory} MB for container {vm_id}")
    except Exception as e:
        return handle_error(e)

def resize_storage(vm_id, disk_size):
    try:
        lxc_manager = LXCManager()
        result = lxc_manager.resize_storage(vm_id, disk_size)
        return create_response(data=result, message=f"Storage increased by {disk_size} GB for container {vm_id}")
    except Exception as e:
        return handle_error(e)
