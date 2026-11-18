"""Tools for managing oVirt / OLVM Data Centers."""

import logging

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError
from ovirt_mcp.models.datacenter import (
    DataCenterDetail,
    DataCenterSummary,
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
