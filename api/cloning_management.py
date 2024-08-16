from lxc_management import LXCManager
from utils import create_response, handle_error

def create_clone(vm_id, new_vm_id, new_vm_name):
    try:
        lxc_manager = LXCManager()
        result = lxc_manager.clone(vm_id, new_vm_id, new_vm_name)
        return create_response(data=result, message=f"Container {vm_id} cloned as '{new_vm_name}' with ID {new_vm_id}")
    except Exception as e:
        return handle_error(e)

def delete_clone(vm_id):
    try:
        lxc_manager = LXCManager()
        result = lxc_manager.delete_container(vm_id)
        return create_response(data=result, message=f"Container {vm_id} successfully deleted")
    except Exception as e:
        return handle_error(e)
