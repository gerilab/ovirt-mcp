"""Tools for managing oVirt / OLVM Quotas and resource ceilings."""

import contextlib
import logging

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.quota import (
    QuotaClusterLimit,
    QuotaDetail,
    QuotaResult,
    QuotaStorageLimit,
    QuotaSummary,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger("ovirt_mcp.tools.quotas")


def list_quotas_tool(data_center: str | None = None) -> list[QuotaSummary]:
    """List quotas across Data Centers or within a specific Data Center.

    Args:
        data_center: Optional Data Center name or UUID to filter quotas.

    Returns:
        List of QuotaSummary objects with parent Data Center information.
    """
    client = get_client()
    conn = client.get_connection()
    dcs_svc = conn.system_service().data_centers_service()

    target_dcs = []
    if data_center:
        target_dc = client.find_resource_by_id_or_name(dcs_svc, data_center, "data center")
        target_dcs.append(target_dc)
    else:
        target_dcs = dcs_svc.list()

    results: list[QuotaSummary] = []
    for dc in target_dcs:
        dc_id = str(dc.id)
        dc_name = str(getattr(dc, "name", dc_id))
        dc_svc = dcs_svc.data_center_service(dc.id)

        try:
            quotas = dc_svc.quotas_service().list()
            for q in quotas:
                results.append(
                    QuotaSummary(
                        id=str(q.id),
                        name=str(getattr(q, "name", q.id)),
                        description=(
                            str(q.description)
                            if getattr(q, "description", None) is not None
                            else None
                        ),
                        data_center_id=dc_id,
                        data_center_name=dc_name,
                    )
                )
        except Exception as exc:
            logger.warning("Could not list quotas for Data Center %s: %s", dc_name, exc)

    return results


def get_quota_tool(name_or_id: str, data_center: str | None = None) -> QuotaDetail:
    """Retrieve detailed compute and storage limits for a specific quota.

    Args:
        name_or_id: Quota name or UUID.
        data_center: Optional Data Center name or UUID scoping the search.

    Returns:
        QuotaDetail with cluster and storage limits.
    """
    client = get_client()
    conn = client.get_connection()
    dcs_svc = conn.system_service().data_centers_service()

    target_dcs = []
    if data_center:
        target_dc = client.find_resource_by_id_or_name(dcs_svc, data_center, "data center")
        target_dcs.append(target_dc)
    else:
        target_dcs = dcs_svc.list()

    found_quota = None
    parent_dc = None
    for dc in target_dcs:
        dc_svc = dcs_svc.data_center_service(dc.id)
        quotas_svc = dc_svc.quotas_service()
        try:
            # Try by id first
            q = quotas_svc.quota_service(name_or_id).get()
            found_quota = q
            parent_dc = dc
            break
        except Exception:
            pass

        # Try by name in this DC
        try:
            qs = quotas_svc.list()
            for q in qs:
                if str(getattr(q, "name", "")).lower() == name_or_id.lower():
                    found_quota = q
                    parent_dc = dc
                    break
            if found_quota:
                break
        except Exception:
            pass

    if not found_quota or not parent_dc:
        raise OvirtValidationError(
            f"Quota '{name_or_id}' not found.",
            details={"name_or_id": name_or_id, "data_center": data_center},
        )

    q_svc = dcs_svc.data_center_service(parent_dc.id).quotas_service().quota_service(found_quota.id)

    # Cluster limits
    cl_limits: list[QuotaClusterLimit] = []
    try:
        raw_cls = q_svc.quota_cluster_limits_service().list()
        for cl in raw_cls:
            cl_id = str(cl.cluster.id) if hasattr(cl, "cluster") and cl.cluster else None
            cl_name = (
                str(cl.cluster.name)
                if hasattr(cl, "cluster") and cl.cluster and hasattr(cl.cluster, "name")
                else None
            )
            vcpu = getattr(cl, "vcpu_limit", None)
            mem_raw = getattr(cl, "memory_limit", None)
            mem_gb = float(mem_raw) if mem_raw is not None else None
            cl_limits.append(
                QuotaClusterLimit(
                    id=str(cl.id),
                    cluster_id=cl_id,
                    cluster_name=cl_name,
                    vcpu_limit=vcpu,
                    memory_limit_gb=mem_gb,
                )
            )
    except Exception as exc:
        logger.warning("Could not fetch cluster limits for quota %s: %s", found_quota.name, exc)

    # Storage limits
    st_limits: list[QuotaStorageLimit] = []
    try:
        raw_sls = q_svc.quota_storage_limits_service().list()
        for sl in raw_sls:
            sd_id = (
                str(sl.storage_domain.id)
                if hasattr(sl, "storage_domain") and sl.storage_domain
                else None
            )
            sd_name = (
                str(sl.storage_domain.name)
                if hasattr(sl, "storage_domain")
                and sl.storage_domain
                and hasattr(sl.storage_domain, "name")
                else None
            )
            lim_raw = getattr(sl, "limit", None)
            lim_gb = float(lim_raw) if lim_raw is not None else None
            st_limits.append(
                QuotaStorageLimit(
                    id=str(sl.id),
                    storage_domain_id=sd_id,
                    storage_domain_name=sd_name,
                    limit_gb=lim_gb,
                )
            )
    except Exception as exc:
        logger.warning("Could not fetch storage limits for quota %s: %s", found_quota.name, exc)

    return QuotaDetail(
        id=str(found_quota.id),
        name=str(found_quota.name),
        description=(
            str(found_quota.description)
            if getattr(found_quota, "description", None) is not None
            else None
        ),
        data_center_id=str(parent_dc.id),
        data_center_name=str(parent_dc.name),
        cluster_limits=cl_limits,
        storage_limits=st_limits,
    )


def create_quota_tool(
    name: str,
    data_center: str,
    description: str | None = None,
) -> QuotaResult:
    """Create a new resource quota under a designated Data Center.

    Args:
        name: Name for the new quota.
        data_center: Name or UUID of the parent Data Center.
        description: Optional descriptive notes.

    Returns:
        QuotaResult with creation outcome.
    """
    require_mutation_allowed("ovirt_quota_create")

    name = name.strip()
    if not name:
        raise OvirtValidationError("Quota name cannot be empty.")

    client = get_client()
    conn = client.get_connection()
    dcs_svc = conn.system_service().data_centers_service()

    dc = client.find_resource_by_id_or_name(dcs_svc, data_center, "data center")
    dc_svc = dcs_svc.data_center_service(dc.id)
    quotas_svc = dc_svc.quotas_service()

    # Collision guard
    existing = quotas_svc.list()
    for q in existing:
        if str(getattr(q, "name", "")).lower() == name.lower():
            raise OvirtValidationError(
                f"A quota named '{name}' already exists in Data Center '{dc.name}'.",
                details={"quota_name": name, "data_center": str(dc.name)},
            )

    try:
        created = quotas_svc.add(
            sdk_types.Quota(
                name=name,
                description=description,
            )
        )
        q_id = str(created.id)
    except Exception as exc:
        audit_log(
            "ovirt_quota_create",
            name,
            {"data_center": str(dc.name), "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to create quota '{name}' in Data Center '{dc.name}': {exc}",
            details={"quota_name": name, "data_center": str(dc.name), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_quota_create",
        name,
        {"quota_id": q_id, "data_center": str(dc.name)},
        "SUCCESS",
    )

    return QuotaResult(
        success=True,
        quota_id=q_id,
        quota_name=name,
        data_center_name=str(dc.name),
        action="create",
        message=f"Quota '{name}' successfully created in Data Center '{dc.name}'.",
    )


def delete_quota_tool(
    name_or_id: str,
    data_center: str,
    confirm: bool = False,
) -> QuotaResult:
    """Delete a quota from a Data Center.

    Protected by safe-mode confirmation. The system Default quota cannot be deleted.

    Args:
        name_or_id: Quota name or UUID.
        data_center: Name or UUID of the parent Data Center.
        confirm: Confirmation flag required in safe-mode.

    Returns:
        QuotaResult with deletion outcome.
    """
    require_destructive_confirmation("ovirt_quota_delete", confirm)
    require_mutation_allowed("ovirt_quota_delete")

    client = get_client()
    conn = client.get_connection()
    dcs_svc = conn.system_service().data_centers_service()

    dc = client.find_resource_by_id_or_name(dcs_svc, data_center, "data center")
    dc_svc = dcs_svc.data_center_service(dc.id)
    quotas_svc = dc_svc.quotas_service()

    # Find quota
    target_q = None
    with contextlib.suppress(Exception):
        target_q = quotas_svc.quota_service(name_or_id).get()

    if not target_q:
        for q in quotas_svc.list():
            if str(getattr(q, "name", "")).lower() == name_or_id.lower():
                target_q = q
                break

    if not target_q:
        raise OvirtValidationError(
            f"Quota '{name_or_id}' not found in Data Center '{dc.name}'.",
            details={"quota": name_or_id, "data_center": str(dc.name)},
        )

    q_id = str(target_q.id)
    q_name = str(getattr(target_q, "name", q_id))

    # Guard: Default quota cannot be deleted
    if q_name.lower() == "default":
        raise OvirtValidationError(
            f"Cannot delete system Default quota in Data Center '{dc.name}'.",
            details={"quota_id": q_id, "data_center": str(dc.name)},
        )

    try:
        quotas_svc.quota_service(q_id).remove()
    except Exception as exc:
        audit_log(
            "ovirt_quota_delete",
            q_name,
            {"quota_id": q_id, "data_center": str(dc.name), "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to delete quota '{q_name}' ({q_id}) in Data Center '{dc.name}': {exc}",
            details={"quota_id": q_id, "data_center": str(dc.name), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_quota_delete",
        q_name,
        {"quota_id": q_id, "data_center": str(dc.name)},
        "SUCCESS",
    )

    return QuotaResult(
        success=True,
        quota_id=q_id,
        quota_name=q_name,
        data_center_name=str(dc.name),
        action="delete",
        message=f"Quota '{q_name}' successfully deleted from Data Center '{dc.name}'.",
    )
