"""MCP tool modules."""

from .backups import (
    delete_vm_checkpoint_tool,
    finalize_vm_backup_tool,
    get_vm_backup_tool,
    get_vm_checkpoint_tool,
    list_vm_backups_tool,
    list_vm_checkpoints_tool,
    start_vm_backup_tool,
)
from .clusters import get_cluster_tool, list_clusters_tool, upgrade_cluster_tool
from .compute import get_vm_console_file_tool
from .disks import convert_disk_tool, refresh_disk_lun_tool
from .events import list_system_events_tool, list_vm_events_tool
from .hosts import approve_host_tool, copy_host_networks_tool
from .jobs import get_job_tool, list_jobs_tool
from .storage import list_unregistered_vms_tool, register_unregistered_vm_tool
from .users import (
    add_permission_tool,
    add_role_tool,
    add_user_tool,
    delete_role_tool,
    delete_user_tool,
    get_user_tool,
    list_permissions_tool,
    list_roles_tool,
    list_users_tool,
    remove_permission_tool,
)
from .vm_exports import export_disk_tool, export_vm_tool, import_vm_tool
from .vm_pools import (
    allocate_vm_pool_vm_tool,
    create_vm_pool_tool,
    delete_vm_pool_tool,
    get_vm_pool_tool,
    list_vm_pools_tool,
    update_vm_pool_tool,
)
from .vms import (
    add_vm_watchdog_tool,
    attach_vm_host_device_tool,
    clone_vm_from_snapshot_tool,
    detach_vm_host_device_tool,
    get_vm_initialization_tool,
    get_vm_tool,
    list_vm_host_devices_tool,
    list_vm_watchdogs_tool,
    list_vms_tool,
    remove_vm_watchdog_tool,
    set_vm_initialization_tool,
)

__all__ = [
    "add_permission_tool",
    "add_role_tool",
    "add_user_tool",
    "add_vm_watchdog_tool",
    "allocate_vm_pool_vm_tool",
    "approve_host_tool",
    "attach_vm_host_device_tool",
    "clone_vm_from_snapshot_tool",
    "convert_disk_tool",
    "copy_host_networks_tool",
    "create_vm_pool_tool",
    "delete_role_tool",
    "delete_user_tool",
    "delete_vm_checkpoint_tool",
    "delete_vm_pool_tool",
    "detach_vm_host_device_tool",
    "export_disk_tool",
    "export_vm_tool",
    "finalize_vm_backup_tool",
    "get_cluster_tool",
    "get_job_tool",
    "get_user_tool",
    "get_vm_backup_tool",
    "get_vm_checkpoint_tool",
    "get_vm_console_file_tool",
    "get_vm_initialization_tool",
    "get_vm_pool_tool",
    "get_vm_tool",
    "import_vm_tool",
    "list_clusters_tool",
    "list_jobs_tool",
    "list_permissions_tool",
    "list_roles_tool",
    "list_system_events_tool",
    "list_unregistered_vms_tool",
    "list_users_tool",
    "list_vm_backups_tool",
    "list_vm_checkpoints_tool",
    "list_vm_events_tool",
    "list_vm_host_devices_tool",
    "list_vm_pools_tool",
    "list_vm_watchdogs_tool",
    "list_vms_tool",
    "refresh_disk_lun_tool",
    "register_unregistered_vm_tool",
    "remove_permission_tool",
    "remove_vm_watchdog_tool",
    "set_vm_initialization_tool",
    "start_vm_backup_tool",
    "update_vm_pool_tool",
    "upgrade_cluster_tool",
]
