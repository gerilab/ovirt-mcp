"""Tools for inspecting and managing oVirt / OLVM virtualization clusters."""

import contextlib
import logging
from typing import Any

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.models.cluster import (
    ClusterDetail,
    ClusterSummary,
)

logger = logging.getLogger(__name__)


def _clean_opt_str(val: Any) -> str | None:
    """Return string or None if unset or a mock object."""
    if val is None or not isinstance(val, str):
        return None
    return val


def _extract_cluster_summary(
    c: Any,
    dc_names: dict[str, str] | None = None,
) -> ClusterSummary:
    """Extract a typed ClusterSummary from an oVirt SDK Cluster object."""
    c_id = str(c.id)
    name = str(getattr(c, "name", c_id))
    description = _clean_opt_str(getattr(c, "description", None))

    dc_obj = getattr(c, "data_center", None)
    dc_id = str(dc_obj.id) if dc_obj and getattr(dc_obj, "id", None) else None
    dc_name = _clean_opt_str(getattr(dc_obj, "name", None)) or (
        dc_names.get(dc_id) if dc_names and dc_id else None
    )

    cpu_obj = getattr(c, "cpu", None)
    cpu_type = _clean_opt_str(getattr(cpu_obj, "type", None))
    cpu_arch = None
    if cpu_obj:
        arch_val = getattr(cpu_obj, "architecture", None)
        cpu_arch = str(getattr(arch_val, "value", arch_val or "")).lower() or None
        if not isinstance(cpu_arch, str) or not cpu_arch:
            cpu_arch = None

    ver_obj = getattr(c, "version", None)
    compat_ver = None
    if ver_obj:
        raw_full = getattr(ver_obj, "full_version", None)
        if raw_full and isinstance(raw_full, str):
            compat_ver = raw_full
        else:
            major = getattr(ver_obj, "major", None)
            minor = getattr(ver_obj, "minor", None)
            if major is not None and minor is not None:
                compat_ver = f"{major}.{minor}"

    ballooning = bool(getattr(c, "ballooning_enabled", False))
    ha_res = bool(getattr(c, "ha_reservation", False))

    return ClusterSummary(
        id=c_id,
        name=name,
        description=description,
        data_center_id=dc_id,
        data_center_name=dc_name,
        cpu_type=cpu_type,
        cpu_architecture=cpu_arch,
        compatibility_version=compat_ver,
        ballooning_enabled=ballooning,
        ha_reservation=ha_res,
    )


def _extract_cluster_detail(
    c: Any,
    dc_names: dict[str, str] | None = None,
) -> ClusterDetail:
    """Extract a typed ClusterDetail from an oVirt SDK Cluster object."""
    summary = _extract_cluster_summary(c, dc_names)

    mem_policy = getattr(c, "memory_policy", None)
    overcommit = None
    if mem_policy:
        oc_obj = getattr(mem_policy, "over_commit", None)
        if oc_obj and hasattr(oc_obj, "percent"):
            with contextlib.suppress(ValueError, TypeError):
                overcommit = int(oc_obj.percent)

    fips_obj = getattr(c, "fips_mode", None)
    fips_str = str(getattr(fips_obj, "value", fips_obj or "")).lower() or None
    if not isinstance(fips_str, str) or not fips_str:
        fips_str = None

    bios_obj = getattr(c, "bios_type", None)
    bios_str = str(getattr(bios_obj, "value", bios_obj or "")).lower() or None
    if not isinstance(bios_str, str) or not bios_str:
        bios_str = None

    threads_as_cores = bool(getattr(c, "threads_as_cores", False))

    mig_obj = getattr(c, "migration", None)
    mig_enc = False
    mig_bw = None
    if mig_obj:
        mig_enc = bool(getattr(mig_obj, "encrypted", False))
        bw_obj = getattr(mig_obj, "bandwidth", None)
        if bw_obj:
            mig_bw = _clean_opt_str(getattr(bw_obj, "assignment_method", None))

    fencing_obj = getattr(c, "fencing_policy", None)
    fencing_enabled = bool(getattr(fencing_obj, "enabled", True)) if fencing_obj else True

    ksm_obj = getattr(c, "ksm", None)
    ksm_enabled = bool(getattr(ksm_obj, "enabled", True)) if ksm_obj else True

    switch_obj = getattr(c, "switch_type", None)
    switch_str = str(getattr(switch_obj, "value", switch_obj or "")).lower() or None
    if not isinstance(switch_str, str) or not switch_str:
        switch_str = None

    return ClusterDetail(
        id=summary.id,
        name=summary.name,
        description=summary.description,
        data_center_id=summary.data_center_id,
        data_center_name=summary.data_center_name,
        cpu_type=summary.cpu_type,
        cpu_architecture=summary.cpu_architecture,
        compatibility_version=summary.compatibility_version,
        ballooning_enabled=summary.ballooning_enabled,
        ha_reservation=summary.ha_reservation,
        memory_overcommit_percent=overcommit,
        fips_mode=fips_str,
        bios_type=bios_str,
        threads_as_cores=threads_as_cores,
        migration_encrypted=mig_enc,
        migration_bandwidth=mig_bw,
        fencing_enabled=fencing_enabled,
        ksm_enabled=ksm_enabled,
        switch_type=switch_str,
    )


def list_clusters_tool(
    search: str | None = None,
    data_center: str | None = None,
) -> list[ClusterSummary]:
    """List virtualization clusters with CPU architectures, compatibility, and memory policies.

    Args:
        search: Optional search filter query (e.g. 'name=Prod*').
        data_center: Optional parent Data Center name or UUID filter.

    Returns:
        List of ClusterSummary objects.
    """
    client = get_client()
    conn = client.get_connection()
    sys_service = conn.system_service()
    clusters_service = sys_service.clusters_service()

    target_dc_id: str | None = None
    if data_center:
        dcs_service = sys_service.data_centers_service()
        dc = client.find_resource_by_id_or_name(dcs_service, data_center, "data_center")
        if dc:
            target_dc_id = str(dc.id)

    # Pre-fetch Data Centers to populate friendly names
    dc_names: dict[str, str] = {}
    try:
        for d in sys_service.data_centers_service().list():
            dc_names[str(d.id)] = str(d.name)
    except Exception:
        pass

    kwargs: dict[str, Any] = {}
    if search:
        kwargs["search"] = search

    clusters = clusters_service.list(**kwargs) or []
    results: list[ClusterSummary] = []
    for c in clusters:
        summary = _extract_cluster_summary(c, dc_names)
        if target_dc_id and summary.data_center_id != target_dc_id:
            continue
        results.append(summary)

    return results


def get_cluster_tool(name_or_id: str) -> ClusterDetail:
    """Retrieve deep technical parameters and capability profile of a cluster.

    Args:
        name_or_id: Cluster display name or UUID.

    Returns:
        ClusterDetail object with complete cluster hardware policies.
    """
    client = get_client()
    conn = client.get_connection()
    sys_service = conn.system_service()
    clusters_service = sys_service.clusters_service()

    cluster = client.find_resource_by_id_or_name(clusters_service, name_or_id, "cluster")
    if not cluster:
        raise OvirtValidationError(f"Cluster '{name_or_id}' not found.")

    dc_names: dict[str, str] = {}
    try:
        for d in sys_service.data_centers_service().list():
            dc_names[str(d.id)] = str(d.name)
    except Exception:
        pass

    return _extract_cluster_detail(cluster, dc_names)
