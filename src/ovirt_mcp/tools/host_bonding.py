"""Tools for managing Hypervisor Host Network Bonding (LACP, Active-Backup)."""

import logging

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.host_network import HostBondResult
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger("ovirt_mcp.tools.host_bonding")


def create_host_bond_tool(
    host_name_or_id: str,
    bond_name: str,
    slaves: list[str],
    mode: str = "active-backup",
) -> HostBondResult:
    """Create a bonded network interface on a hypervisor host.

    Combines two or more physical interfaces into a high-availability or aggregated link.

    Args:
        host_name_or_id: Name or UUID of the hypervisor host.
        bond_name: Name for the bond device (e.g. 'bond0').
        slaves: List of physical NIC names to enslave (e.g. ['eth1', 'eth2']).
        mode: Bonding mode policy ('active-backup' / mode 1, '802.3ad' / mode 4 LACP, 'balance-rr' / mode 0).

    Returns:
        HostBondResult with bonding outcome.
    """
    require_mutation_allowed("ovirt_host_bond_create")

    bond_name = bond_name.strip()
    if not bond_name:
        raise OvirtValidationError("Bond name cannot be empty.")

    clean_slaves = [s.strip() for s in slaves if s.strip()]
    if len(clean_slaves) < 2:
        raise OvirtValidationError(
            f"Bonding requires at least 2 physical slave interfaces; got {len(clean_slaves)}: {clean_slaves}.",
            details={"slaves": clean_slaves},
        )

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    h_svc = hosts_svc.host_service(host.id)

    # Verify existing host NICs
    existing_nics = h_svc.nics_service().list()
    nic_names = {str(getattr(n, "name", "")) for n in existing_nics}

    # Pre-flight check: All slave interfaces must exist
    missing_slaves = [s for s in clean_slaves if s not in nic_names]
    if missing_slaves:
        raise OvirtValidationError(
            f"Physical slave interface(s) {missing_slaves} not found on host '{host.name}'. "
            f"Available interfaces: {sorted(nic_names)}.",
            details={"missing_slaves": missing_slaves, "host": str(host.name)},
        )

    # Check if bond already exists
    if bond_name in nic_names:
        raise OvirtValidationError(
            f"An interface or bond named '{bond_name}' already exists on host '{host.name}'.",
            details={"bond_name": bond_name, "host": str(host.name)},
        )

    mode_map = {
        "active-backup": "1",
        "balance-rr": "0",
        "802.3ad": "4",
        "balance-xor": "2",
        "broadcast": "3",
        "balance-tlb": "5",
        "balance-alb": "6",
    }
    mode_value = mode_map.get(mode.lower(), mode)

    bond_spec = sdk_types.HostNic(
        name=bond_name,
        bonding=sdk_types.Bonding(
            slaves=[sdk_types.HostNic(name=s) for s in clean_slaves],
            options=[sdk_types.Option(name="mode", value=mode_value)],
        ),
    )

    try:
        h_svc.setup_networks(
            modified_bonds=[bond_spec],
            check_connectivity=True,
            commit_on_success=True,
        )
    except Exception as exc:
        audit_log(
            "ovirt_host_bond_create",
            bond_name,
            {"host": str(host.name), "slaves": clean_slaves, "mode": mode, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to create bond '{bond_name}' on host '{host.name}': {exc}",
            details={"bond_name": bond_name, "host": str(host.name), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_host_bond_create",
        bond_name,
        {"host": str(host.name), "slaves": clean_slaves, "mode": mode},
        "SUCCESS",
    )

    return HostBondResult(
        success=True,
        host_id=str(host.id),
        host_name=str(host.name),
        bond_name=bond_name,
        slaves=clean_slaves,
        action="create",
        message=(
            f"Network bond '{bond_name}' successfully created on host '{host.name}' "
            f"with slaves {clean_slaves} (mode: {mode})."
        ),
    )


def delete_host_bond_tool(
    host_name_or_id: str,
    bond_name: str,
    confirm: bool = False,
) -> HostBondResult:
    """Delete a network bond interface from a hypervisor host.

    Releases slave physical interfaces back to standalone mode. Protected by safe-mode confirmation.

    Args:
        host_name_or_id: Name or UUID of the hypervisor host.
        bond_name: Name of the bond to dismantle (e.g. 'bond0').
        confirm: Confirmation flag required in safe-mode.

    Returns:
        HostBondResult with removal outcome.
    """
    require_destructive_confirmation("ovirt_host_bond_delete", confirm)
    require_mutation_allowed("ovirt_host_bond_delete")

    bond_name = bond_name.strip()
    if not bond_name:
        raise OvirtValidationError("Bond name cannot be empty.")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    h_svc = hosts_svc.host_service(host.id)

    # Verify bond exists
    existing_nics = h_svc.nics_service().list()
    matching_bond = next(
        (n for n in existing_nics if str(getattr(n, "name", "")).lower() == bond_name.lower()),
        None,
    )
    if not matching_bond:
        raise OvirtValidationError(
            f"Bond interface '{bond_name}' not found on host '{host.name}'.",
            details={"bond_name": bond_name, "host": str(host.name)},
        )

    try:
        h_svc.setup_networks(
            removed_bonds=[sdk_types.HostNic(name=bond_name)],
            check_connectivity=True,
            commit_on_success=True,
        )
    except Exception as exc:
        audit_log(
            "ovirt_host_bond_delete",
            bond_name,
            {"host": str(host.name), "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to delete bond '{bond_name}' on host '{host.name}': {exc}",
            details={"bond_name": bond_name, "host": str(host.name), "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_host_bond_delete",
        bond_name,
        {"host": str(host.name)},
        "SUCCESS",
    )

    return HostBondResult(
        success=True,
        host_id=str(host.id),
        host_name=str(host.name),
        bond_name=bond_name,
        slaves=[],
        action="delete",
        message=f"Network bond '{bond_name}' successfully removed from host '{host.name}'.",
    )
