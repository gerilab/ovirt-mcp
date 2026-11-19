"""Tools for managing oVirt / OLVM Virtual Machine Pools (VDI, on-demand pools)."""

import logging
from typing import Any

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.vm_pool import (
    VmPoolDetail,
    VmPoolResult,
    VmPoolSummary,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger(__name__)


def _clean_opt_str(val: Any) -> str | None:
    """Return string or None if unset or a mock object."""
    if val is None or not isinstance(val, str):
        return None
    return val


def _extract_pool_summary(
    pool: Any,
    cluster_names: dict[str, str] | None = None,
    template_names: dict[str, str] | None = None,
) -> VmPoolSummary:
    """Extract a typed VmPoolSummary from an oVirt SDK VmPool object."""
    pool_id = str(pool.id)
    name = str(getattr(pool, "name", pool_id))
    description = _clean_opt_str(getattr(pool, "description", None))

    cluster_obj = getattr(pool, "cluster", None)
    cluster_id = str(cluster_obj.id) if cluster_obj and getattr(cluster_obj, "id", None) else ""
    c_name = _clean_opt_str(getattr(cluster_obj, "name", None)) or (
        cluster_names.get(cluster_id) if cluster_names else None
    )

    template_obj = getattr(pool, "template", None)
    template_id = str(template_obj.id) if template_obj and getattr(template_obj, "id", None) else ""
    t_name = _clean_opt_str(getattr(template_obj, "name", None)) or (
        template_names.get(template_id) if template_names else None
    )

    size = int(getattr(pool, "size", 1) or 1)
    prestarted = int(getattr(pool, "prestarted_vms", 0) or 0)
    max_user = int(getattr(pool, "max_user_vms", 1) or 1)

    type_obj = getattr(pool, "type", None)
    type_str = str(getattr(type_obj, "value", type_obj or "automatic")).lower()
    stateful = bool(getattr(pool, "stateful", False))

    return VmPoolSummary(
        id=pool_id,
        name=name,
        description=description,
        cluster_id=cluster_id,
        cluster_name=c_name,
        template_id=template_id,
        template_name=t_name,
        size=size,
        prestarted_vms=prestarted,
        max_user_vms=max_user,
        type=type_str,
        stateful=stateful,
    )


def list_vm_pools_tool(
    cluster: str | None = None,
    search: str | None = None,
) -> list[VmPoolSummary]:
    """List Virtual Machine Pools defined across clusters in oVirt / OLVM.

    Args:
        cluster: Optional cluster name or UUID filter.
        search: Optional oVirt search query expression (e.g. 'name=desktop*').

    Returns:
        List of VmPoolSummary models.
    """
    client = get_client()
    system_service = client.get_connection().system_service()
    pools_service = system_service.vm_pools_service()
    clusters_service = system_service.clusters_service()
    templates_service = system_service.templates_service()

    # Pre-cache cluster names
    cluster_names: dict[str, str] = {}
    target_cluster_id: str | None = None
    try:
        for c in clusters_service.list():
            c_id = str(c.id)
            c_name = str(c.name)
            cluster_names[c_id] = c_name
            if cluster and (cluster.lower() in (c_name.lower(), c_id.lower())):
                target_cluster_id = c_id
    except Exception as exc:
        logger.debug("Failed caching clusters for vm pools: %s", exc)

    # Pre-cache template names
    template_names: dict[str, str] = {}
    try:
        for t in templates_service.list():
            template_names[str(t.id)] = str(t.name)
    except Exception as exc:
        logger.debug("Failed caching templates for vm pools: %s", exc)

    kwargs: dict[str, Any] = {}
    if search:
        kwargs["search"] = search.strip()

    try:
        pools = pools_service.list(**kwargs)
    except Exception as exc:
        raise OvirtMCPError(f"Failed to list VM pools: {exc}") from exc

    results: list[VmPoolSummary] = []
    for p in pools:
        summary = _extract_pool_summary(p, cluster_names, template_names)
        if target_cluster_id and summary.cluster_id != target_cluster_id:
            continue
        results.append(summary)

    return results


def get_vm_pool_tool(name_or_id: str) -> VmPoolDetail:
    """Retrieve detailed specification, size, and member VM names for a Virtual Machine Pool.

    Args:
        name_or_id: VM Pool name or UUID.

    Returns:
        VmPoolDetail with pool capacity and member VMs list.
    """
    client = get_client()
    system_service = client.get_connection().system_service()
    pools_service = system_service.vm_pools_service()
    vms_service = system_service.vms_service()

    pool = client.find_resource_by_id_or_name(pools_service, name_or_id, "vm_pool")
    summary = _extract_pool_summary(pool)

    # Resolve member VMs belonging to this pool
    vm_names: list[str] = []
    allocated_count = 0
    try:
        member_vms = vms_service.list(search=f"pool={summary.name}")
        for vm in member_vms:
            v_name = str(getattr(vm, "name", vm.id))
            vm_names.append(v_name)
            status_obj = getattr(vm, "status", None)
            status_str = str(getattr(status_obj, "value", status_obj or "")).lower()
            if status_str in ("up", "powering_up", "migrating"):
                allocated_count += 1
    except Exception as exc:
        logger.debug("Could not fetch member VMs for pool '%s': %s", summary.name, exc)

    return VmPoolDetail(
        **summary.model_dump(),
        allocated_vms_count=allocated_count,
        vms=vm_names,
    )


def create_vm_pool_tool(
    name: str,
    cluster: str,
    template: str,
    size: int = 1,
    prestarted_vms: int = 0,
    max_user_vms: int = 1,
    description: str | None = None,
    pool_type: str = "automatic",
    confirm: bool = False,
) -> VmPoolResult:
    """Create a new Virtual Machine Pool from a template on a cluster.

    Safety: Creating pools allocates compute/disk capacity and requires confirm=True in Safe Mode.

    Args:
        name: Unique name for the VM pool.
        cluster: Target Cluster name or UUID.
        template: Source Template name or UUID.
        size: Total number of VMs to provision in the pool (default: 1).
        prestarted_vms: Number of VMs kept booted and ready for instantaneous access (default: 0).
        max_user_vms: Maximum VMs a single user may acquire simultaneously (default: 1).
        description: Optional pool description.
        pool_type: 'automatic' (stateless refresh upon return) or 'manual'.
        confirm: Confirmation flag required in safe mode.

    Returns:
        VmPoolResult with creation details.
    """
    clean_name = name.strip()
    if not clean_name:
        raise OvirtValidationError("VM pool name cannot be empty.")
    if size < 1:
        raise OvirtValidationError(f"VM pool size must be at least 1, got {size}.")
    if prestarted_vms < 0 or prestarted_vms > size:
        raise OvirtValidationError(
            f"Prestarted VMs ({prestarted_vms}) must be between 0 and pool size ({size})."
        )

    require_destructive_confirmation(
        f"create VM pool '{clean_name}' (size: {size}, template: '{template}', cluster: '{cluster}')",
        confirmed=confirm,
    )

    client = get_client()
    system_service = client.get_connection().system_service()
    pools_service = system_service.vm_pools_service()
    clusters_service = system_service.clusters_service()
    templates_service = system_service.templates_service()

    cluster_obj = client.find_resource_by_id_or_name(clusters_service, cluster, "cluster")
    template_obj = client.find_resource_by_id_or_name(templates_service, template, "template")

    clean_type = pool_type.strip().lower()
    sdk_type = (
        sdk_types.VmPoolType.AUTOMATIC if clean_type == "automatic" else sdk_types.VmPoolType.MANUAL
    )

    pool_spec = sdk_types.VmPool(
        name=clean_name,
        description=description.strip() if description else None,
        cluster=sdk_types.Cluster(id=cluster_obj.id),
        template=sdk_types.Template(id=template_obj.id),
        size=size,
        prestarted_vms=prestarted_vms,
        max_user_vms=max_user_vms,
        type=sdk_type,
    )

    try:
        new_pool = pools_service.add(pool_spec)
        pool_id = str(new_pool.id)
    except Exception as exc:
        audit_log(
            "create_vm_pool",
            clean_name,
            {"cluster": cluster, "template": template, "size": size, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to create VM pool '{clean_name}': {exc}") from exc

    audit_log(
        "create_vm_pool",
        clean_name,
        {"pool_id": pool_id, "size": size, "cluster": cluster},
        "SUCCESS",
    )
    return VmPoolResult(
        success=True,
        action="create",
        pool_id=pool_id,
        pool_name=clean_name,
        message=f"VM pool '{clean_name}' successfully created with {size} virtual machine(s).",
    )


def update_vm_pool_tool(
    name_or_id: str,
    size: int | None = None,
    prestarted_vms: int | None = None,
    max_user_vms: int | None = None,
    description: str | None = None,
    confirm: bool = False,
) -> VmPoolResult:
    """Update Virtual Machine Pool capacity, prestarted standby count, or description.

    Args:
        name_or_id: VM Pool name or UUID.
        size: New total number of VMs in the pool.
        prestarted_vms: New number of prestarted standby VMs.
        max_user_vms: New maximum VMs per user.
        description: New description.
        confirm: Confirmation flag required in safe mode when altering capacity (size).

    Returns:
        VmPoolResult with outcome details.
    """
    if size is not None:
        require_destructive_confirmation(
            f"update VM pool '{name_or_id}' size to {size}", confirmed=confirm
        )
    else:
        require_mutation_allowed("update_vm_pool")

    client = get_client()
    system_service = client.get_connection().system_service()
    pools_service = system_service.vm_pools_service()

    pool = client.find_resource_by_id_or_name(pools_service, name_or_id, "vm_pool")
    pool_id = str(pool.id)
    pool_name = str(getattr(pool, "name", pool_id))
    pool_service = pools_service.pool_service(pool_id)

    update_spec = sdk_types.VmPool()
    if size is not None:
        if size < 1:
            raise OvirtValidationError(f"VM pool size must be at least 1, got {size}.")
        update_spec.size = size
    if prestarted_vms is not None:
        update_spec.prestarted_vms = prestarted_vms
    if max_user_vms is not None:
        update_spec.max_user_vms = max_user_vms
    if description is not None:
        update_spec.description = description.strip()

    try:
        pool_service.update(update_spec)
    except Exception as exc:
        audit_log("update_vm_pool", pool_name, {"pool_id": pool_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(f"Failed to update VM pool '{pool_name}': {exc}") from exc

    audit_log("update_vm_pool", pool_name, {"pool_id": pool_id, "size": size}, "SUCCESS")
    return VmPoolResult(
        success=True,
        action="update",
        pool_id=pool_id,
        pool_name=pool_name,
        message=f"VM pool '{pool_name}' successfully updated.",
    )


def delete_vm_pool_tool(
    name_or_id: str,
    confirm: bool = False,
) -> VmPoolResult:
    """Delete a Virtual Machine Pool from oVirt / OLVM.

    Protected by Safe Mode: requires confirm=True.

    Args:
        name_or_id: VM Pool name or UUID to remove.
        confirm: Confirmation flag required in safe mode.

    Returns:
        VmPoolResult with outcome details.
    """
    require_destructive_confirmation(f"delete VM pool '{name_or_id}'", confirmed=confirm)

    client = get_client()
    system_service = client.get_connection().system_service()
    pools_service = system_service.vm_pools_service()

    pool = client.find_resource_by_id_or_name(pools_service, name_or_id, "vm_pool")
    pool_id = str(pool.id)
    pool_name = str(getattr(pool, "name", pool_id))

    try:
        pools_service.pool_service(pool_id).remove()
    except Exception as exc:
        audit_log("delete_vm_pool", pool_name, {"pool_id": pool_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(f"Failed to delete VM pool '{pool_name}': {exc}") from exc

    audit_log("delete_vm_pool", pool_name, {"pool_id": pool_id}, "SUCCESS")
    return VmPoolResult(
        success=True,
        action="delete",
        pool_id=pool_id,
        pool_name=pool_name,
        message=f"VM pool '{pool_name}' successfully deleted.",
    )


def allocate_vm_pool_vm_tool(name_or_id: str) -> VmPoolResult:
    """Acquire and allocate an available virtual machine from a VM Pool for the requesting user.

    Args:
        name_or_id: VM Pool name or UUID.

    Returns:
        VmPoolResult with allocated virtual machine details.
    """
    require_mutation_allowed("allocate_vm_pool_vm")

    client = get_client()
    system_service = client.get_connection().system_service()
    pools_service = system_service.vm_pools_service()

    pool = client.find_resource_by_id_or_name(pools_service, name_or_id, "vm_pool")
    pool_id = str(pool.id)
    pool_name = str(getattr(pool, "name", pool_id))

    try:
        allocated_vm = pools_service.pool_service(pool_id).allocate_vm()
        vm_id = str(allocated_vm.id) if allocated_vm else None
        vm_name = str(getattr(allocated_vm, "name", vm_id)) if allocated_vm else None
    except Exception as exc:
        audit_log(
            "allocate_vm_pool_vm",
            pool_name,
            {"pool_id": pool_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to allocate VM from pool '{pool_name}': {exc}") from exc

    audit_log(
        "allocate_vm_pool_vm",
        pool_name,
        {"pool_id": pool_id, "vm_id": vm_id, "vm_name": vm_name},
        "SUCCESS",
    )
    return VmPoolResult(
        success=True,
        action="allocate_vm",
        pool_id=pool_id,
        pool_name=pool_name,
        allocated_vm_id=vm_id,
        allocated_vm_name=vm_name,
        message=f"Virtual machine '{vm_name}' successfully allocated from pool '{pool_name}'.",
    )
