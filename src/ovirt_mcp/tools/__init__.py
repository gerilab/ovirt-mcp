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
from .events import list_system_events_tool, list_vm_events_tool
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
from .vm_pools import (
    allocate_vm_pool_vm_tool,
    create_vm_pool_tool,
    delete_vm_pool_tool,
    get_vm_pool_tool,
    list_vm_pools_tool,
    update_vm_pool_tool,
)
from .vms import get_vm_tool, list_vms_tool

__all__ = [
    "add_permission_tool",
    "add_role_tool",
    "add_user_tool",
    "allocate_vm_pool_vm_tool",
    "create_vm_pool_tool",
    "delete_role_tool",
    "delete_user_tool",
    "delete_vm_checkpoint_tool",
    "delete_vm_pool_tool",
    "finalize_vm_backup_tool",
    "get_user_tool",
    "get_vm_backup_tool",
    "get_vm_checkpoint_tool",
    "get_vm_pool_tool",
    "get_vm_tool",
    "list_permissions_tool",
    "list_roles_tool",
    "list_system_events_tool",
    "list_users_tool",
    "list_vm_backups_tool",
    "list_vm_checkpoints_tool",
    "list_vm_events_tool",
    "list_vm_pools_tool",
    "list_vms_tool",
    "remove_permission_tool",
    "start_vm_backup_tool",
    "update_vm_pool_tool",
]
