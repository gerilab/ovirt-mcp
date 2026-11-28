"""Tools for managing VM compute resources (CPU, RAM, HA) and graphics console access."""

import logging
from typing import Any

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.compute import (
    VmConsoleFileInfo,
    VmConsoleTicket,
    VmGraphicsConsoleInfo,
    VmUpdateResult,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
    require_vm_status,
)

logger = logging.getLogger("ovirt_mcp.tools.compute")


def update_vm_tool(
    name_or_id: str,
    memory_mb: int | None = None,
    cpu_cores: int | None = None,
    cpu_sockets: int | None = None,
    cpu_threads: int | None = None,
    description: str | None = None,
    ha_enabled: bool | None = None,
    confirm: bool = False,
) -> VmUpdateResult:
    """Update virtual machine compute resources, CPU topology, RAM, description, or HA.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        memory_mb: New RAM memory allocation in megabytes.
        cpu_cores: Number of CPU cores per socket.
        cpu_sockets: Number of CPU sockets.
        cpu_threads: Number of threads per CPU core.
        description: New description or comment for the VM.
        ha_enabled: Enable or disable High Availability failover for this VM.
        confirm: Confirmation flag required in Safe Mode when modifying compute hardware.

    Returns:
        VmUpdateResult with confirmed resource values.
    """
    require_mutation_allowed("update_vm")

    # If altering hardware resources (CPU, RAM), enforce Safe Mode confirmation
    if any(param is not None for param in (memory_mb, cpu_cores, cpu_sockets, cpu_threads)):
        require_destructive_confirmation(
            f"update compute hardware resources for VM '{name_or_id}'", confirmed=confirm
        )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    # Build update kwargs
    update_kwargs: dict[str, Any] = {}

    if memory_mb is not None:
        if memory_mb <= 0:
            raise OvirtValidationError(f"Memory must be greater than 0 MB, got {memory_mb}.")
        update_kwargs["memory"] = memory_mb * (1024**2)

    # CPU topology
    has_cpu_change = any(p is not None for p in (cpu_cores, cpu_sockets, cpu_threads))
    if has_cpu_change:
        current_cpu = getattr(vm, "cpu", None)
        current_topo = getattr(current_cpu, "topology", None) if current_cpu else None

        def _to_int(val: Any, default: int = 1) -> int:
            try:
                return int(val)
            except (TypeError, ValueError):
                return default

        cur_cores = _to_int(getattr(current_topo, "cores", 1)) if current_topo else 1
        cur_sockets = _to_int(getattr(current_topo, "sockets", 1)) if current_topo else 1
        cur_threads = _to_int(getattr(current_topo, "threads", 1)) if current_topo else 1

        final_cores = cpu_cores if cpu_cores is not None else cur_cores
        final_sockets = cpu_sockets if cpu_sockets is not None else cur_sockets
        final_threads = cpu_threads if cpu_threads is not None else cur_threads

        if final_cores <= 0 or final_sockets <= 0 or final_threads <= 0:
            raise OvirtValidationError("CPU cores, sockets, and threads must be positive integers.")

        update_kwargs["cpu"] = sdk_types.Cpu(
            topology=sdk_types.CpuTopology(
                cores=final_cores,
                sockets=final_sockets,
                threads=final_threads,
            )
        )

    if description is not None:
        update_kwargs["description"] = description

    if ha_enabled is not None:
        update_kwargs["high_availability"] = sdk_types.HighAvailability(enabled=ha_enabled)

    if not update_kwargs:
        raise OvirtValidationError("No resource parameters were provided to update.")

    vm_spec = sdk_types.Vm(**update_kwargs)

    try:
        updated = vm_service.update(vm_spec)
    except Exception as exc:
        audit_log(
            "update_vm",
            vm_name,
            {"vm_id": vm_id, "params": str(update_kwargs), "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to update VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "error": str(exc)},
        ) from exc

    audit_log(
        "update_vm",
        vm_name,
        {"vm_id": vm_id, "memory_mb": memory_mb, "cpu_cores": cpu_cores, "ha_enabled": ha_enabled},
        "SUCCESS",
    )

    # Read back confirmed attributes
    up_mem_bytes = getattr(updated, "memory", None)
    up_mem_mb = int(up_mem_bytes / (1024**2)) if up_mem_bytes else memory_mb
    up_cpu = getattr(updated, "cpu", None)
    up_topo = getattr(up_cpu, "topology", None) if up_cpu else None
    up_cores = getattr(up_topo, "cores", cpu_cores) if up_topo else cpu_cores
    up_sockets = getattr(up_topo, "sockets", cpu_sockets) if up_topo else cpu_sockets
    up_ha = getattr(getattr(updated, "high_availability", None), "enabled", ha_enabled)

    return VmUpdateResult(
        success=True,
        vm_id=vm_id,
        vm_name=vm_name,
        memory_mb=up_mem_mb,
        cpu_cores=up_cores,
        cpu_sockets=up_sockets,
        ha_enabled=up_ha,
        description=description,
        message=f"Virtual machine '{vm_name}' successfully updated.",
    )


def list_vm_graphics_consoles_tool(name_or_id: str) -> list[VmGraphicsConsoleInfo]:
    """List available graphics display consoles (VNC / SPICE) for a virtual machine.

    Args:
        name_or_id: Display name or UUID of the virtual machine.

    Returns:
        List of VmGraphicsConsoleInfo containing display protocols and port assignments.
    """
    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_service = vms_service.vm_service(vm_id)

    results: list[VmGraphicsConsoleInfo] = []
    try:
        raw_consoles = vm_service.graphics_consoles_service().list()
        for c in raw_consoles:
            c_id = str(getattr(c, "id", ""))
            proto_obj = getattr(c, "protocol", None)
            proto_str = str(getattr(proto_obj, "value", proto_obj or "vnc")).lower()
            port = getattr(c, "port", None)
            tls_port = getattr(c, "tls_port", None)

            results.append(
                VmGraphicsConsoleInfo(
                    id=c_id,
                    protocol=proto_str,
                    port=port,
                    tls_port=tls_port,
                )
            )
    except Exception as exc:
        logger.warning("Failed to list graphics consoles for VM '%s': %s", name_or_id, exc)
        raise OvirtMCPError(
            f"Failed to list graphics consoles for VM '{name_or_id}': {exc}",
            details={"vm": name_or_id, "error": str(exc)},
        ) from exc

    return results


def get_vm_console_ticket_tool(
    name_or_id: str,
    expiry_seconds: int = 120,
) -> VmConsoleTicket:
    """Generate a temporary authentication ticket/password for graphical console (VNC / SPICE) access.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        expiry_seconds: Ticket validity lifespan in seconds (default: 120s).

    Returns:
        VmConsoleTicket with access password and connection instructions.
    """
    require_mutation_allowed("get_vm_console_ticket")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    status_obj = getattr(vm, "status", None)
    vm_status = str(getattr(status_obj, "value", status_obj or "")).lower()
    require_vm_status(vm_name, vm_status, ("up",), action_name="get_vm_console_ticket")

    ticket_spec = sdk_types.Ticket(expiry=expiry_seconds)

    try:
        ticket_res = vm_service.ticket(ticket=ticket_spec)
        ticket_val = str(getattr(ticket_res, "value", ""))
    except Exception as exc:
        audit_log(
            "get_vm_console_ticket",
            vm_name,
            {"vm_id": vm_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to generate console ticket for VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "error": str(exc)},
        ) from exc

    audit_log(
        "get_vm_console_ticket",
        vm_name,
        {"vm_id": vm_id, "expiry_seconds": expiry_seconds},
        "SUCCESS",
    )
    return VmConsoleTicket(
        vm_id=vm_id,
        vm_name=vm_name,
        ticket_value=ticket_val,
        expiry_seconds=expiry_seconds,
        message=(
            f"Console authentication ticket generated for VM '{vm_name}'. "
            f"Valid for {expiry_seconds} seconds. Use this ticket with your VNC/SPICE client."
        ),
    )


def get_vm_console_file_tool(
    name_or_id: str,
    protocol: str | None = None,
    expiry_seconds: int = 120,
) -> VmConsoleFileInfo:
    """Generate a complete Virt-Viewer .vv configuration file payload for direct graphical console access.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        protocol: Optional preferred graphics protocol ('spice' or 'vnc'). If None, selects first active console.
        expiry_seconds: Ticket validity lifespan in seconds (default: 120s).

    Returns:
        VmConsoleFileInfo containing the complete .vv file content ready to save or stream to remote-viewer.
    """
    require_mutation_allowed("get_vm_console_file")

    client = get_client()
    conn = client.get_connection()
    sys_service = conn.system_service()
    vms_service = sys_service.vms_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    status_obj = getattr(vm, "status", None)
    vm_status = str(getattr(status_obj, "value", status_obj or "")).lower()
    require_vm_status(vm_name, vm_status, ("up",), action_name="get_vm_console_file")

    consoles = vm_service.graphics_consoles_service().list() or []
    if not consoles:
        raise OvirtValidationError(f"No graphical consoles configured for VM '{vm_name}'.")

    target_console = None
    if protocol:
        p_clean = protocol.strip().lower()
        for gc in consoles:
            proto_val = str(
                getattr(getattr(gc, "protocol", None), "value", getattr(gc, "protocol", ""))
            ).lower()
            if proto_val == p_clean:
                target_console = gc
                break
        if not target_console:
            raise OvirtValidationError(
                f"No graphical console with protocol '{protocol}' found for VM '{vm_name}'."
            )
    else:
        # Default to SPICE if available, else first
        for gc in consoles:
            proto_val = str(
                getattr(getattr(gc, "protocol", None), "value", getattr(gc, "protocol", ""))
            ).lower()
            if proto_val == "spice":
                target_console = gc
                break
        if not target_console:
            target_console = consoles[0]

    chosen_proto = str(
        getattr(
            getattr(target_console, "protocol", None),
            "value",
            getattr(target_console, "protocol", "vnc"),
        )
    ).lower()

    # Generate ticket
    ticket_spec = sdk_types.Ticket(expiry=expiry_seconds)
    try:
        ticket_res = vm_service.ticket(ticket=ticket_spec)
        ticket_val = str(getattr(ticket_res, "value", ""))
    except Exception as exc:
        audit_log("get_vm_console_file", vm_name, {"vm_id": vm_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(f"Failed to generate console ticket for VM '{vm_name}': {exc}") from exc

    # Determine host and port
    host_addr = getattr(target_console, "address", None)
    if not host_addr:
        vm_host = getattr(vm, "host", None)
        if vm_host and getattr(vm_host, "id", None):
            try:
                host_obj = sys_service.hosts_service().host_service(vm_host.id).get()
                host_addr = getattr(host_obj, "address", None) or getattr(host_obj, "name", None)
            except Exception:
                pass
    if not host_addr:
        host_addr = "127.0.0.1"

    port = getattr(target_console, "port", None)
    tls_port = getattr(target_console, "tls_port", None)
    active_port = int(port or tls_port or 5900)

    # Build standard Virt-Viewer .vv file
    vv_lines = [
        "[virt-viewer]",
        f"type={chosen_proto}",
        f"host={host_addr}",
        f"port={active_port}",
        f"password={ticket_val}",
        f"title={vm_name}",
        "delete-this-file=1",
        "fullscreen=0",
        "toggle-fullscreen=shift+f11",
        "release-cursor=shift+f12",
    ]
    if tls_port:
        vv_lines.append(f"tls-port={tls_port}")
    vv_content = "\n".join(vv_lines) + "\n"

    audit_log("get_vm_console_file", vm_name, {"vm_id": vm_id, "protocol": chosen_proto}, "SUCCESS")
    return VmConsoleFileInfo(
        vm_id=vm_id,
        vm_name=vm_name,
        protocol=chosen_proto,
        host=str(host_addr),
        port=active_port,
        ticket_value=ticket_val,
        expiry_seconds=expiry_seconds,
        vv_content=vv_content,
        instructions=(
            f"Save the 'vv_content' to a local file (e.g. '{vm_name}.vv') and launch with: "
            f"`remote-viewer {vm_name}.vv`"
        ),
    )
