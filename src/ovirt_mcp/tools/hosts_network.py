"""Hypervisor Host Network Attachments and iSCSI Discovery tools."""

import logging

from ovirtsdk4 import types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.models.host_network import (
    HostIscsiDiscoverResult,
    HostIscsiLoginResult,
    HostNetworkAttachmentInfo,
    HostNetworkSetupResult,
)
from ovirt_mcp.tools.guards import audit_log, require_mutation_allowed

logger = logging.getLogger("ovirt_mcp.tools.hosts_network")


def ovirt_host_network_attachment_list(host_name_or_id: str) -> list[HostNetworkAttachmentInfo]:
    """List all logical network attachments on a hypervisor host.

    Resolves which logical oVirt network (e.g. 'ovirtmgmt') is attached to which physical
    NIC or bond (e.g. 'eth0'), along with IPv4 assignment method, address, netmask,
    gateway, and in-sync status.

    Args:
        host_name_or_id: UUID or name of the hypervisor host.

    Returns:
        List of HostNetworkAttachmentInfo objects.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    h_svc = hosts_svc.host_service(host.id)

    # Pre-fetch lookup maps
    net_map: dict[str, str] = {}
    try:
        net_map = {str(n.id): str(n.name) for n in sys_svc.networks_service().list()}
    except Exception as e:
        logger.debug("Failed listing global networks for attachment resolution: %s", e)

    nic_map: dict[str, str] = {}
    try:
        nic_map = {str(nic.id): str(nic.name) for nic in h_svc.nics_service().list()}
    except Exception as e:
        logger.debug("Failed listing host nics for attachment resolution: %s", e)

    attachments = h_svc.network_attachments_service().list()
    result: list[HostNetworkAttachmentInfo] = []

    for att in attachments:
        net_id = str(att.network.id) if att.network and att.network.id else ""
        net_name = net_map.get(net_id, "unknown")
        nic_id = str(att.host_nic.id) if att.host_nic and att.host_nic.id else ""
        nic_name = nic_map.get(nic_id, "unknown")

        boot_proto = "none"
        ip_addr: str | None = None
        netmask: str | None = None
        gateway: str | None = None

        if getattr(att, "ip_address_assignments", None):
            for ip_assign in att.ip_address_assignments:
                method = str(ip_assign.assignment_method) if ip_assign.assignment_method else "none"
                if method != "none":
                    boot_proto = method
                    if getattr(ip_assign, "ip", None):
                        ip_addr = str(ip_assign.ip.address) if ip_assign.ip.address else None
                        netmask = str(ip_assign.ip.netmask) if ip_assign.ip.netmask else None
                        gateway = str(ip_assign.ip.gateway) if ip_assign.ip.gateway else None
                    break

        result.append(
            HostNetworkAttachmentInfo(
                id=str(att.id),
                network_id=net_id,
                network_name=net_name,
                host_nic_id=nic_id,
                host_nic_name=nic_name,
                in_sync=bool(att.in_sync)
                if hasattr(att, "in_sync") and att.in_sync is not None
                else True,
                boot_protocol=boot_proto,
                ip_address=ip_addr,
                netmask=netmask,
                gateway=gateway,
            )
        )

    return result


def ovirt_host_iscsi_discover(
    host_name_or_id: str,
    address: str,
    port: int = 3260,
    username: str | None = None,
    password: str | None = None,
) -> HostIscsiDiscoverResult:
    """Discover available iSCSI targets on a target storage portal from a hypervisor host.

    Sends an iSCSI discovery request via the hypervisor host OS kernel to discover all
    target IQNs available on the specified storage server and port.

    Args:
        host_name_or_id: UUID or name of the hypervisor host performing discovery.
        address: IP address or hostname of the storage server portal (e.g. '192.0.2.10').
        port: iSCSI portal TCP port (default: 3260).
        username: Optional CHAP authentication username.
        password: Optional CHAP authentication password.

    Returns:
        HostIscsiDiscoverResult containing list of discovered target IQNs.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    h_svc = hosts_svc.host_service(host.id)

    addr_clean = address.strip()
    if not addr_clean:
        raise OvirtValidationError("iSCSI portal address must not be empty.")

    iscsi_details = sdk_types.IscsiDetails(
        address=addr_clean,
        port=port,
        username=username,
        password=password,
    )

    try:
        raw_targets = h_svc.iscsi_discover(iscsi=iscsi_details)
    except Exception as e:
        logger.error(
            "iSCSI discovery failed on host %s to %s:%d: %s", host.name, addr_clean, port, e
        )
        raise OvirtValidationError(
            f"Failed to discover iSCSI targets from host '{host.name}' on portal '{addr_clean}:{port}': {e}",
            details={"host": str(host.name), "address": addr_clean, "port": port},
        ) from e

    discovered_targets: list[str] = []
    if raw_targets:
        for t in raw_targets:
            discovered_targets.append(str(t))

    return HostIscsiDiscoverResult(
        host_id=str(host.id),
        host_name=str(host.name),
        address=addr_clean,
        port=port,
        targets=discovered_targets,
        count=len(discovered_targets),
    )


def ovirt_host_iscsi_login(
    host_name_or_id: str,
    address: str,
    target: str,
    port: int = 3260,
    username: str | None = None,
    password: str | None = None,
) -> HostIscsiLoginResult:
    """Log in to an iSCSI target portal from a hypervisor host.

    Connects the hypervisor host OS kernel (iscsiadm) to the designated iSCSI target portal,
    discovering LUN block devices (/dev/mapper/...) necessary for iSCSI Storage Domain creation.

    Args:
        host_name_or_id: UUID or name of the hypervisor host.
        address: IP address or hostname of the iSCSI portal.
        target: Target IQN to log in to (e.g. 'iqn.2024-01.org.example:storage.target01').
        port: iSCSI portal port (default: 3260).
        username: Optional CHAP username.
        password: Optional CHAP password.

    Returns:
        HostIscsiLoginResult with login outcome.
    """
    require_mutation_allowed("ovirt_host_iscsi_login")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    h_svc = hosts_svc.host_service(host.id)

    addr_clean = address.strip()
    target_clean = target.strip()
    if not addr_clean or not target_clean:
        raise OvirtValidationError("iSCSI address and target IQN must not be empty.")

    iscsi_details = sdk_types.IscsiDetails(
        address=addr_clean,
        port=port,
        target=target_clean,
        username=username,
        password=password,
    )

    try:
        h_svc.iscsi_login(iscsi=iscsi_details)
    except Exception as e:
        logger.error(
            "iSCSI login failed on host %s to %s:%d [%s]: %s",
            host.name,
            addr_clean,
            port,
            target_clean,
            e,
        )
        raise OvirtValidationError(
            f"Failed iSCSI login on host '{host.name}' to target '{target_clean}' at '{addr_clean}:{port}': {e}",
            details={"host": str(host.name), "address": addr_clean, "target": target_clean},
        ) from e

    audit_log(
        "ovirt_host_iscsi_login",
        str(host.name),
        {"address": addr_clean, "port": port, "target": target_clean},
        "SUCCESS",
    )

    return HostIscsiLoginResult(
        success=True,
        host_id=str(host.id),
        host_name=str(host.name),
        target=target_clean,
        address=addr_clean,
        port=port,
        message=(
            f"Hypervisor host '{host.name}' logged in successfully to iSCSI target '{target_clean}' "
            f"at portal '{addr_clean}:{port}'."
        ),
    )


def ovirt_host_network_sync(
    host_name_or_id: str,
    network_attachment_id: str | None = None,
) -> HostNetworkSetupResult:
    """Synchronize out-of-sync network attachments on a hypervisor host.

    Reapplies logical network configurations (VLAN, MTU, QoS) from the oVirt Engine
    to the hypervisor host with safe rollback protection (check_connectivity=True).

    Args:
        host_name_or_id: UUID or name of the hypervisor host.
        network_attachment_id: Optional UUID of a specific attachment to synchronize.
                               If omitted, synchronizes all out-of-sync attachments on the host.

    Returns:
        HostNetworkSetupResult with outcome.
    """
    require_mutation_allowed("ovirt_host_network_sync")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    h_svc = hosts_svc.host_service(host.id)

    attachments = h_svc.network_attachments_service().list()
    sync_targets: list[sdk_types.NetworkAttachment] = []

    if network_attachment_id:
        target_att = next((a for a in attachments if str(a.id) == network_attachment_id), None)
        if not target_att:
            raise OvirtValidationError(
                f"Network attachment '{network_attachment_id}' not found on host '{host.name}'.",
                details={"host": str(host.name), "attachment_id": network_attachment_id},
            )
        sync_targets.append(sdk_types.NetworkAttachment(id=target_att.id))
    else:
        for a in attachments:
            if hasattr(a, "in_sync") and a.in_sync is False:
                sync_targets.append(sdk_types.NetworkAttachment(id=a.id))

    if not sync_targets:
        return HostNetworkSetupResult(
            success=True,
            host_id=str(host.id),
            host_name=str(host.name),
            action="sync_networks",
            message=f"All network attachments on host '{host.name}' are already in-sync. No action needed.",
        )

    h_svc.setup_networks(
        synchronized_network_attachments=sync_targets,
        check_connectivity=True,
        commit_on_success=True,
    )

    audit_log(
        "ovirt_host_network_sync",
        str(host.name),
        {"synchronized_attachments_count": len(sync_targets)},
        "SUCCESS",
    )

    return HostNetworkSetupResult(
        success=True,
        host_id=str(host.id),
        host_name=str(host.name),
        action="sync_networks",
        message=f"Successfully synchronized {len(sync_targets)} network attachment(s) on host '{host.name}'.",
    )
