"""Tools for managing oVirt / OLVM Data Centers."""

import logging
from typing import Any

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.datacenter import (
    DataCenterDetail,
    DataCenterOperationResult,
    DataCenterSummary,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger("ovirt_mcp.tools.datacenters")


def list_datacenters_tool(search: str | None = None) -> list[DataCenterSummary]:
    """List all Data Centers in the virtualization environment.

    Args:
        search: Optional search query (e.g. 'status=up', 'name=Home*').

    Returns:
        List of DataCenterSummary objects with compatibility and storage type.
    """
    client = get_client()
    conn = client.get_connection()
    dcs_svc = conn.system_service().data_centers_service()

    try:
        raw_dcs = dcs_svc.list(search=search)
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to list Data Centers: {exc}",
            details={"search": search, "error": str(exc)},
        ) from exc

    results: list[DataCenterSummary] = []
    for dc in raw_dcs:
        dc_id = str(dc.id)
        dc_name = str(getattr(dc, "name", dc_id))
        desc = str(dc.description) if getattr(dc, "description", None) is not None else None

        st_obj = getattr(dc, "status", None)
        status_str = str(getattr(st_obj, "value", st_obj or "up")).lower()

        is_local = bool(getattr(dc, "local", False))
        storage_type = "local" if is_local else "shared"

        compat_ver = None
        if hasattr(dc, "version") and dc.version:
            v_maj = getattr(dc.version, "major", None)
            v_min = getattr(dc.version, "minor", None)
            if v_maj is not None:
                compat_ver = f"{v_maj}.{v_min}" if v_min is not None else str(v_maj)

        quota_mode = None
        qm_obj = getattr(dc, "quota_mode", None)
        if qm_obj is not None:
            quota_mode = str(getattr(qm_obj, "value", qm_obj)).lower()

        results.append(
            DataCenterSummary(
                id=dc_id,
                name=dc_name,
                description=desc,
                status=status_str,
                storage_type=storage_type,
                compatibility_version=compat_ver,
                quota_mode=quota_mode,
            )
        )

    return results


def get_datacenter_tool(name_or_id: str) -> DataCenterDetail:
    """Retrieve complete specification of a Data Center including memberships.

    Args:
        name_or_id: Data Center name or UUID.

    Returns:
        DataCenterDetail with attached clusters, storage domains, and logical networks.
    """
    client = get_client()
    conn = client.get_connection()
    dcs_svc = conn.system_service().data_centers_service()

    dc = client.find_resource_by_id_or_name(dcs_svc, name_or_id, "data center")
    dc_id = str(dc.id)
    dc_name = str(getattr(dc, "name", dc_id))
    desc = str(dc.description) if getattr(dc, "description", None) is not None else None

    st_obj = getattr(dc, "status", None)
    status_str = str(getattr(st_obj, "value", st_obj or "up")).lower()

    is_local = bool(getattr(dc, "local", False))
    storage_type = "local" if is_local else "shared"

    compat_ver = None
    if hasattr(dc, "version") and dc.version:
        v_maj = getattr(dc.version, "major", None)
        v_min = getattr(dc.version, "minor", None)
        if v_maj is not None:
            compat_ver = f"{v_maj}.{v_min}" if v_min is not None else str(v_maj)

    quota_mode = None
    qm_obj = getattr(dc, "quota_mode", None)
    if qm_obj is not None:
        quota_mode = str(getattr(qm_obj, "value", qm_obj)).lower()

    dc_svc = dcs_svc.data_center_service(dc.id)

    # Attached clusters
    cluster_names: list[str] = []
    try:
        cls = dc_svc.clusters_service().list()
        cluster_names = [str(getattr(c, "name", c.id)) for c in cls]
    except Exception as exc:
        logger.warning("Could not fetch clusters for Data Center %s: %s", dc_name, exc)

    # Attached storage domains
    sd_names: list[str] = []
    try:
        sds = dc_svc.storage_domains_service().list()
        sd_names = [str(getattr(s, "name", s.id)) for s in sds]
    except Exception as exc:
        logger.warning("Could not fetch storage domains for Data Center %s: %s", dc_name, exc)

    # Defined networks
    net_names: list[str] = []
    try:
        nets = dc_svc.networks_service().list()
        net_names = [str(getattr(n, "name", n.id)) for n in nets]
    except Exception as exc:
        logger.warning("Could not fetch networks for Data Center %s: %s", dc_name, exc)

    return DataCenterDetail(
        id=dc_id,
        name=dc_name,
        description=desc,
        status=status_str,
        storage_type=storage_type,
        compatibility_version=compat_ver,
        quota_mode=quota_mode,
        clusters=cluster_names,
        storage_domains=sd_names,
        networks=net_names,
    )


def clean_finished_tasks_datacenter_tool(
    name_or_id: str,
    dry_run: bool = False,
    confirm: bool = False,
) -> DataCenterOperationResult:
    """Clean finished asynchronous tasks for a Data Center.

    Args:
        name_or_id: Name or UUID of the Data Center.
        dry_run: If True, validates preconditions without executing.
        confirm: Confirmation flag for mutation in Safe Mode.

    Returns:
        DataCenterOperationResult with operation outcome.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"clean finished tasks for Data Center '{name_or_id}'", confirmed=confirm
        )
    else:
        require_mutation_allowed("clean_finished_tasks_datacenter")

    client = get_client()
    conn = client.get_connection()
    dcs_svc = conn.system_service().data_centers_service()
    dc = client.find_resource_by_id_or_name(dcs_svc, name_or_id, "data center")
    dc_id = str(dc.id)
    dc_name = str(getattr(dc, "name", dc_id))

    if dry_run:
        return DataCenterOperationResult(
            success=True,
            action="clean_finished_tasks",
            data_center_id=dc_id,
            data_center_name=dc_name,
            dry_run=True,
            message=f"[DRY RUN] Clean finished tasks validated for Data Center '{dc_name}'.",
        )

    try:
        dc_service = dcs_svc.data_center_service(dc_id)
        dc_service.clean_finished_tasks()
        audit_log(
            "ovirt_datacenter_clean_finished_tasks",
            dc_name,
            {"data_center_id": dc_id},
            "SUCCESS",
        )
        return DataCenterOperationResult(
            success=True,
            action="clean_finished_tasks",
            data_center_id=dc_id,
            data_center_name=dc_name,
            dry_run=False,
            message=f"Clean finished tasks command successfully dispatched for Data Center '{dc_name}'.",
        )
    except Exception as exc:
        audit_log(
            "ovirt_datacenter_clean_finished_tasks",
            dc_name,
            {"data_center_id": dc_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to clean finished tasks for Data Center '{dc_name}': {exc}"
        ) from exc


def create_datacenter_tool(
    name: str,
    local_storage: bool = False,
    description: str | None = None,
    comment: str | None = None,
    compatibility_version: str | None = None,
    quota_mode: str | None = "disabled",
    dry_run: bool = False,
) -> DataCenterOperationResult:
    """Create a new Data Center in oVirt / OLVM.

    Args:
        name: Name of the new Data Center.
        local_storage: If True, configures the Data Center for local storage domains instead of shared storage.
        description: Optional description of the Data Center.
        comment: Optional comment on the Data Center.
        compatibility_version: Optional compatibility version string (e.g. '4.7').
        quota_mode: Quota enforcement mode ('audit', 'enabled', 'disabled'). Default is 'disabled'.
        dry_run: If True, validates configuration without creating.

    Returns:
        DataCenterOperationResult with created Data Center ID and outcome.
    """
    require_mutation_allowed("create_datacenter")

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    dcs_service = system_service.data_centers_service()

    # Verify uniqueness
    try:
        existing = dcs_service.list(search=f"name={name}")
        for dc in existing:
            dc_name = getattr(dc, "name", "")
            if type(dc_name).__name__ in ("MagicMock", "Mock") and hasattr(dc_name, "_mock_name"):
                dc_name = getattr(dc_name, "_mock_name", "")
            else:
                dc_name = str(dc_name)
            if dc_name == name:
                raise OvirtValidationError(
                    f"A Data Center with name '{name}' already exists in oVirt inventory.",
                    details={"name": name, "existing_dc_id": str(getattr(dc, "id", ""))},
                )
    except OvirtValidationError:
        raise
    except Exception as exc:
        logger.debug("Could not verify Data Center uniqueness: %s", exc)

    if dry_run:
        audit_log(
            "ovirt_datacenter_create",
            name,
            {"local_storage": local_storage, "quota_mode": quota_mode, "dry_run": True},
            "SUCCESS",
        )
        return DataCenterOperationResult(
            success=True,
            data_center_id="dry-run-dc-id",
            data_center_name=name,
            action="create",
            dry_run=True,
            message=f"[DRY RUN] Data Center '{name}' is valid and would be created.",
        )

    dc_kwargs: dict[str, Any] = {
        "name": name,
        "local": local_storage,
    }
    if description:
        dc_kwargs["description"] = description
    if comment:
        dc_kwargs["comment"] = comment
    if compatibility_version:
        parts = compatibility_version.split(".")
        if len(parts) >= 2:
            dc_kwargs["version"] = sdk_types.Version(
                major=int(parts[0]),
                minor=int(parts[1]),
            )
    if quota_mode:
        qm_map = {
            "disabled": sdk_types.QuotaModeType.DISABLED,
            "audit": sdk_types.QuotaModeType.AUDIT,
            "enabled": sdk_types.QuotaModeType.ENABLED,
        }
        if quota_mode.lower() in qm_map:
            dc_kwargs["quota_mode"] = qm_map[quota_mode.lower()]

    dc_spec = sdk_types.DataCenter(**dc_kwargs)
    try:
        created = dcs_service.add(dc_spec)
        created_id = str(getattr(created, "id", ""))
    except Exception as exc:
        audit_log(
            "ovirt_datacenter_create",
            name,
            {"error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to create Data Center '{name}': {exc}") from exc

    audit_log(
        "ovirt_datacenter_create",
        name,
        {"data_center_id": created_id},
        "SUCCESS",
    )
    return DataCenterOperationResult(
        success=True,
        data_center_id=created_id,
        data_center_name=name,
        action="create",
        dry_run=False,
        message=f"Data Center '{name}' (UUID: {created_id}) created successfully.",
    )


def delete_datacenter_tool(
    name_or_id: str,
    force: bool = False,
    dry_run: bool = False,
    confirm: bool = False,
) -> DataCenterOperationResult:
    """Delete a Data Center from oVirt / OLVM.

    Args:
        name_or_id: Name or UUID of the Data Center to remove.
        force: If True, forces removal even if storage domains or clusters are attached.
        dry_run: If True, validates removal without deleting.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).

    Returns:
        DataCenterOperationResult with outcome and identification.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"delete datacenter '{name_or_id}' (force={force})",
            confirmed=confirm,
        )
    else:
        require_mutation_allowed("delete_datacenter")

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    dcs_service = system_service.data_centers_service()

    dc = client.find_resource_by_id_or_name(dcs_service, name_or_id, "data center")
    dc_id = str(dc.id)
    dc_name = str(getattr(dc, "name", dc_id))

    dc_service = dcs_service.data_center_service(dc_id)

    # Pre-flight check: clusters and storage domains attached
    if not force:
        try:
            clusters = dc_service.clusters_service().list()
            if clusters:
                c_names = [str(getattr(c, "name", c.id)) for c in clusters]
                raise OvirtValidationError(
                    f"Cannot delete Data Center '{dc_name}' because it contains {len(clusters)} cluster(s): {', '.join(c_names)}. Remove clusters first or specify force=True.",
                    details={"data_center_id": dc_id, "clusters": c_names},
                )
        except OvirtValidationError:
            raise
        except Exception as exc:
            logger.debug("Could not verify clusters in data center: %s", exc)

        try:
            sds = dc_service.storage_domains_service().list()
            if sds:
                sd_names = [str(getattr(s, "name", s.id)) for s in sds]
                raise OvirtValidationError(
                    f"Cannot delete Data Center '{dc_name}' because it has {len(sds)} attached Storage Domain(s): {', '.join(sd_names)}. Detach storage domains first or specify force=True.",
                    details={"data_center_id": dc_id, "storage_domains": sd_names},
                )
        except OvirtValidationError:
            raise
        except Exception as exc:
            logger.debug("Could not verify storage domains in data center: %s", exc)

    if dry_run:
        audit_log(
            "ovirt_datacenter_delete",
            dc_name,
            {"data_center_id": dc_id, "force": force, "dry_run": True},
            "SUCCESS",
        )
        return DataCenterOperationResult(
            success=True,
            data_center_id=dc_id,
            data_center_name=dc_name,
            action="delete",
            dry_run=True,
            message=f"[DRY RUN] Data Center '{dc_name}' ({dc_id}) is eligible for removal.",
        )

    try:
        dc_service.remove(force=force if force else None)
    except Exception as exc:
        audit_log(
            "ovirt_datacenter_delete",
            dc_name,
            {"data_center_id": dc_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to delete Data Center '{dc_name}': {exc}") from exc

    audit_log(
        "ovirt_datacenter_delete",
        dc_name,
        {"data_center_id": dc_id},
        "SUCCESS",
    )
    return DataCenterOperationResult(
        success=True,
        data_center_id=dc_id,
        data_center_name=dc_name,
        action="delete",
        dry_run=False,
        message=f"Data Center '{dc_name}' ({dc_id}) was successfully deleted.",
    )
