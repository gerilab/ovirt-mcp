"""MCP tool modules."""

from .events import list_system_events_tool, list_vm_events_tool
from .users import (
    add_permission_tool,
    add_user_tool,
    delete_user_tool,
    get_user_tool,
    list_permissions_tool,
    list_roles_tool,
    list_users_tool,
    remove_permission_tool,
)
from .vms import get_vm_tool, list_vms_tool

__all__ = [
    "add_permission_tool",
    "add_user_tool",
    "delete_user_tool",
    "get_user_tool",
    "get_vm_tool",
    "list_permissions_tool",
    "list_roles_tool",
    "list_system_events_tool",
    "list_users_tool",
    "list_vm_events_tool",
    "list_vms_tool",
    "remove_permission_tool",
]
