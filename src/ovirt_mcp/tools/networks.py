"""Tools for managing VM virtual network interfaces (vNICs) and vNIC profiles."""

import logging

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.network import VmNicDetail, VmNicResult, VnicProfileInfo
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger("ovirt_mcp.tools.networks")


def list_vm_nics_tool(name_or_id: str) -> list[VmNicDetail]:
    """List virtual network interface cards (vNICs) attached to a virtual machine.

    Args:
        name_or_id: Display name or UUID of the virtual machine.

    Returns:
        List of VmNicDetail with MAC address, interface type, plugged, and linked status.
    """
    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    profiles_service = conn.system_service().vnic_profiles_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_service = vms_service.vm_service(vm_id)

    # Pre-cache profiles for quick lookup
    profile_cache: dict[str, tuple[str, str | None]] = {}
    try:
        raw_profiles = profiles_service.list()
        for p in raw_profiles:
            p_id = str(getattr(p, "id", ""))
            p_name = str(getattr(p, "name", p_id))
            prof_net_obj = getattr(p, "network", None)
            prof_net_name = str(getattr(prof_net_obj, "name", "")) if prof_net_obj else None
            profile_cache[p_id] = (p_name, prof_net_name)
    except Exception as prof_err:
        logger.debug("Transient error caching vNIC profiles: %s", prof_err)

    nic_list: list[VmNicDetail] = []
    try:
        raw_nics = vm_service.nics_service().list()
        for nic in raw_nics:
            n_id = str(getattr(nic, "id", ""))
            n_name = str(getattr(nic, "name", n_id))
            mac_obj = getattr(nic, "mac", None)
            mac_addr = getattr(mac_obj, "address", None) if mac_obj else None

            iface_obj = getattr(nic, "interface", None)
            iface_str = str(getattr(iface_obj, "value", iface_obj or "virtio")).lower()

            prof_obj = getattr(nic, "vnic_profile", None)
            prof_id = str(getattr(prof_obj, "id", "")) if prof_obj else None
            prof_name: str | None = None
            net_name: str | None = None
            if prof_id and prof_id in profile_cache:
                prof_name, net_name = profile_cache[prof_id]

            plugged = bool(getattr(nic, "plugged", True))
            linked = bool(getattr(nic, "linked", True))

            nic_list.append(
                VmNicDetail(
                    id=n_id,
                    name=n_name,
                    mac_address=mac_addr,
                    interface=iface_str,
                    vnic_profile_name=prof_name,
                    vnic_profile_id=prof_id,
                    network_name=net_name,
                    plugged=plugged,
                    linked=linked,
                )
            )
    except Exception as exc:
        logger.warning("Failed to list vNICs for VM '%s': %s", name_or_id, exc)
        raise OvirtMCPError(
            f"Failed to list vNICs for VM '{name_or_id}': {exc}",
            details={"vm": name_or_id, "error": str(exc)},
        ) from exc

    return nic_list


def add_vm_nic_tool(
    name_or_id: str,
    name: str,
    profile: str,
    interface: str = "virtio",
    plugged: bool = True,
    linked: bool = True,
) -> VmNicResult:
    """Add a new virtual network interface card (vNIC) to a virtual machine.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        name: Name for the new vNIC (e.g. 'nic1', 'nic2', 'eth0').
        profile: Name or UUID of the vNIC profile (e.g. 'ovirtmgmt').
        interface: NIC model interface ('virtio', 'e1000', 'rtl8139_virtio').
        plugged: Whether the vNIC is plugged into the VM slot immediately.
        linked: Whether network link is connected (up).

    Returns:
        VmNicResult with created vNIC ID, MAC address, and confirmation.
    """
    require_mutation_allowed("add_vm_nic")

    if not name or not name.strip():
        raise OvirtValidationError("vNIC name cannot be empty.")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    profiles_service = conn.system_service().vnic_profiles_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    prof = client.find_resource_by_id_or_name(profiles_service, profile, "vnic profile")
    prof_id = str(prof.id)

    try:
        iface_enum = sdk_types.NicInterface(interface.lower())
    except ValueError:
        raise OvirtValidationError(
            f"Invalid NIC interface '{interface}'. Valid choices: 'virtio', 'e1000', 'rtl8139_virtio'.",
            details={"interface": interface},
        ) from None

    nic_spec = sdk_types.Nic(
        name=name.strip(),
        interface=iface_enum,
        vnic_profile=sdk_types.VnicProfile(id=prof_id),
        plugged=plugged,
        linked=linked,
    )

    try:
        created = vm_service.nics_service().add(nic_spec)
        nic_id = str(getattr(created, "id", ""))
        mac_obj = getattr(created, "mac", None)
        mac_addr = getattr(mac_obj, "address", None) if mac_obj else None
    except Exception as exc:
        audit_log(
            "add_vm_nic",
            vm_name,
            {"vm_id": vm_id, "nic_name": name, "profile": profile, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to add vNIC '{name}' to VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "nic_name": name, "error": str(exc)},
        ) from exc

    audit_log(
        "add_vm_nic",
        vm_name,
        {"vm_id": vm_id, "nic_id": nic_id, "nic_name": name, "mac_address": mac_addr},
        "SUCCESS",
    )
    return VmNicResult(
        success=True,
        action="add",
        vm_id=vm_id,
        vm_name=vm_name,
        nic_id=nic_id,
        nic_name=name.strip(),
        mac_address=mac_addr,
        message=f"vNIC '{name.strip()}' ({interface}) successfully added to VM '{vm_name}' (profile={profile}).",
    )


def remove_vm_nic_tool(
    name_or_id: str,
    nic_name_or_id: str,
    confirm: bool = False,
) -> VmNicResult:
    """Remove a virtual network interface card (vNIC) from a virtual machine.

    Reversible counterpart to add_vm_nic.
    Destructive action in Safe Mode: requires confirm=True.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        nic_name_or_id: Display name or UUID of the vNIC to remove.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).

    Returns:
        VmNicResult with removal confirmation.
    """
    require_destructive_confirmation(
        f"remove vNIC '{nic_name_or_id}' from VM '{name_or_id}'", confirmed=confirm
    )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    raw_nics = vm_service.nics_service().list()
    target_nic = None
    for n in raw_nics:
        n_id = str(getattr(n, "id", ""))
        n_name = str(getattr(n, "name", ""))
        if nic_name_or_id in (n_id, n_name):
            target_nic = n
            break

    if not target_nic:
        raise OvirtValidationError(
            f"vNIC '{nic_name_or_id}' not found on virtual machine '{vm_name}'.",
            details={"vm_id": vm_id, "nic": nic_name_or_id},
        )

    target_nic_id = str(getattr(target_nic, "id", ""))
    target_nic_name = str(getattr(target_nic, "name", target_nic_id))

    try:
        vm_service.nics_service().nic_service(target_nic_id).remove()
    except Exception as exc:
        audit_log(
            "remove_vm_nic",
            vm_name,
            {"vm_id": vm_id, "nic_id": target_nic_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to remove vNIC '{target_nic_name}' from VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "nic_id": target_nic_id, "error": str(exc)},
        ) from exc

    audit_log(
        "remove_vm_nic",
        vm_name,
        {"vm_id": vm_id, "nic_id": target_nic_id, "nic_name": target_nic_name},
        "SUCCESS",
    )
    return VmNicResult(
        success=True,
        action="remove",
        vm_id=vm_id,
        vm_name=vm_name,
        nic_id=target_nic_id,
        nic_name=target_nic_name,
        message=f"vNIC '{target_nic_name}' ({target_nic_id}) successfully removed from VM '{vm_name}'.",
    )


def list_vnic_profiles_tool(network: str | None = None) -> list[VnicProfileInfo]:
    """List available vNIC profiles across virtual networks in the oVirt / OLVM environment.

    Args:
        network: Optional network name or UUID to filter vNIC profiles.

    Returns:
        List of VnicProfileInfo with profile IDs, names, network bindings, and passthrough flags.
    """
    client = get_client()
    conn = client.get_connection()
    profiles_service = conn.system_service().vnic_profiles_service()
    networks_service = conn.system_service().networks_service()

    # Pre-cache networks for resolving network names
    net_name_cache: dict[str, str] = {}
    try:
        raw_nets = networks_service.list()
        for net in raw_nets:
            n_id = str(getattr(net, "id", ""))
            n_name = str(getattr(net, "name", n_id))
            net_name_cache[n_id] = n_name
    except Exception as net_err:
        logger.debug("Transient error listing networks: %s", net_err)

    target_net_id: str | None = None
    if network:
        net = client.find_resource_by_id_or_name(networks_service, network, "network")
        target_net_id = str(net.id)

    profile_list: list[VnicProfileInfo] = []
    try:
        raw_profiles = profiles_service.list()
        for p in raw_profiles:
            p_id = str(getattr(p, "id", ""))
            p_name = str(getattr(p, "name", p_id))
            net_obj = getattr(p, "network", None)
            net_id: str | None = str(getattr(net_obj, "id", "")) if net_obj else None
            net_name: str | None = None
            if net_id:
                net_name = net_name_cache.get(net_id)
            if not net_name and net_obj:
                raw_name = getattr(net_obj, "name", None)
                net_name = str(raw_name) if raw_name else None

            if target_net_id and net_id != target_net_id:
                continue

            pt = bool(getattr(p, "pass_through", False))
            pm = bool(getattr(p, "port_mirroring", False))

            profile_list.append(
                VnicProfileInfo(
                    id=p_id,
                    name=p_name,
                    network_name=net_name,
                    network_id=net_id,
                    pass_through=pt,
                    port_mirroring=pm,
                )
            )
    except Exception as exc:
        logger.warning("Failed to list vNIC profiles: %s", exc)
        raise OvirtMCPError(
            f"Failed to list vNIC profiles: {exc}",
            details={"network": network, "error": str(exc)},
        ) from exc

    return profile_list
