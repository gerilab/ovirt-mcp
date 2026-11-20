"""Storage Domain management tools for oVirt / OLVM."""

import contextlib
import logging
from typing import Any

from ovirtsdk4 import types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.models.storage import (
    StorageDomainDetail,
    StorageDomainIoStats,
    StorageDomainResult,
    StorageDomainSummary,
    StorageDomainTopDiskIo,
)
from ovirt_mcp.tools.disks import extract_disk_io_stats
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger("ovirt_mcp.tools.storage")


def _bytes_to_gb(byte_val: Any) -> float:
    """Safely convert bytes to gigabytes rounded to 2 decimal places."""
    if byte_val is None:
        return 0.0
    try:
        return round(float(byte_val) / (1024**3), 2)
    except (ValueError, TypeError):
        return 0.0


def _build_storage_domain_summary(
    sd: Any,
    dc_map: dict[str, list[str]],
    dc_status_map: dict[str, str],
) -> StorageDomainSummary:
    """Build StorageDomainSummary from an SDK StorageDomain object."""
    avail_gb = _bytes_to_gb(getattr(sd, "available", None))
    used_gb = _bytes_to_gb(getattr(sd, "used", None))
    comm_gb = _bytes_to_gb(getattr(sd, "committed", None))
    total_gb = round(avail_gb + used_gb, 2)
    usage_pct = round((used_gb / total_gb) * 100, 1) if total_gb > 0 else 0.0

    sd_id = str(sd.id)
    attached_dcs = dc_map.get(sd_id, [])

    # Determine status: check DC status if attached, or unattached
    status_str = dc_status_map.get(sd_id)
    if not status_str:
        if getattr(sd, "status", None):
            status_str = str(sd.status)
        else:
            status_str = "attached" if attached_dcs else "unattached"

    storage_type_str = "unknown"
    addr_str: str | None = None
    path_str: str | None = None
    target_str: str | None = None

    if getattr(sd, "storage", None):
        st = sd.storage
        if getattr(st, "type", None):
            storage_type_str = str(st.type).lower()
        addr_str = str(st.address) if getattr(st, "address", None) else None
        path_str = str(st.path) if getattr(st, "path", None) else None
        target_str = str(st.target) if getattr(st, "target", None) else None

    format_str: str | None = None
    if getattr(sd, "storage_format", None):
        format_str = str(sd.storage_format).lower()

    overcommit_ratio = round(comm_gb / total_gb, 2) if total_gb > 0 and comm_gb is not None else 0.0

    warn_ind = getattr(sd, "warning_low_space_indicator", None)
    crit_block = getattr(sd, "critical_space_action_blocker", None)
    space_health = "ok"
    if crit_block is not None and avail_gb <= float(crit_block):
        space_health = "critical_space"
    elif (
        warn_ind is not None and total_gb > 0 and ((avail_gb / total_gb) * 100.0) <= float(warn_ind)
    ):
        space_health = "warning_low_space"

    return StorageDomainSummary(
        id=sd_id,
        name=str(sd.name),
        type=str(sd.type).lower() if getattr(sd, "type", None) else "data",
        storage_type=storage_type_str,
        status=status_str.lower(),
        available_gb=avail_gb,
        used_gb=used_gb,
        committed_gb=comm_gb,
        total_gb=total_gb,
        usage_percent=usage_pct,
        overcommit_ratio=overcommit_ratio,
        space_health=space_health,
        storage_format=format_str,
        address=addr_str,
        path=path_str,
        target=target_str,
        data_centers=attached_dcs,
    )


# =========================================================================
# 1. Storage Domain Inspection
# =========================================================================


def ovirt_storage_domain_list() -> list[StorageDomainSummary]:
    """List all Storage Domains in oVirt / OLVM with capacity and status.

    Returns:
        List of StorageDomainSummary objects including type, protocol, capacity in GB,
        usage percent, and attached Data Centers.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    sds_svc = sys_svc.storage_domains_service()

    # Pre-fetch Data Centers to map domain attachments and statuses
    dc_map: dict[str, list[str]] = {}
    dc_status_map: dict[str, str] = {}
    try:
        dcs = sys_svc.data_centers_service().list()
        for dc in dcs:
            dc_svc = sys_svc.data_centers_service().data_center_service(dc.id)
            attached = dc_svc.storage_domains_service().list()
            for a in attached:
                a_id = str(a.id)
                dc_map.setdefault(a_id, []).append(str(dc.name))
                if getattr(a, "status", None):
                    dc_status_map[a_id] = str(a.status)
    except Exception as e:
        logger.debug("Failed querying Data Centers for storage domain attachments: %s", e)

    domains = sds_svc.list()
    result: list[StorageDomainSummary] = []

    for sd in domains:
        result.append(_build_storage_domain_summary(sd, dc_map, dc_status_map))

    return result


def ovirt_storage_domain_get(name_or_id: str) -> StorageDomainDetail:
    """Get deep configuration, thresholds, and object counts for a Storage Domain.

    Args:
        name_or_id: Display name or UUID of the storage domain.

    Returns:
        StorageDomainDetail object.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    sds_svc = sys_svc.storage_domains_service()

    sd = client.find_resource_by_id_or_name(sds_svc, name_or_id, "storage_domain")
    sd_svc = sds_svc.storage_domain_service(sd.id)
    sd_detail = sd_svc.get()

    # Build basic summary
    dc_map: dict[str, list[str]] = {}
    dc_status_map: dict[str, str] = {}
    try:
        dcs = sys_svc.data_centers_service().list()
        for dc in dcs:
            dc_svc = sys_svc.data_centers_service().data_center_service(dc.id)
            attached = dc_svc.storage_domains_service().list()
            for a in attached:
                a_id = str(a.id)
                dc_map.setdefault(a_id, []).append(str(dc.name))
                if getattr(a, "status", None):
                    dc_status_map[a_id] = str(a.status)
    except Exception as e:
        logger.debug("Failed querying Data Centers: %s", e)

    summary = _build_storage_domain_summary(sd_detail, dc_map, dc_status_map)

    # Count disks and calculate aggregate real-time I/O telemetry
    disks_count = 0
    top_io_disks: list[StorageDomainTopDiskIo] = []
    tot_read_bytes = 0.0
    tot_write_bytes = 0.0
    tot_read_mb = 0.0
    tot_write_mb = 0.0
    tot_read_iops = 0.0
    tot_write_iops = 0.0
    read_latencies: list[float] = []
    write_latencies: list[float] = []
    active_disks_count = 0

    try:
        sd_disks = sd_svc.disks_service().list()
        disks_count = len(sd_disks)
        disks_service = sys_svc.disks_service()
        for d in sd_disks:
            d_id = str(getattr(d, "id", ""))
            d_name = str(getattr(d, "name", None) or d_id)
            d_io = None
            with contextlib.suppress(Exception):
                d_io = extract_disk_io_stats(disks_service.disk_service(d_id))

            if d_io:
                active_disks_count += 1
                tot_read_bytes += d_io.read_bytes_sec
                tot_write_bytes += d_io.write_bytes_sec
                tot_read_mb += d_io.read_mb_sec
                tot_write_mb += d_io.write_mb_sec
                tot_read_iops += d_io.read_iops
                tot_write_iops += d_io.write_iops
                if d_io.read_latency_ms > 0:
                    read_latencies.append(d_io.read_latency_ms)
                if d_io.write_latency_ms > 0:
                    write_latencies.append(d_io.write_latency_ms)

                top_io_disks.append(
                    StorageDomainTopDiskIo(
                        disk_id=d_id,
                        disk_name=d_name,
                        read_mb_sec=d_io.read_mb_sec,
                        write_mb_sec=d_io.write_mb_sec,
                        read_iops=d_io.read_iops,
                        write_iops=d_io.write_iops,
                        read_latency_ms=d_io.read_latency_ms,
                        write_latency_ms=d_io.write_latency_ms,
                    )
                )

        top_io_disks.sort(
            key=lambda x: (x.read_mb_sec + x.write_mb_sec) * 100 + x.read_iops + x.write_iops,
            reverse=True,
        )
        top_io_disks = top_io_disks[:10]
    except Exception as e:
        logger.debug("Failed calculating disk statistics in storage domain %s: %s", sd.id, e)

    avg_read_lat = round(sum(read_latencies) / len(read_latencies), 3) if read_latencies else 0.0
    avg_write_lat = (
        round(sum(write_latencies) / len(write_latencies), 3) if write_latencies else 0.0
    )

    io_stats = StorageDomainIoStats(
        total_read_bytes_sec=round(tot_read_bytes, 1),
        total_write_bytes_sec=round(tot_write_bytes, 1),
        total_read_mb_sec=round(tot_read_mb, 3),
        total_write_mb_sec=round(tot_write_mb, 3),
        total_read_iops=round(tot_read_iops, 1),
        total_write_iops=round(tot_write_iops, 1),
        avg_read_latency_ms=avg_read_lat,
        avg_write_latency_ms=avg_write_lat,
        active_disks_count=active_disks_count,
    )

    # Count templates
    templates_count = 0
    try:
        templates_count = len(sd_svc.templates_service().list())
    except Exception as e:
        logger.debug("Failed counting templates in storage domain %s: %s", sd.id, e)

    # Count and list VMs
    vms_count = 0
    vms_list: list[str] = []
    try:
        sd_vms = sd_svc.vms_service().list()
        vms_count = len(sd_vms)
        for v in sd_vms:
            v_name = getattr(v, "name", None)
            if v_name:
                vms_list.append(str(v_name))
    except Exception as e:
        logger.debug("Failed counting VMs in storage domain %s: %s", sd.id, e)

    warn_threshold = getattr(sd_detail, "warning_low_space_indicator", None)
    crit_threshold = getattr(sd_detail, "critical_space_action_blocker", None)

    return StorageDomainDetail(
        **summary.model_dump(),
        description=str(sd_detail.description) if getattr(sd_detail, "description", None) else None,
        warning_low_space_indicator=int(warn_threshold) if warn_threshold is not None else None,
        critical_space_action_blocker=int(crit_threshold) if crit_threshold is not None else None,
        supports_discard=bool(getattr(sd_detail, "supports_discard", False)),
        supports_discard_zeroes_data=bool(
            getattr(sd_detail, "supports_discard_zeroes_data", False)
        ),
        wipe_after_delete=bool(getattr(sd_detail, "wipe_after_delete", False)),
        disks_count=disks_count,
        templates_count=templates_count,
        vms_count=vms_count,
        io_stats=io_stats,
        top_io_disks=top_io_disks,
        vms_list=vms_list,
    )


# =========================================================================
# 2. Storage Domain Lifecycle (Create / Attach / Activate / Maintenance / Detach / Delete)
# =========================================================================


def ovirt_storage_domain_create_nfs(
    name: str,
    host_name_or_id: str,
    address: str,
    path: str,
    domain_type: str = "data",
    nfs_version: str = "auto",
    description: str | None = None,
) -> StorageDomainResult:
    """Create a new NFS Storage Domain in oVirt / OLVM.

    The designated hypervisor host is instructed by the Engine to mount the NFS export
    and format the storage domain metadata.

    Args:
        name: Unique name for the storage domain.
        host_name_or_id: Hypervisor host responsible for initializing storage domain metadata.
        address: IP address or hostname of the NFS server (e.g. '192.0.2.20').
        path: Exported NFS directory path (e.g. '/exports/data').
        domain_type: Domain role: 'data', 'iso', or 'export' (default: 'data').
        nfs_version: NFS version: 'auto', 'v3', 'v4', 'v4_1', 'v4_2' (default: 'auto').
        description: Optional human-readable description.

    Returns:
        StorageDomainResult with creation details and UUID.
    """
    require_mutation_allowed("ovirt_storage_domain_create_nfs")

    name_clean = name.strip()
    addr_clean = address.strip()
    path_clean = path.strip()
    if not name_clean or not addr_clean or not path_clean:
        raise OvirtValidationError("Storage domain name, NFS address, and path must not be empty.")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    sds_svc = sys_svc.storage_domains_service()
    hosts_svc = sys_svc.hosts_service()

    # Pre-check existence
    for existing in sds_svc.list():
        if existing.name == name_clean:
            raise OvirtValidationError(
                f"Storage domain '{name_clean}' already exists (UUID: {existing.id}).",
                details={"name": name_clean, "storage_domain_id": str(existing.id)},
            )

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")

    # Map domain type enum
    dtype_lower = domain_type.strip().lower()
    sd_type = sdk_types.StorageDomainType.DATA
    if dtype_lower == "iso":
        sd_type = sdk_types.StorageDomainType.ISO
    elif dtype_lower == "export":
        sd_type = sdk_types.StorageDomainType.EXPORT

    # Map NFS version enum
    nfs_ver = sdk_types.NfsVersion.AUTO
    ver_clean = nfs_version.strip().lower()
    if ver_clean == "v3":
        nfs_ver = sdk_types.NfsVersion.V3
    elif ver_clean in ("v4", "v4_0"):
        nfs_ver = sdk_types.NfsVersion.V4
    elif ver_clean == "v4_1":
        nfs_ver = sdk_types.NfsVersion.V4_1
    elif ver_clean == "v4_2":
        nfs_ver = sdk_types.NfsVersion.V4_2

    host_storage = sdk_types.HostStorage(
        type=sdk_types.StorageType.NFS,
        address=addr_clean,
        path=path_clean,
        nfs_version=nfs_ver,
    )

    new_sd = sdk_types.StorageDomain(
        name=name_clean,
        description=description,
        type=sd_type,
        storage_format=sdk_types.StorageFormat.V5
        if sd_type == sdk_types.StorageDomainType.DATA
        else sdk_types.StorageFormat.V1,
        storage=host_storage,
        host=sdk_types.Host(id=host.id),
    )

    try:
        created = sds_svc.add(new_sd)
    except Exception as e:
        logger.error(
            "Failed to create NFS storage domain %s on %s:%s: %s",
            name_clean,
            addr_clean,
            path_clean,
            e,
        )
        raise OvirtValidationError(
            f"Failed to create NFS storage domain '{name_clean}' on '{addr_clean}:{path_clean}': {e}",
            details={
                "name": name_clean,
                "address": addr_clean,
                "path": path_clean,
                "host": str(host.name),
            },
        ) from e

    audit_log(
        "ovirt_storage_domain_create_nfs",
        name_clean,
        {
            "storage_domain_id": str(created.id),
            "address": addr_clean,
            "path": path_clean,
            "host": str(host.name),
        },
        "SUCCESS",
    )

    return StorageDomainResult(
        success=True,
        storage_domain_id=str(created.id),
        storage_domain_name=str(created.name),
        action="create_nfs",
        status="unattached",
        message=(
            f"NFS Storage Domain '{created.name}' created successfully (UUID: {created.id}). "
            f"Backed by {addr_clean}:{path_clean}. Initialized via host '{host.name}'."
        ),
    )


def ovirt_storage_domain_attach(
    storage_domain_name_or_id: str,
    data_center_name_or_id: str,
) -> StorageDomainResult:
    """Attach a Storage Domain to a Data Center.

    Args:
        storage_domain_name_or_id: Name or UUID of the storage domain to attach.
        data_center_name_or_id: Name or UUID of the target Data Center.

    Returns:
        StorageDomainResult with attachment status.
    """
    require_mutation_allowed("ovirt_storage_domain_attach")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    sds_svc = sys_svc.storage_domains_service()
    dcs_svc = sys_svc.data_centers_service()

    sd = client.find_resource_by_id_or_name(sds_svc, storage_domain_name_or_id, "storage_domain")
    dc = client.find_resource_by_id_or_name(dcs_svc, data_center_name_or_id, "data_center")

    dc_svc = dcs_svc.data_center_service(dc.id)
    attached_svc = dc_svc.storage_domains_service()

    # Pre-check if already attached
    for existing in attached_svc.list():
        if existing.id == sd.id:
            return StorageDomainResult(
                success=True,
                storage_domain_id=str(sd.id),
                storage_domain_name=str(sd.name),
                data_center_name=str(dc.name),
                action="attach",
                status=str(existing.status).lower()
                if getattr(existing, "status", None)
                else "active",
                message=f"Storage Domain '{sd.name}' is already attached to Data Center '{dc.name}'.",
            )

    attached_svc.add(sdk_types.StorageDomain(id=sd.id))

    audit_log(
        "ovirt_storage_domain_attach",
        str(sd.name),
        {
            "storage_domain_id": str(sd.id),
            "data_center_id": str(dc.id),
            "data_center_name": str(dc.name),
        },
        "SUCCESS",
    )

    return StorageDomainResult(
        success=True,
        storage_domain_id=str(sd.id),
        storage_domain_name=str(sd.name),
        data_center_name=str(dc.name),
        action="attach",
        message=f"Storage Domain '{sd.name}' attached successfully to Data Center '{dc.name}'.",
    )


def ovirt_storage_domain_activate(
    storage_domain_name_or_id: str,
    data_center_name_or_id: str,
) -> StorageDomainResult:
    """Activate an attached Storage Domain in a Data Center.

    Args:
        storage_domain_name_or_id: Name or UUID of the storage domain.
        data_center_name_or_id: Name or UUID of the Data Center.

    Returns:
        StorageDomainResult with activation status.
    """
    require_mutation_allowed("ovirt_storage_domain_activate")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    sds_svc = sys_svc.storage_domains_service()
    dcs_svc = sys_svc.data_centers_service()

    sd = client.find_resource_by_id_or_name(sds_svc, storage_domain_name_or_id, "storage_domain")
    dc = client.find_resource_by_id_or_name(dcs_svc, data_center_name_or_id, "data_center")

    dc_sd_svc = (
        dcs_svc.data_center_service(dc.id).storage_domains_service().storage_domain_service(sd.id)
    )
    dc_sd_svc.activate()

    audit_log(
        "ovirt_storage_domain_activate",
        str(sd.name),
        {"storage_domain_id": str(sd.id), "data_center_id": str(dc.id)},
        "SUCCESS",
    )

    return StorageDomainResult(
        success=True,
        storage_domain_id=str(sd.id),
        storage_domain_name=str(sd.name),
        data_center_name=str(dc.name),
        action="activate",
        status="active",
        message=f"Storage Domain '{sd.name}' activated successfully in Data Center '{dc.name}'.",
    )


def ovirt_storage_domain_maintenance(
    storage_domain_name_or_id: str,
    data_center_name_or_id: str,
) -> StorageDomainResult:
    """Move an attached Storage Domain to maintenance mode in a Data Center (deactivate).

    Required step before detaching or removing a storage domain.

    Args:
        storage_domain_name_or_id: Name or UUID of the storage domain.
        data_center_name_or_id: Name or UUID of the Data Center.

    Returns:
        StorageDomainResult with maintenance status.
    """
    require_mutation_allowed("ovirt_storage_domain_maintenance")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    sds_svc = sys_svc.storage_domains_service()
    dcs_svc = sys_svc.data_centers_service()

    sd = client.find_resource_by_id_or_name(sds_svc, storage_domain_name_or_id, "storage_domain")
    dc = client.find_resource_by_id_or_name(dcs_svc, data_center_name_or_id, "data_center")

    dc_sd_svc = (
        dcs_svc.data_center_service(dc.id).storage_domains_service().storage_domain_service(sd.id)
    )
    dc_sd_svc.deactivate()

    audit_log(
        "ovirt_storage_domain_maintenance",
        str(sd.name),
        {"storage_domain_id": str(sd.id), "data_center_id": str(dc.id)},
        "SUCCESS",
    )

    return StorageDomainResult(
        success=True,
        storage_domain_id=str(sd.id),
        storage_domain_name=str(sd.name),
        data_center_name=str(dc.name),
        action="maintenance",
        status="maintenance",
        message=f"Storage Domain '{sd.name}' moved to maintenance mode in Data Center '{dc.name}'.",
    )


def ovirt_storage_domain_detach(
    storage_domain_name_or_id: str,
    data_center_name_or_id: str,
) -> StorageDomainResult:
    """Detach a Storage Domain from a Data Center (reversible counterpart of attach).

    The storage domain must first be in maintenance mode before it can be detached.

    Args:
        storage_domain_name_or_id: Name or UUID of the storage domain.
        data_center_name_or_id: Name or UUID of the Data Center.

    Returns:
        StorageDomainResult with detachment status.
    """
    require_mutation_allowed("ovirt_storage_domain_detach")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    sds_svc = sys_svc.storage_domains_service()
    dcs_svc = sys_svc.data_centers_service()

    sd = client.find_resource_by_id_or_name(sds_svc, storage_domain_name_or_id, "storage_domain")
    dc = client.find_resource_by_id_or_name(dcs_svc, data_center_name_or_id, "data_center")

    dc_sd_svc = (
        dcs_svc.data_center_service(dc.id).storage_domains_service().storage_domain_service(sd.id)
    )

    # Pre-flight check: ensure domain is in maintenance
    try:
        attached_sd = dc_sd_svc.get()
        if attached_sd and getattr(attached_sd, "status", None):
            cur_status = str(attached_sd.status).lower()
            if cur_status == "active":
                raise OvirtValidationError(
                    f"Cannot detach Storage Domain '{sd.name}' because it is currently 'active' in "
                    f"Data Center '{dc.name}'. You must first move the storage domain to maintenance "
                    "mode using ovirt_storage_domain_maintenance.",
                    details={
                        "storage_domain": str(sd.name),
                        "data_center": str(dc.name),
                        "status": cur_status,
                    },
                )
    except Exception as e:
        if isinstance(e, OvirtValidationError):
            raise
        logger.debug("Error checking attached domain status: %s", e)

    dc_sd_svc.remove()

    audit_log(
        "ovirt_storage_domain_detach",
        str(sd.name),
        {"storage_domain_id": str(sd.id), "data_center_id": str(dc.id)},
        "SUCCESS",
    )

    return StorageDomainResult(
        success=True,
        storage_domain_id=str(sd.id),
        storage_domain_name=str(sd.name),
        data_center_name=str(dc.name),
        action="detach",
        status="unattached",
        message=f"Storage Domain '{sd.name}' detached successfully from Data Center '{dc.name}'.",
    )


def ovirt_storage_domain_delete(
    name_or_id: str,
    host_name_or_id: str | None = None,
    format: bool = False,
    confirm: bool = False,
) -> StorageDomainResult:
    """Delete or unregister a Storage Domain from oVirt / OLVM.

    Protected by safe-mode confirmation (confirm=True). If the domain is still attached
    to an active Data Center, deletion is rejected by pre-flight guard to protect data integrity.

    Args:
        name_or_id: Name or UUID of the storage domain to delete.
        host_name_or_id: Hypervisor host required by oVirt to format or wipe storage metadata.
                         If omitted, the SPM or first active host is used automatically.
        format: Whether to format the underlying storage, wiping all disk images (DESTRUCTIVE).
        confirm: Confirmation flag required in safe-mode.

    Returns:
        StorageDomainResult with deletion status.
    """
    require_destructive_confirmation("ovirt_storage_domain_delete", confirm)

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    sds_svc = sys_svc.storage_domains_service()
    hosts_svc = sys_svc.hosts_service()

    sd = client.find_resource_by_id_or_name(sds_svc, name_or_id, "storage_domain")

    # Guard 1: Verify not attached to any Data Center
    dcs = sys_svc.data_centers_service().list()
    attached_to_dcs: list[str] = []
    for dc in dcs:
        dc_svc = sys_svc.data_centers_service().data_center_service(dc.id)
        for a in dc_svc.storage_domains_service().list():
            if a.id == sd.id:
                attached_to_dcs.append(str(dc.name))

    if attached_to_dcs:
        raise OvirtValidationError(
            f"Cannot delete Storage Domain '{sd.name}' because it is currently attached to "
            f"Data Center(s): {attached_to_dcs}. You must first move the storage domain to "
            "maintenance and detach it using ovirt_storage_domain_detach.",
            details={"storage_domain": str(sd.name), "attached_data_centers": attached_to_dcs},
        )

    # Determine execution host
    exec_host_name: str | None = None
    if host_name_or_id:
        target_h = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
        exec_host_name = str(target_h.name)
    else:
        # Find SPM or first active host
        all_hosts = hosts_svc.list()
        spm_host = next(
            (
                h
                for h in all_hosts
                if getattr(h, "spm", None) and str(h.spm.status).lower() == "spm"
            ),
            None,
        )
        if spm_host:
            exec_host_name = str(spm_host.name)
        elif all_hosts:
            exec_host_name = str(all_hosts[0].name)

    sd_svc = sds_svc.storage_domain_service(sd.id)

    remove_kwargs: dict[str, Any] = {"format": format}
    if exec_host_name:
        remove_kwargs["host"] = exec_host_name

    sd_svc.remove(**remove_kwargs)

    audit_log(
        "ovirt_storage_domain_delete",
        str(sd.name),
        {"storage_domain_id": str(sd.id), "format": format, "host": exec_host_name},
        "SUCCESS",
    )

    return StorageDomainResult(
        success=True,
        storage_domain_id=str(sd.id),
        storage_domain_name=str(sd.name),
        action="delete",
        message=(
            f"Storage Domain '{sd.name}' deleted successfully "
            f"(format={format}, executed via host '{exec_host_name}')."
        ),
    )
