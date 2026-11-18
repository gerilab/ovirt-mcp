"""Tools for managing oVirt / OLVM Inventory Tags and tag assignments."""

import logging

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.tag import (
    TagAssignmentResult,
    TagResult,
    TagSummary,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger("ovirt_mcp.tools.tags")

ROOT_TAG_ID = "00000000-0000-0000-0000-000000000000"


def list_tags_tool(search: str | None = None) -> list[TagSummary]:
    """List inventory tags in the oVirt / OLVM environment.

    Args:
        search: Optional search query (e.g. 'name=prod*').

    Returns:
        List of TagSummary objects with parent hierarchical links.
    """
    client = get_client()
    conn = client.get_connection()
    tags_svc = conn.system_service().tags_service()

    try:
        raw_tags = tags_svc.list(search=search)
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to list tags: {exc}",
            details={"search": search, "error": str(exc)},
        ) from exc

    results: list[TagSummary] = []
    for t in raw_tags:
        t_id = str(t.id)
        t_name = str(getattr(t, "name", t_id))
        desc = str(t.description) if getattr(t, "description", None) is not None else None

        p_id = None
        if hasattr(t, "parent") and t.parent and getattr(t.parent, "id", None):
            p_id = str(t.parent.id)

        results.append(
            TagSummary(
                id=t_id,
                name=t_name,
                description=desc,
                parent_id=p_id,
            )
        )

    return results


def create_tag_tool(
    name: str,
    description: str | None = None,
    parent: str | None = None,
) -> TagResult:
    """Create a new inventory tag in oVirt / OLVM.

    Args:
        name: Name for the new tag.
        description: Optional descriptive text.
        parent: Optional parent tag name or UUID to create a hierarchical nested tag.

    Returns:
        TagResult with creation outcome.
    """
    require_mutation_allowed("ovirt_tag_create")

    name = name.strip()
    if not name:
        raise OvirtValidationError("Tag name cannot be empty.")

    client = get_client()
    conn = client.get_connection()
    tags_svc = conn.system_service().tags_service()

    # Name collision check
    for t in tags_svc.list():
        if str(getattr(t, "name", "")).lower() == name.lower():
            raise OvirtValidationError(
                f"A tag named '{name}' already exists in the environment.",
                details={"tag_name": name, "existing_id": str(t.id)},
            )

    parent_id = None
    if parent:
        parent_tag = client.find_resource_by_id_or_name(tags_svc, parent, "tag")
        parent_id = str(parent_tag.id)

    tag_spec = sdk_types.Tag(
        name=name,
        description=description,
    )
    if parent_id:
        tag_spec.parent = sdk_types.Tag(id=parent_id)

    try:
        created = tags_svc.add(tag_spec)
        t_id = str(created.id)
    except Exception as exc:
        audit_log("ovirt_tag_create", name, {"parent": parent, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(
            f"Failed to create tag '{name}': {exc}",
            details={"tag_name": name, "error": str(exc)},
        ) from exc

    audit_log("ovirt_tag_create", name, {"tag_id": t_id, "parent": parent}, "SUCCESS")

    return TagResult(
        success=True,
        tag_id=t_id,
        tag_name=name,
        action="create",
        message=f"Inventory tag '{name}' successfully created.",
    )


def delete_tag_tool(
    name_or_id: str,
    confirm: bool = False,
) -> TagResult:
    """Delete an inventory tag from oVirt / OLVM.

    Protected by safe-mode confirmation. The root tag cannot be deleted.

    Args:
        name_or_id: Tag name or UUID.
        confirm: Confirmation flag required in safe-mode.

    Returns:
        TagResult with deletion outcome.
    """
    require_destructive_confirmation("ovirt_tag_delete", confirm)
    require_mutation_allowed("ovirt_tag_delete")

    client = get_client()
    conn = client.get_connection()
    tags_svc = conn.system_service().tags_service()

    tag = client.find_resource_by_id_or_name(tags_svc, name_or_id, "tag")
    t_id = str(tag.id)
    t_name = str(getattr(tag, "name", t_id))

    if t_id == ROOT_TAG_ID or t_name.lower() == "root":
        raise OvirtValidationError(
            f"Cannot delete system root tag '{t_name}' ({t_id}).",
            details={"tag_id": t_id, "tag_name": t_name},
        )

    try:
        tags_svc.tag_service(t_id).remove()
    except Exception as exc:
        audit_log("ovirt_tag_delete", t_name, {"tag_id": t_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(
            f"Failed to delete tag '{t_name}' ({t_id}): {exc}",
            details={"tag_id": t_id, "error": str(exc)},
        ) from exc

    audit_log("ovirt_tag_delete", t_name, {"tag_id": t_id}, "SUCCESS")

    return TagResult(
        success=True,
        tag_id=t_id,
        tag_name=t_name,
        action="delete",
        message=f"Inventory tag '{t_name}' ({t_id}) successfully deleted.",
    )


def assign_vm_tag_tool(
    vm_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Assign an inventory tag to a virtual machine.

    Args:
        vm_name_or_id: Name or UUID of the virtual machine.
        tag_name_or_id: Name or UUID of the tag to assign.

    Returns:
        TagAssignmentResult with assignment outcome.
    """
    require_mutation_allowed("ovirt_vm_tag_assign")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    vms_svc = sys_svc.vms_service()
    tags_svc = sys_svc.tags_service()

    vm = client.find_resource_by_id_or_name(vms_svc, vm_name_or_id, "vm")
    tag = client.find_resource_by_id_or_name(tags_svc, tag_name_or_id, "tag")

    vm_tags_svc = vms_svc.vm_service(vm.id).tags_service()

    # Check if already assigned
    for t in vm_tags_svc.list():
        if str(t.id) == str(tag.id):
            return TagAssignmentResult(
                success=True,
                tag_id=str(tag.id),
                tag_name=str(tag.name),
                entity_id=str(vm.id),
                entity_name=str(vm.name),
                entity_type="vm",
                action="assign",
                message=f"Tag '{tag.name}' is already assigned to VM '{vm.name}'.",
            )

    try:
        vm_tags_svc.add(sdk_types.Tag(id=tag.id))
    except Exception as exc:
        audit_log(
            "ovirt_vm_tag_assign", str(tag.name), {"vm": str(vm.name), "error": str(exc)}, "FAILED"
        )
        raise OvirtMCPError(
            f"Failed to assign tag '{tag.name}' to VM '{vm.name}': {exc}",
            details={"vm_id": str(vm.id), "tag_id": str(tag.id), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_vm_tag_assign",
        str(tag.name),
        {"vm_id": str(vm.id), "tag_id": str(tag.id)},
        "SUCCESS",
    )

    return TagAssignmentResult(
        success=True,
        tag_id=str(tag.id),
        tag_name=str(tag.name),
        entity_id=str(vm.id),
        entity_name=str(vm.name),
        entity_type="vm",
        action="assign",
        message=f"Tag '{tag.name}' successfully assigned to VM '{vm.name}'.",
    )


def unassign_vm_tag_tool(
    vm_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Unassign an inventory tag from a virtual machine.

    Args:
        vm_name_or_id: Name or UUID of the virtual machine.
        tag_name_or_id: Name or UUID of the tag to detach.

    Returns:
        TagAssignmentResult with unassignment outcome.
    """
    require_mutation_allowed("ovirt_vm_tag_unassign")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    vms_svc = sys_svc.vms_service()
    tags_svc = sys_svc.tags_service()

    vm = client.find_resource_by_id_or_name(vms_svc, vm_name_or_id, "vm")
    tag = client.find_resource_by_id_or_name(tags_svc, tag_name_or_id, "tag")

    vm_tags_svc = vms_svc.vm_service(vm.id).tags_service()

    try:
        vm_tags_svc.tag_service(tag.id).remove()
    except Exception as exc:
        audit_log(
            "ovirt_vm_tag_unassign",
            str(tag.name),
            {"vm": str(vm.name), "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to unassign tag '{tag.name}' from VM '{vm.name}': {exc}",
            details={"vm_id": str(vm.id), "tag_id": str(tag.id), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_vm_tag_unassign",
        str(tag.name),
        {"vm_id": str(vm.id), "tag_id": str(tag.id)},
        "SUCCESS",
    )

    return TagAssignmentResult(
        success=True,
        tag_id=str(tag.id),
        tag_name=str(tag.name),
        entity_id=str(vm.id),
        entity_name=str(vm.name),
        entity_type="vm",
        action="unassign",
        message=f"Tag '{tag.name}' successfully unassigned from VM '{vm.name}'.",
    )


def assign_host_tag_tool(
    host_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Assign an inventory tag to a hypervisor host.

    Args:
        host_name_or_id: Name or UUID of the hypervisor host.
        tag_name_or_id: Name or UUID of the tag to assign.

    Returns:
        TagAssignmentResult with assignment outcome.
    """
    require_mutation_allowed("ovirt_host_tag_assign")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()
    tags_svc = sys_svc.tags_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    tag = client.find_resource_by_id_or_name(tags_svc, tag_name_or_id, "tag")

    host_tags_svc = hosts_svc.host_service(host.id).tags_service()

    # Check if already assigned
    for t in host_tags_svc.list():
        if str(t.id) == str(tag.id):
            return TagAssignmentResult(
                success=True,
                tag_id=str(tag.id),
                tag_name=str(tag.name),
                entity_id=str(host.id),
                entity_name=str(host.name),
                entity_type="host",
                action="assign",
                message=f"Tag '{tag.name}' is already assigned to host '{host.name}'.",
            )

    try:
        host_tags_svc.add(sdk_types.Tag(id=tag.id))
    except Exception as exc:
        audit_log(
            "ovirt_host_tag_assign",
            str(tag.name),
            {"host": str(host.name), "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to assign tag '{tag.name}' to host '{host.name}': {exc}",
            details={"host_id": str(host.id), "tag_id": str(tag.id), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_host_tag_assign",
        str(tag.name),
        {"host_id": str(host.id), "tag_id": str(tag.id)},
        "SUCCESS",
    )

    return TagAssignmentResult(
        success=True,
        tag_id=str(tag.id),
        tag_name=str(tag.name),
        entity_id=str(host.id),
        entity_name=str(host.name),
        entity_type="host",
        action="assign",
        message=f"Tag '{tag.name}' successfully assigned to host '{host.name}'.",
    )


def unassign_host_tag_tool(
    host_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Unassign an inventory tag from a hypervisor host.

    Args:
        host_name_or_id: Name or UUID of the hypervisor host.
        tag_name_or_id: Name or UUID of the tag to detach.

    Returns:
        TagAssignmentResult with unassignment outcome.
    """
    require_mutation_allowed("ovirt_host_tag_unassign")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()
    tags_svc = sys_svc.tags_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    tag = client.find_resource_by_id_or_name(tags_svc, tag_name_or_id, "tag")

    host_tags_svc = hosts_svc.host_service(host.id).tags_service()

    try:
        host_tags_svc.tag_service(tag.id).remove()
    except Exception as exc:
        audit_log(
            "ovirt_host_tag_unassign",
            str(tag.name),
            {"host": str(host.name), "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to unassign tag '{tag.name}' from host '{host.name}': {exc}",
            details={"host_id": str(host.id), "tag_id": str(tag.id), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_host_tag_unassign",
        str(tag.name),
        {"host_id": str(host.id), "tag_id": str(tag.id)},
        "SUCCESS",
    )

    return TagAssignmentResult(
        success=True,
        tag_id=str(tag.id),
        tag_name=str(tag.name),
        entity_id=str(host.id),
        entity_name=str(host.name),
        entity_type="host",
        action="unassign",
        message=f"Tag '{tag.name}' successfully unassigned from host '{host.name}'.",
    )


def list_user_tags_tool(user_name_or_id: str) -> list[TagSummary]:
    """List inventory tags assigned to an oVirt / OLVM user.

    Args:
        user_name_or_id: Username or UUID of the user.

    Returns:
        List of TagSummary objects assigned to the user.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    users_svc = sys_svc.users_service()

    user = client.find_resource_by_id_or_name(users_svc, user_name_or_id, "user")
    user_tags_svc = users_svc.user_service(user.id).tags_service()

    try:
        raw_tags = user_tags_svc.list()
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to list tags for user '{user_name_or_id}': {exc}",
            details={"user": user_name_or_id, "error": str(exc)},
        ) from exc

    results: list[TagSummary] = []
    for t in raw_tags:
        t_id = str(t.id)
        t_name = str(getattr(t, "name", t_id))
        desc = str(t.description) if getattr(t, "description", None) is not None else None
        p_id = (
            str(t.parent.id)
            if hasattr(t, "parent") and t.parent and getattr(t.parent, "id", None)
            else None
        )
        results.append(
            TagSummary(
                id=t_id,
                name=t_name,
                description=desc,
                parent_id=p_id,
            )
        )

    return results


def assign_user_tag_tool(
    user_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Assign an inventory tag to an oVirt / OLVM user.

    Args:
        user_name_or_id: Username or UUID of the user.
        tag_name_or_id: Name or UUID of the tag to assign.

    Returns:
        TagAssignmentResult with assignment outcome.
    """
    require_mutation_allowed("ovirt_user_tag_assign")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    users_svc = sys_svc.users_service()
    tags_svc = sys_svc.tags_service()

    user = client.find_resource_by_id_or_name(users_svc, user_name_or_id, "user")
    tag = client.find_resource_by_id_or_name(tags_svc, tag_name_or_id, "tag")

    user_display = str(getattr(user, "user_name", getattr(user, "name", user.id)))
    user_tags_svc = users_svc.user_service(user.id).tags_service()

    # Check if already assigned
    for t in user_tags_svc.list():
        if str(t.id) == str(tag.id):
            return TagAssignmentResult(
                success=True,
                tag_id=str(tag.id),
                tag_name=str(tag.name),
                entity_id=str(user.id),
                entity_name=user_display,
                entity_type="user",
                action="assign",
                message=f"Tag '{tag.name}' is already assigned to user '{user_display}'.",
            )

    try:
        user_tags_svc.add(sdk_types.Tag(id=tag.id))
    except Exception as exc:
        audit_log(
            "ovirt_user_tag_assign",
            str(tag.name),
            {"user": user_display, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to assign tag '{tag.name}' to user '{user_display}': {exc}",
            details={"user_id": str(user.id), "tag_id": str(tag.id), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_user_tag_assign",
        str(tag.name),
        {"user_id": str(user.id), "tag_id": str(tag.id)},
        "SUCCESS",
    )

    return TagAssignmentResult(
        success=True,
        tag_id=str(tag.id),
        tag_name=str(tag.name),
        entity_id=str(user.id),
        entity_name=user_display,
        entity_type="user",
        action="assign",
        message=f"Tag '{tag.name}' successfully assigned to user '{user_display}'.",
    )


def unassign_user_tag_tool(
    user_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Unassign an inventory tag from an oVirt / OLVM user.

    Args:
        user_name_or_id: Username or UUID of the user.
        tag_name_or_id: Name or UUID of the tag to unassign.

    Returns:
        TagAssignmentResult with unassignment outcome.
    """
    require_mutation_allowed("ovirt_user_tag_unassign")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    users_svc = sys_svc.users_service()
    tags_svc = sys_svc.tags_service()

    user = client.find_resource_by_id_or_name(users_svc, user_name_or_id, "user")
    tag = client.find_resource_by_id_or_name(tags_svc, tag_name_or_id, "tag")

    user_display = str(getattr(user, "user_name", getattr(user, "name", user.id)))
    user_tags_svc = users_svc.user_service(user.id).tags_service()

    try:
        user_tags_svc.tag_service(tag.id).remove()
    except Exception as exc:
        audit_log(
            "ovirt_user_tag_unassign",
            str(tag.name),
            {"user": user_display, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to unassign tag '{tag.name}' from user '{user_display}': {exc}",
            details={"user_id": str(user.id), "tag_id": str(tag.id), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_user_tag_unassign",
        str(tag.name),
        {"user_id": str(user.id), "tag_id": str(tag.id)},
        "SUCCESS",
    )

    return TagAssignmentResult(
        success=True,
        tag_id=str(tag.id),
        tag_name=str(tag.name),
        entity_id=str(user.id),
        entity_name=user_display,
        entity_type="user",
        action="unassign",
        message=f"Tag '{tag.name}' successfully unassigned from user '{user_display}'.",
    )
