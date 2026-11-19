"""Tools for managing oVirt / OLVM Logical Networks (VLANs, MTU, cluster networks)."""

import logging

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.logical_network import (
    LogicalNetworkDetail,
    LogicalNetworkResult,
    LogicalNetworkSummary,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger("ovirt_mcp.tools.logical_networks")

MANAGEMENT_NETWORK_NAME = "ovirtmgmt"


def list_logical_networks_tool(
    data_center: str | None = None,
) -> list[LogicalNetworkSummary]:
    """List logical networks across Data Centers or filtered by a specific Data Center.

    Args:
        data_center: Optional Data Center name or UUID to filter networks.

    Returns:
        List of LogicalNetworkSummary objects with VLAN tag and MTU.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    nets_svc = sys_svc.networks_service()
    dcs_svc = sys_svc.data_centers_service()

    target_dc_id = None
    if data_center:
        dc_obj = client.find_resource_by_id_or_name(dcs_svc, data_center, "data center")
        target_dc_id = str(dc_obj.id)

    try:
        raw_nets = nets_svc.list()
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to list logical networks: {exc}",
            details={"data_center": data_center, "error": str(exc)},
        ) from exc

    # Cache DC names
    dc_names: dict[str, str] = {}
    for d in dcs_svc.list():
        dc_names[str(d.id)] = str(getattr(d, "name", str(d.id)))

    results: list[LogicalNetworkSummary] = []
    for net in raw_nets:
        net_dc_id = (
            str(net.data_center.id) if hasattr(net, "data_center") and net.data_center else None
        )
        if target_dc_id and net_dc_id != target_dc_id:
            continue

        net_id = str(net.id)
        net_name = str(getattr(net, "name", net_id))
        desc = str(net.description) if getattr(net, "description", None) is not None else None

        vlan_id = None
        if hasattr(net, "vlan") and net.vlan and getattr(net.vlan, "id", None) is not None:
            vlan_id = int(net.vlan.id)

        mtu_val = getattr(net, "mtu", None)
        mtu = int(mtu_val) if mtu_val is not None else None

        st_obj = getattr(net, "status", None)
        status_str = str(getattr(st_obj, "value", st_obj or "operational")).lower()

        results.append(
            LogicalNetworkSummary(
                id=net_id,
                name=net_name,
                description=desc,
                data_center_id=net_dc_id or "unknown",
                data_center_name=dc_names.get(net_dc_id or "", "unknown"),
                vlan_id=vlan_id,
                mtu=mtu,
                status=status_str,
            )
        )

    return results


def get_logical_network_tool(
    name_or_id: str,
) -> LogicalNetworkDetail:
    """Retrieve detailed configuration and topology for a logical network.

    Args:
        name_or_id: Name or UUID of the logical network.

    Returns:
        LogicalNetworkDetail with MTU, VLAN, STP, port isolation, vNIC profiles, labels, and permissions.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    nets_svc = sys_svc.networks_service()
    dcs_svc = sys_svc.data_centers_service()

    net = client.find_resource_by_id_or_name(nets_svc, name_or_id, "network")
    net_id = str(net.id)
    net_name = str(getattr(net, "name", net_id))
    desc = getattr(net, "description", None)

    dc_obj = getattr(net, "data_center", None)
    net_dc_id = str(dc_obj.id) if dc_obj and getattr(dc_obj, "id", None) else "unknown"
    dc_name = "unknown"
    if dc_obj and getattr(dc_obj, "name", None):
        dc_name = str(dc_obj.name)
    elif net_dc_id != "unknown":
        try:
            dc = dcs_svc.data_center_service(net_dc_id).get()
            dc_name = str(getattr(dc, "name", net_dc_id))
        except Exception:
            dc_name = net_dc_id

    vlan_obj = getattr(net, "vlan", None)
    vlan_id = getattr(vlan_obj, "id", None) if vlan_obj else None
    if vlan_id is not None:
        try:
            vlan_id = int(vlan_id)
        except (ValueError, TypeError):
            vlan_id = None

    mtu = getattr(net, "mtu", None)
    if mtu is not None:
        try:
            mtu = int(mtu)
        except (ValueError, TypeError):
            mtu = None

    status_obj = getattr(net, "status", None)
    status_str = str(getattr(status_obj, "value", status_obj or "operational")).lower()
    stp = bool(getattr(net, "stp", False))
    port_isolation = bool(getattr(net, "port_isolation", False))

    raw_usages = getattr(net, "usages", []) or []
    usages = [str(getattr(u, "value", u)) for u in raw_usages]

    net_svc = nets_svc.network_service(net_id)

    # vNIC profiles
    vnic_profiles: list[str] = []
    try:
        profiles = net_svc.vnic_profiles_service().list()
        vnic_profiles = [str(p.name) for p in profiles if getattr(p, "name", None)]
    except Exception as exc:
        logger.debug("Could not fetch vnic profiles for network '%s': %s", net_name, exc)

    # Network labels
    network_labels: list[str] = []
    try:
        labels = net_svc.network_labels_service().list()
        network_labels = [str(getattr(lbl, "id", lbl)) for lbl in labels]
    except Exception as exc:
        logger.debug("Could not fetch labels for network '%s': %s", net_name, exc)

    # Permissions count
    permissions_count = 0
    try:
        perms = net_svc.permissions_service().list()
        permissions_count = len(perms)
    except Exception as exc:
        logger.debug("Could not fetch permissions for network '%s': %s", net_name, exc)

    return LogicalNetworkDetail(
        id=net_id,
        name=net_name,
        description=desc,
        data_center_id=net_dc_id,
        data_center_name=dc_name,
        vlan_id=vlan_id,
        mtu=mtu,
        status=status_str,
        stp=stp,
        port_isolation=port_isolation,
        usages=usages,
        vnic_profiles=vnic_profiles,
        network_labels=network_labels,
        permissions_count=permissions_count,
    )


def create_logical_network_tool(
    name: str,
    data_center: str,
    vlan_id: int | None = None,
    mtu: int | None = None,
    description: str | None = None,
) -> LogicalNetworkResult:
    """Create a new logical network with optional VLAN tagging and custom MTU.

    Args:
        name: Name for the logical network.
        data_center: Name or UUID of the parent Data Center.
        vlan_id: Optional 802.1Q VLAN encapsulation tag (1-4094).
        mtu: Optional MTU payload size (e.g. 1500, 9000 for jumbo frames).
        description: Optional descriptive text.

    Returns:
        LogicalNetworkResult with creation outcome.
    """
    require_mutation_allowed("ovirt_network_create")

    name = name.strip()
    if not name:
        raise OvirtValidationError("Network name cannot be empty.")

    if vlan_id is not None and not (1 <= vlan_id <= 4094):
        raise OvirtValidationError(
            f"Invalid VLAN ID: {vlan_id}. Must be between 1 and 4094.",
            details={"vlan_id": vlan_id},
        )

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    dcs_svc = sys_svc.data_centers_service()
    nets_svc = sys_svc.networks_service()

    dc = client.find_resource_by_id_or_name(dcs_svc, data_center, "data center")

    # Name collision check
    existing = nets_svc.list()
    for n in existing:
        n_dc_id = str(n.data_center.id) if hasattr(n, "data_center") and n.data_center else None
        if n_dc_id == str(dc.id) and str(getattr(n, "name", "")).lower() == name.lower():
            raise OvirtValidationError(
                f"A logical network named '{name}' already exists in Data Center '{dc.name}'.",
                details={"network_name": name, "data_center": str(dc.name)},
            )

    net_kwargs: dict[str, object] = {
        "name": name,
        "description": description,
        "data_center": sdk_types.DataCenter(id=dc.id),
    }
    if vlan_id is not None:
        net_kwargs["vlan"] = sdk_types.Vlan(id=vlan_id)
    if mtu is not None:
        net_kwargs["mtu"] = mtu

    try:
        created = nets_svc.add(sdk_types.Network(**net_kwargs))
        net_id = str(created.id)
    except Exception as exc:
        audit_log(
            "ovirt_network_create",
            name,
            {"data_center": str(dc.name), "vlan_id": vlan_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to create logical network '{name}' in Data Center '{dc.name}': {exc}",
            details={"network_name": name, "data_center": str(dc.name), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_network_create",
        name,
        {"network_id": net_id, "data_center": str(dc.name), "vlan_id": vlan_id},
        "SUCCESS",
    )

    return LogicalNetworkResult(
        success=True,
        network_id=net_id,
        network_name=name,
        data_center_name=str(dc.name),
        action="create",
        message=f"Logical network '{name}' successfully created in Data Center '{dc.name}'.",
    )


def delete_logical_network_tool(
    name_or_id: str,
    data_center: str | None = None,
    confirm: bool = False,
) -> LogicalNetworkResult:
    """Delete a logical network from oVirt / OLVM.

    Protected by safe-mode confirmation. Protected management networks (such as
    'ovirtmgmt') cannot be deleted.

    Args:
        name_or_id: Network name or UUID.
        data_center: Optional Data Center name or UUID scoping the search.
        confirm: Confirmation flag required in safe-mode.

    Returns:
        LogicalNetworkResult with deletion outcome.
    """
    require_destructive_confirmation("ovirt_network_delete", confirm)
    require_mutation_allowed("ovirt_network_delete")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    nets_svc = sys_svc.networks_service()
    dcs_svc = sys_svc.data_centers_service()

    target_dc_id = None
    dc_name = "unknown"
    if data_center:
        dc_obj = client.find_resource_by_id_or_name(dcs_svc, data_center, "data center")
        target_dc_id = str(dc_obj.id)
        dc_name = str(dc_obj.name)

    net = client.find_resource_by_id_or_name(nets_svc, name_or_id, "network")
    net_id = str(net.id)
    net_name = str(getattr(net, "name", net_id))

    if net_name.lower() == MANAGEMENT_NETWORK_NAME:
        raise OvirtValidationError(
            f"Cannot delete the default management network '{net_name}'. "
            "It is required for host cluster communication and engine management.",
            details={"network_name": net_name, "network_id": net_id},
        )

    if hasattr(net, "data_center") and net.data_center:
        net_dc_id = str(net.data_center.id)
        if target_dc_id and net_dc_id != target_dc_id:
            raise OvirtValidationError(
                f"Network '{net_name}' does not belong to specified Data Center.",
                details={"network_id": net_id, "expected_dc": target_dc_id, "actual_dc": net_dc_id},
            )
        try:
            dc_res = dcs_svc.data_center_service(net_dc_id).get()
            dc_name = str(dc_res.name)
        except Exception:
            pass

    try:
        nets_svc.network_service(net_id).remove()
    except Exception as exc:
        audit_log(
            "ovirt_network_delete",
            net_name,
            {"network_id": net_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to delete logical network '{net_name}' ({net_id}): {exc}",
            details={"network_id": net_id, "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_network_delete",
        net_name,
        {"network_id": net_id, "data_center": dc_name},
        "SUCCESS",
    )

    return LogicalNetworkResult(
        success=True,
        network_id=net_id,
        network_name=net_name,
        data_center_name=dc_name,
        action="delete",
        message=f"Logical network '{net_name}' successfully deleted from Data Center '{dc_name}'.",
    )
