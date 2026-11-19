"""Tools for managing oVirt / OLVM user accounts, roles, and authorization permissions."""

import logging
from typing import Any

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.user import (
    PermissionResult,
    PermissionSummary,
    RoleSummary,
    UserDetail,
    UserResult,
    UserSummary,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger(__name__)


def _clean_opt_str(val: Any) -> str | None:
    """Safely convert an optional attribute to a clean string or None."""
    if val is None or type(val).__name__ == "MagicMock":
        return None
    s = str(val).strip()
    return s if s else None


def _extract_user_summary(user: Any) -> UserSummary:
    """Extract a typed UserSummary from an oVirt SDK User object."""
    user_id = str(user.id)
    raw_name = _clean_opt_str(getattr(user, "name", None))
    raw_user_name = _clean_opt_str(getattr(user, "user_name", None))
    principal = _clean_opt_str(getattr(user, "principal", None))

    user_name = raw_user_name or principal or user_id
    name = raw_name or principal or raw_user_name or user_id

    domain_obj = getattr(user, "domain", None)
    domain_name = _clean_opt_str(getattr(domain_obj, "name", None)) if domain_obj else None
    email = _clean_opt_str(getattr(user, "email", None))
    department = _clean_opt_str(getattr(user, "department", None))
    logged_in = bool(getattr(user, "logged_in", False))

    return UserSummary(
        id=user_id,
        name=name,
        user_name=user_name,
        principal=principal,
        domain_name=domain_name,
        email=email,
        department=department,
        logged_in=logged_in,
    )


def list_users_tool(
    search: str | None = None,
    max_results: int = 100,
) -> list[UserSummary]:
    """List users registered in the oVirt / OLVM engine across authorization domains.

    Args:
        search: Optional oVirt search query (e.g. 'usrname = admin*').
        max_results: Maximum number of users to return (default: 100).

    Returns:
        List of UserSummary models.
    """
    client = get_client()
    system_service = client.get_connection().system_service()
    users_service = system_service.users_service()

    kwargs: dict[str, Any] = {"max": max_results}
    if search:
        kwargs["search"] = search.strip()

    try:
        users = users_service.list(**kwargs)
    except Exception as exc:
        raise OvirtMCPError(f"Failed to list users: {exc}") from exc

    return [_extract_user_summary(u) for u in users]


def get_user_tool(name_or_id: str) -> UserDetail:
    """Retrieve detailed user account information, assigned roles, and permission counts.

    Args:
        name_or_id: Username or UUID of the user.

    Returns:
        UserDetail with role memberships and permission count.
    """
    client = get_client()
    system_service = client.get_connection().system_service()
    users_service = system_service.users_service()

    user = client.find_resource_by_id_or_name(users_service, name_or_id, "user")
    summary = _extract_user_summary(user)

    user_service = users_service.user_service(summary.id)

    # Fetch assigned roles
    role_names: list[str] = []
    try:
        roles = user_service.roles_service().list()
        role_names = [r.name for r in roles if getattr(r, "name", None)]
    except Exception as exc:
        logger.debug("Could not fetch roles for user '%s': %s", summary.user_name, exc)

    # Fetch permissions count
    perms_count = 0
    try:
        perms = user_service.permissions_service().list()
        perms_count = len(perms)
    except Exception as exc:
        logger.debug("Could not fetch permissions for user '%s': %s", summary.user_name, exc)

    return UserDetail(
        **summary.model_dump(),
        roles=role_names,
        permissions_count=perms_count,
    )


def add_user_tool(
    user_name: str,
    domain: str,
    principal: str | None = None,
) -> UserResult:
    """Import and register a user from an authorization provider / directory service into oVirt.

    Enterprise Best Practice:
      Allows provisioning dedicated, least-privilege service accounts (e.g. 'mcp-service@internal-authz')
      instead of operating under unrestricted root credentials.

    Args:
        user_name: Username in the authorization directory (e.g. 'mcp-service' or 'mcp-user@internal-authz').
        domain: Authorization domain / realm name (e.g. 'internal-authz', 'internal', or corporate LDAP realm).
        principal: Optional User Principal Name (UPN) without realm for Active Directory compatibility.

    Returns:
        UserResult with outcome details.
    """
    require_mutation_allowed("add_user")

    clean_user = user_name.strip()
    clean_domain = domain.strip()

    # Normalize full username with domain if not already suffixed
    full_username = f"{clean_user}@{clean_domain}" if "@" not in clean_user else clean_user

    client = get_client()
    system_service = client.get_connection().system_service()
    users_service = system_service.users_service()

    user_spec = sdk_types.User(
        user_name=full_username,
        domain=sdk_types.Domain(name=clean_domain),
    )
    if principal:
        user_spec.principal = principal.strip()

    try:
        new_user = users_service.add(user_spec)
        user_id = str(new_user.id)
    except Exception as exc:
        audit_log("add_user", full_username, {"domain": clean_domain, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(f"Failed to add user '{full_username}': {exc}") from exc

    audit_log("add_user", full_username, {"user_id": user_id, "domain": clean_domain}, "SUCCESS")
    return UserResult(
        success=True,
        action="add",
        user_id=user_id,
        user_name=full_username,
        message=f"User '{full_username}' successfully registered into oVirt from domain '{clean_domain}'.",
    )


def delete_user_tool(
    name_or_id: str,
    confirm: bool = False,
) -> UserResult:
    """De-register and remove a user account from the oVirt / OLVM engine.

    Safety Guards:
      1. Safe-Mode Protection: Requires confirm=True when MCP_SAFE_MODE=true.
      2. Lockout Guard: Strictly prohibits deleting primary root administrator accounts ('admin@*').

    Args:
        name_or_id: Username or UUID of the user to remove.
        confirm: Confirmation flag required in safe mode.

    Returns:
        UserResult with outcome details.
    """
    require_destructive_confirmation(f"delete user account '{name_or_id}'", confirmed=confirm)

    client = get_client()
    system_service = client.get_connection().system_service()
    users_service = system_service.users_service()

    user = client.find_resource_by_id_or_name(users_service, name_or_id, "user")
    user_id = str(user.id)
    user_name = str(getattr(user, "user_name", getattr(user, "name", user_id)))

    # ── Enterprise Lockout Guard ──────────────────────────────────────────────
    if "admin@" in user_name.lower():
        raise OvirtValidationError(
            f"Safety Guard: Deleting root administrative account '{user_name}' is strictly prohibited "
            "to prevent permanent engine management lockout.",
            details={"user_id": user_id, "user_name": user_name},
        )

    try:
        users_service.user_service(user_id).remove()
    except Exception as exc:
        audit_log("delete_user", user_name, {"user_id": user_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(f"Failed to delete user '{user_name}': {exc}") from exc

    audit_log("delete_user", user_name, {"user_id": user_id}, "SUCCESS")
    return UserResult(
        success=True,
        action="delete",
        user_id=user_id,
        user_name=user_name,
        message=f"User '{user_name}' successfully removed from oVirt engine.",
    )


def list_roles_tool(
    administrative: bool | None = None,
) -> list[RoleSummary]:
    """List authorization roles defined in oVirt / OLVM.

    Args:
        administrative: Optional filter: True for administrator roles, False for user roles.

    Returns:
        List of RoleSummary models.
    """
    client = get_client()
    system_service = client.get_connection().system_service()
    roles_service = system_service.roles_service()

    try:
        roles = roles_service.list()
    except Exception as exc:
        raise OvirtMCPError(f"Failed to list roles: {exc}") from exc

    results: list[RoleSummary] = []
    for r in roles:
        is_admin = bool(getattr(r, "administrative", False))
        if administrative is not None and is_admin != administrative:
            continue
        results.append(
            RoleSummary(
                id=str(r.id),
                name=str(r.name),
                description=getattr(r, "description", None),
                administrative=is_admin,
                mutable=bool(getattr(r, "mutable", False)),
            )
        )

    return results


def list_permissions_tool(
    user_name_or_id: str | None = None,
    role_name_or_id: str | None = None,
) -> list[PermissionSummary]:
    """List authorization permissions granted to users across the virtualization environment.

    Args:
        user_name_or_id: Optional user display name or UUID to inspect permissions for a single user.
        role_name_or_id: Optional role name (e.g. 'SuperUser', 'PowerUserRole') or UUID filter.

    Returns:
        List of PermissionSummary models.
    """
    client = get_client()
    system_service = client.get_connection().system_service()
    users_service = system_service.users_service()
    roles_service = system_service.roles_service()

    # Pre-cache roles by ID to avoid N+1 queries
    role_names_by_id: dict[str, str] = {}
    target_role_id: str | None = None
    try:
        for r in roles_service.list():
            r_id = str(r.id)
            r_name = str(r.name)
            role_names_by_id[r_id] = r_name
            if role_name_or_id and (
                role_name_or_id.lower() == r_name.lower() or role_name_or_id == r_id
            ):
                target_role_id = r_id
    except Exception as exc:
        logger.debug("Failed to cache role names: %s", exc)

    # Determine permissions service to query
    target_user_name: str | None = None
    target_user_id: str | None = None
    if user_name_or_id:
        user = client.find_resource_by_id_or_name(users_service, user_name_or_id, "user")
        target_user_id = str(user.id)
        target_user_name = str(getattr(user, "user_name", getattr(user, "name", target_user_id)))
        perms_service = users_service.user_service(target_user_id).permissions_service()
    else:
        perms_service = system_service.permissions_service()

    try:
        perms = perms_service.list()
    except Exception as exc:
        raise OvirtMCPError(f"Failed to list permissions: {exc}") from exc

    results: list[PermissionSummary] = []
    for p in perms:
        perm_id = str(p.id)
        role_obj = getattr(p, "role", None)
        r_id = str(role_obj.id) if role_obj and getattr(role_obj, "id", None) else ""
        if target_role_id and r_id != target_role_id:
            continue

        r_name = role_names_by_id.get(r_id, r_id)

        # User resolution
        user_obj = getattr(p, "user", None)
        u_id = (
            str(user_obj.id)
            if user_obj and getattr(user_obj, "id", None)
            else (target_user_id or None)
        )
        u_name = _clean_opt_str(getattr(user_obj, "name", None)) or target_user_name

        # Resolve target entity
        target_type = "system"
        target_name: str | None = None
        target_id: str | None = None

        vm_obj = getattr(p, "vm", None)
        cluster_obj = getattr(p, "cluster", None)
        dc_obj = getattr(p, "data_center", None)
        sd_obj = getattr(p, "storage_domain", None)

        if vm_obj is not None and getattr(vm_obj, "id", None) is not None:
            target_type = "vm"
            target_id = str(vm_obj.id)
            target_name = _clean_opt_str(getattr(vm_obj, "name", None)) or target_id
        elif cluster_obj is not None and getattr(cluster_obj, "id", None) is not None:
            target_type = "cluster"
            target_id = str(cluster_obj.id)
            target_name = _clean_opt_str(getattr(cluster_obj, "name", None)) or target_id
        elif dc_obj is not None and getattr(dc_obj, "id", None) is not None:
            target_type = "data_center"
            target_id = str(dc_obj.id)
            target_name = _clean_opt_str(getattr(dc_obj, "name", None)) or target_id
        elif sd_obj is not None and getattr(sd_obj, "id", None) is not None:
            target_type = "storage_domain"
            target_id = str(sd_obj.id)
            target_name = _clean_opt_str(getattr(sd_obj, "name", None)) or target_id

        results.append(
            PermissionSummary(
                id=perm_id,
                user_id=u_id,
                user_name=u_name,
                role_id=r_id,
                role_name=r_name,
                target_type=target_type,
                target_id=target_id,
                target_name=target_name,
            )
        )

    return results


def add_permission_tool(
    user_name_or_id: str,
    role_name_or_id: str,
    target_type: str = "system",
    target_name_or_id: str | None = None,
    confirm: bool = False,
) -> PermissionResult:
    """Grant an authorization role to a user on a target entity or system-wide.

    Enterprise Safety Matrix:
      1. Role Grant Gate: Granting high-privilege administrative roles ('SuperUser', 'DataCenterAdmin',
         'ClusterAdmin') modifies enterprise security posture and strictly requires confirm=True in Safe Mode.
      2. Entity Resolution: Verifies target entity existence upfront (Data Center, Cluster, VM, Storage Domain).

    Args:
        user_name_or_id: Username or UUID of the target user.
        role_name_or_id: Name or UUID of the role to assign (e.g. 'UserRole', 'PowerUserRole', 'SuperUser').
        target_type: Target entity type: 'system', 'data_center', 'cluster', 'vm', or 'storage_domain'.
        target_name_or_id: Display name or UUID of target entity (None when target_type='system').
        confirm: Confirmation flag required in safe mode when granting administrative roles.

    Returns:
        PermissionResult with outcome details.
    """
    clean_target_type = target_type.strip().lower()
    valid_types = ("system", "data_center", "cluster", "vm", "storage_domain")
    if clean_target_type not in valid_types:
        raise OvirtValidationError(
            f"Invalid target_type '{target_type}'. Valid options are: {', '.join(valid_types)}."
        )

    client = get_client()
    system_service = client.get_connection().system_service()
    users_service = system_service.users_service()
    roles_service = system_service.roles_service()

    # Find user and role
    user = client.find_resource_by_id_or_name(users_service, user_name_or_id, "user")
    user_id = str(user.id)
    user_name = str(getattr(user, "user_name", getattr(user, "name", user_id)))

    role = client.find_resource_by_id_or_name(roles_service, role_name_or_id, "role")
    role_id = str(role.id)
    role_name = str(role.name)
    is_admin_role = bool(getattr(role, "administrative", False)) or role_name.lower() in (
        "superuser",
        "datacenteradmin",
        "clusteradmin",
    )

    # ── Enterprise Safe Mode Gate ──────────────────────────────────────────────
    if is_admin_role:
        require_destructive_confirmation(
            f"grant high-privilege administrative role '{role_name}' to user '{user_name}'",
            confirmed=confirm,
        )
    else:
        require_mutation_allowed("add_permission")

    # Resolve target entity kwargs
    target_kwargs: dict[str, Any] = {}
    resolved_target_name: str | None = None

    if clean_target_type == "data_center":
        if not target_name_or_id:
            raise OvirtValidationError(
                "target_name_or_id is required when target_type='data_center'."
            )
        dc = client.find_resource_by_id_or_name(
            system_service.data_centers_service(), target_name_or_id, "data_center"
        )
        target_kwargs["data_center"] = sdk_types.DataCenter(id=dc.id)
        resolved_target_name = str(dc.name)
    elif clean_target_type == "cluster":
        if not target_name_or_id:
            raise OvirtValidationError("target_name_or_id is required when target_type='cluster'.")
        cluster = client.find_resource_by_id_or_name(
            system_service.clusters_service(), target_name_or_id, "cluster"
        )
        target_kwargs["cluster"] = sdk_types.Cluster(id=cluster.id)
        resolved_target_name = str(cluster.name)
    elif clean_target_type == "vm":
        if not target_name_or_id:
            raise OvirtValidationError("target_name_or_id is required when target_type='vm'.")
        vm = client.find_resource_by_id_or_name(
            system_service.vms_service(), target_name_or_id, "vm"
        )
        target_kwargs["vm"] = sdk_types.Vm(id=vm.id)
        resolved_target_name = str(vm.name)
    elif clean_target_type == "storage_domain":
        if not target_name_or_id:
            raise OvirtValidationError(
                "target_name_or_id is required when target_type='storage_domain'."
            )
        sd = client.find_resource_by_id_or_name(
            system_service.storage_domains_service(), target_name_or_id, "storage_domain"
        )
        target_kwargs["storage_domain"] = sdk_types.StorageDomain(id=sd.id)
        resolved_target_name = str(sd.name)

    perm_spec = sdk_types.Permission(
        user=sdk_types.User(id=user_id),
        role=sdk_types.Role(id=role_id),
        **target_kwargs,
    )

    try:
        new_perm = system_service.permissions_service().add(perm_spec)
        perm_id = str(new_perm.id)
    except Exception as exc:
        audit_log(
            "add_permission",
            user_name,
            {"role": role_name, "target_type": clean_target_type, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to grant role '{role_name}' to user '{user_name}': {exc}"
        ) from exc

    target_desc = (
        f" on {clean_target_type} '{resolved_target_name}'"
        if resolved_target_name
        else " system-wide"
    )
    msg = f"Role '{role_name}' successfully granted to user '{user_name}'{target_desc}."
    audit_log(
        "add_permission",
        user_name,
        {"role": role_name, "permission_id": perm_id, "target_type": clean_target_type},
        "SUCCESS",
    )

    return PermissionResult(
        success=True,
        action="add",
        permission_id=perm_id,
        user_name=user_name,
        role_name=role_name,
        target_type=clean_target_type,
        target_name=resolved_target_name,
        message=msg,
    )


def remove_permission_tool(
    permission_id: str,
    confirm: bool = False,
) -> PermissionResult:
    """Revoke and delete an authorization permission grant from oVirt / OLVM.

    Destructive security action in Safe Mode: requires confirm=True.

    Args:
        permission_id: UUID of the permission grant to revoke.
        confirm: Confirmation flag required in safe mode.

    Returns:
        PermissionResult with outcome details.
    """
    clean_perm_id = permission_id.strip()
    require_destructive_confirmation(
        f"revoke permission grant '{clean_perm_id}'", confirmed=confirm
    )

    client = get_client()
    system_service = client.get_connection().system_service()
    perms_service = system_service.permissions_service()

    try:
        perm_service = perms_service.permission_service(clean_perm_id)
        perm = perm_service.get()
        role_name = getattr(getattr(perm, "role", None), "name", "UnknownRole")
        user_name = getattr(getattr(perm, "user", None), "name", "UnknownUser")
    except Exception:
        role_name = "UnknownRole"
        user_name = "UnknownUser"

    try:
        perms_service.permission_service(clean_perm_id).remove()
    except Exception as exc:
        audit_log("remove_permission", clean_perm_id, {"error": str(exc)}, "FAILED")
        raise OvirtMCPError(f"Failed to revoke permission '{clean_perm_id}': {exc}") from exc

    audit_log(
        "remove_permission",
        clean_perm_id,
        {"user": user_name, "role": role_name},
        "SUCCESS",
    )
    return PermissionResult(
        success=True,
        action="remove",
        permission_id=clean_perm_id,
        user_name=user_name,
        role_name=role_name,
        target_type="unknown",
        target_name=None,
        message=f"Permission grant '{clean_perm_id}' (role: '{role_name}', user: '{user_name}') successfully revoked.",
    )
