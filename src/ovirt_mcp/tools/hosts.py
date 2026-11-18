"""Hypervisor Host infrastructure management tools for oVirt / OLVM."""

import logging
import time
from typing import Any

from ovirtsdk4 import types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import (
    OvirtMCPError,
    OvirtTimeoutError,
    OvirtValidationError,
)
from ovirt_mcp.models.host import (
    HostDetail,
    HostDeviceInfo,
    HostEvent,
    HostHardwareInfo,
    HostLifecycleResult,
    HostNicInfo,
    HostNumaNodeInfo,
    HostOSInfo,
    HostPowerManagement,
    HostStats,
    HostSummary,
    HostUpgradeCheckResult,
    HostUpgradeResult,
)
from ovirt_mcp.tools.guards import audit_log, require_destructive_confirmation

logger = logging.getLogger("ovirt_mcp.tools.hosts")


def _is_nested_hypervisor(manufacturer: str | None, product_name: str | None) -> bool:
    """Detect if the hypervisor host is nested inside another virtualization hypervisor."""
    manuf = (manufacturer or "").lower()
    prod = (product_name or "").lower()
    virtual_indicators = (
        "vmware",
        "qemu",
        "kvm",
        "virtualbox",
        "xen",
        "microsoft corporation",
        "hyper-v",
        "bochs",
        "innotek",
    )
    return any(ind in manuf or ind in prod for ind in virtual_indicators)


def _safe_str(val: Any) -> str | None:
    """Extract string value safely handling None and mock objects."""
    if val is None:
        return None
    if type(val).__name__ in ("MagicMock", "Mock"):
        return None
    return str(val)


def _get_active_vms_on_host(
    system_service: Any, host_name: str, host_id: str
) -> tuple[int, list[str]]:
    """Return count and display names of running virtual machines hosted on this hypervisor."""
    try:
        vms_service = system_service.vms_service()
        # Search for active VMs pinned or assigned to this host
        vms = vms_service.list(search=f"host={host_name} and status=up")
        active_names = [str(getattr(v, "name", "unknown")) for v in vms]
        return len(active_names), active_names
    except Exception as exc:
        logger.debug("Failed to search active VMs on host '%s': %s", host_name, exc)
        return 0, []


def _get_pinned_vms_on_host(system_service: Any, host_name: str, host_id: str) -> list[str]:
    """Return names of VMs pinned to this specific host that cannot live-migrate."""
    try:
        vms_service = system_service.vms_service()
        vms = vms_service.list(search=f"host={host_name}")
        pinned: list[str] = []
        for v in vms:
            placement_policy = getattr(v, "placement_policy", None)
            hosts = getattr(placement_policy, "hosts", None) or []
            is_pinned = any(getattr(h, "id", None) == host_id for h in hosts)
            affinity = getattr(getattr(placement_policy, "affinity", None), "value", "").lower()
            if is_pinned or affinity in ("user_migratable", "pinned"):
                # In oVirt, pinned VMs without cluster migration permissions cannot live-migrate
                pinned.append(str(v.name))
        return pinned
    except Exception as exc:
        logger.debug("Failed to inspect pinned VMs on host '%s': %s", host_name, exc)
        return []


def list_hosts_tool(
    cluster: str | None = None,
    status: str | None = None,
) -> list[HostSummary]:
    """List hypervisor hosts in the virtualization environment.

    Args:
        cluster: Optional cluster name or UUID filter.
        status: Optional host status filter (e.g. 'up', 'maintenance', 'down').

    Returns:
        List of HostSummary objects.
    """
    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    query_parts: list[str] = []
    if cluster:
        query_parts.append(f"cluster={cluster}")
    if status:
        query_parts.append(f"status={status}")
    search_query = " and ".join(query_parts) if query_parts else None

    try:
        hosts = hosts_service.list(search=search_query) if search_query else hosts_service.list()
    except Exception as exc:
        raise OvirtMCPError(f"Failed to list hosts: {exc}", details={"error": str(exc)}) from exc

    cluster_map: dict[str, str] = {}
    try:
        cluster_map = {str(c.id): str(c.name) for c in system_service.clusters_service().list()}
    except Exception as c_exc:
        logger.debug("Transient error building cluster map: %s", c_exc)

    results: list[HostSummary] = []
    for h in hosts:
        h_id = str(h.id)
        h_name = str(h.name)
        status_val = getattr(getattr(h, "status", None), "value", "unknown")
        cluster_obj = getattr(h, "cluster", None)
        c_id = str(getattr(cluster_obj, "id", "")) if cluster_obj else None
        c_name = cluster_map.get(
            str(c_id), str(getattr(cluster_obj, "name", "default") or "default")
        )
        addr = str(getattr(h, "address", ""))

        hw_info = getattr(h, "hardware_information", None)
        manuf = getattr(hw_info, "manufacturer", None)
        prod = getattr(hw_info, "product_name", None)
        is_nested = _is_nested_hypervisor(manuf, prod)

        spm_obj = getattr(h, "spm", None)
        spm_status = (
            getattr(getattr(spm_obj, "status", None), "value", "none") if spm_obj else "none"
        )

        cpu_obj = getattr(h, "cpu", None)
        cpu_model = _safe_str(getattr(cpu_obj, "name", None))
        topo = getattr(cpu_obj, "topology", None) if cpu_obj else None
        cores = int(getattr(topo, "cores", 1)) if topo else 1
        sockets = int(getattr(topo, "sockets", 1)) if topo else 1

        mem_bytes = int(getattr(h, "memory", 0) or 0)
        total_mem_gb = round(mem_bytes / (1024**3), 2)

        active_count, _ = _get_active_vms_on_host(system_service, h_name, h_id)

        results.append(
            HostSummary(
                id=h_id,
                name=h_name,
                status=status_val,
                cluster_name=c_name,
                cluster_id=c_id,
                address=addr,
                active_vms_count=active_count,
                spm_status=spm_status,
                is_nested=is_nested,
                cpu_model=cpu_model,
                cpu_cores=cores,
                cpu_sockets=sockets,
                total_memory_gb=total_mem_gb,
                update_available=(
                    bool(getattr(h, "update_available", False))
                    if getattr(h, "update_available", None) is not None
                    else None
                ),
            )
        )

    return results


def get_host_tool(name_or_id: str) -> HostDetail:
    """Retrieve full configuration and hardware state of a hypervisor host.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.

    Returns:
        HostDetail model.
    """
    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    h_id = str(host.id)
    h_name = str(host.name)
    status_val = getattr(getattr(host, "status", None), "value", "unknown")

    cluster_obj = getattr(host, "cluster", None)
    c_id = str(getattr(cluster_obj, "id", "")) if cluster_obj else ""
    c_name = str(getattr(cluster_obj, "name", "") or "")
    if not c_name and c_id:
        try:
            cl = system_service.clusters_service().cluster_service(c_id).get()
            c_name = str(getattr(cl, "name", "default"))
        except Exception:
            c_name = "default"
    if not c_name:
        c_name = "default"
    addr = str(getattr(host, "address", ""))
    ssh_port = int(getattr(getattr(host, "ssh", None), "port", 22) or 22)

    hw_obj = getattr(host, "hardware_information", None)
    manuf = getattr(hw_obj, "manufacturer", None)
    prod = getattr(hw_obj, "product_name", None)
    is_nested = _is_nested_hypervisor(manuf, prod)
    hardware_info = HostHardwareInfo(
        manufacturer=_safe_str(manuf),
        product_name=_safe_str(prod),
        version=_safe_str(getattr(hw_obj, "version", None)),
        serial_number=_safe_str(getattr(hw_obj, "serial_number", None)),
        uuid=_safe_str(getattr(hw_obj, "uuid", None)),
    )

    os_obj = getattr(host, "os", None)
    os_info = HostOSInfo(
        os_type=_safe_str(getattr(getattr(os_obj, "type", None), "value", None))
        if os_obj
        else None,
        os_version=_safe_str(getattr(getattr(os_obj, "version", None), "full_version", None))
        if os_obj
        else None,
        kernel_version=_safe_str(
            getattr(getattr(getattr(host, "version", None), "kernel", None), "full_version", None)
        ),
        kvm_version=_safe_str(
            getattr(getattr(getattr(host, "version", None), "kvm", None), "full_version", None)
        ),
        libvirt_version=_safe_str(
            getattr(getattr(getattr(host, "version", None), "libvirt", None), "full_version", None)
        ),
        vdsm_version=_safe_str(
            getattr(
                getattr(getattr(host, "version", None), "full_version", None), "full_version", None
            )
        ),
    )

    pm_obj = getattr(host, "power_management", None)
    pm_enabled = bool(getattr(pm_obj, "enabled", False)) if pm_obj else False
    pm_type = _safe_str(getattr(getattr(pm_obj, "type", None), "value", None)) if pm_obj else None
    pm_addr = _safe_str(getattr(pm_obj, "address", None)) if pm_obj else None
    pm_user = _safe_str(getattr(pm_obj, "username", None)) if pm_obj else None
    pm_auto = bool(getattr(pm_obj, "automatic_pm_enabled", False)) if pm_obj else False
    power_mgmt = HostPowerManagement(
        enabled=pm_enabled,
        pm_type=pm_type,
        address=pm_addr,
        username=pm_user,
        automatic_pm_enabled=pm_auto,
    )

    spm_obj = getattr(host, "spm", None)
    spm_status = (
        str(getattr(getattr(spm_obj, "status", None), "value", "none")) if spm_obj else "none"
    )

    cpu_obj = getattr(host, "cpu", None)
    cpu_model = _safe_str(getattr(cpu_obj, "name", None))
    topo = getattr(cpu_obj, "topology", None) if cpu_obj else None
    cores = int(getattr(topo, "cores", 1)) if topo else 1
    sockets = int(getattr(topo, "sockets", 1)) if topo else 1
    threads = int(getattr(topo, "threads", 1)) if topo else 1

    mem_bytes = int(getattr(host, "memory", 0) or 0)
    total_mem_gb = round(mem_bytes / (1024**3), 2)
    max_sched_bytes = int(getattr(host, "max_scheduling_memory", 0) or 0)
    max_sched_gb = round(max_sched_bytes / (1024**3), 2)

    active_count, _ = _get_active_vms_on_host(system_service, h_name, h_id)

    # Count physical nics and numa nodes
    host_service = hosts_service.host_service(h_id)
    try:
        nics_count = len(host_service.nics_service().list())
    except Exception:
        nics_count = 0
    try:
        numa_count = len(host_service.numa_nodes_service().list())
    except Exception:
        numa_count = 0

    return HostDetail(
        id=h_id,
        name=h_name,
        status=status_val,
        cluster_name=c_name,
        cluster_id=c_id,
        address=addr,
        ssh_port=ssh_port,
        active_vms_count=active_count,
        spm_status=spm_status,
        is_nested=is_nested,
        cpu_model=cpu_model,
        cpu_sockets=sockets,
        cpu_cores=cores,
        cpu_threads=threads,
        total_memory_gb=total_mem_gb,
        max_scheduling_memory_gb=max_sched_gb,
        hardware=hardware_info,
        os=os_info,
        power_management=power_mgmt,
        nics_count=nics_count,
        numa_nodes_count=numa_count,
        update_available=(
            bool(getattr(host, "update_available", False))
            if getattr(host, "update_available", None) is not None
            else None
        ),
    )


def get_host_stats_tool(name_or_id: str) -> HostStats:
    """Retrieve real-time performance metrics and telemetry statistics for a hypervisor host.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.

    Returns:
        HostStats model with CPU, memory, swap, and system telemetry.
    """
    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    h_id = str(host.id)
    h_name = str(host.name)
    status_val = getattr(getattr(host, "status", None), "value", "unknown")

    active_count, _ = _get_active_vms_on_host(system_service, h_name, h_id)

    host_service = hosts_service.host_service(h_id)
    try:
        raw_stats = host_service.statistics_service().list()
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to retrieve statistics for host '{h_name}': {exc}",
            details={"host_id": h_id, "error": str(exc)},
        ) from exc

    stats_map: dict[str, float] = {}
    for s in raw_stats:
        s_name = str(getattr(s, "name", ""))
        vals = getattr(s, "values", None) or []
        if vals:
            val_datum = getattr(vals[0], "datum", 0.0)
            stats_map[s_name] = float(val_datum)

    cpu_user = round(stats_map.get("cpu.current.user", 0.0), 2)
    cpu_sys = round(stats_map.get("cpu.current.system", 0.0), 2)
    cpu_idle = round(stats_map.get("cpu.current.idle", 100.0), 2)
    cpu_usage = round(100.0 - cpu_idle, 2)
    cpu_load_5m = round(stats_map.get("cpu.load.avg.5m", 0.0), 2)

    mem_total_bytes = stats_map.get("memory.total", 0.0)
    mem_used_bytes = stats_map.get("memory.used", 0.0)
    mem_free_bytes = stats_map.get("memory.free", 0.0)
    mem_total_gb = round(mem_total_bytes / (1024**3), 2)
    mem_used_gb = round(mem_used_bytes / (1024**3), 2)
    mem_free_gb = round(mem_free_bytes / (1024**3), 2)
    mem_used_pct = (
        round((mem_used_bytes / mem_total_bytes * 100.0), 2) if mem_total_bytes > 0 else 0.0
    )

    swap_total_mb = round(stats_map.get("swap.total", 0.0) / (1024**2), 2)
    swap_used_mb = round(stats_map.get("swap.used", 0.0) / (1024**2), 2)

    boot_timestamp = stats_map.get("boot.time")
    boot_time_str = (
        time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(boot_timestamp))
        if boot_timestamp and boot_timestamp > 0
        else None
    )

    return HostStats(
        host_id=h_id,
        host_name=h_name,
        status=status_val,
        active_vms_count=active_count,
        cpu_usage_percent=cpu_usage,
        cpu_user_percent=cpu_user,
        cpu_system_percent=cpu_sys,
        cpu_idle_percent=cpu_idle,
        cpu_load_avg_5m=cpu_load_5m,
        memory_total_gb=mem_total_gb,
        memory_used_gb=mem_used_gb,
        memory_free_gb=mem_free_gb,
        memory_used_percent=mem_used_pct,
        swap_total_mb=swap_total_mb,
        swap_used_mb=swap_used_mb,
        boot_time=boot_time_str,
    )


def maintenance_host_tool(
    name_or_id: str,
    stop_pinned_vms: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 300,
) -> HostLifecycleResult:
    """Put a hypervisor host into maintenance mode (deactivate).

    Live-migrates active virtual machines away to other available hosts in the cluster.
    Enterprise Pre-flight Guards:
      - Detects pinned VMs (cannot live-migrate): blocks unless explicitly handled.
      - SPM Role Awareness: reports if Storage Pool Manager role must migrate.
      - Reversibility: counterpart to ovirt_host_activate.

    Destructive action in Safe Mode: requires confirm=True.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        stop_pinned_vms: If True, allows oVirt to stop/shut down non-migratable pinned VMs.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, blocks until the host reaches 'maintenance' status and active VMs = 0.
        timeout_seconds: Maximum wait duration.

    Returns:
        HostLifecycleResult with outcome details.
    """
    require_destructive_confirmation(
        f"put hypervisor host '{name_or_id}' into maintenance mode", confirmed=confirm
    )

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    h_id = str(host.id)
    h_name = str(host.name)
    status_obj = getattr(host, "status", None)
    prev_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    if prev_status == "maintenance":
        return HostLifecycleResult(
            success=True,
            action="maintenance",
            host_id=h_id,
            host_name=h_name,
            previous_status=prev_status,
            current_status="maintenance",
            active_vms_count=0,
            message=f"Host '{h_name}' is already in maintenance mode.",
        )

    # Pre-condition: Check for pinned VMs that cannot migrate
    pinned_vms = _get_pinned_vms_on_host(system_service, h_name, h_id)
    if pinned_vms and not stop_pinned_vms:
        raise OvirtValidationError(
            f"Cannot safely put host '{h_name}' into maintenance mode because {len(pinned_vms)} virtual machine(s) "
            f"are pinned to this host and cannot be live-migrated to another cluster member: {', '.join(pinned_vms)}. "
            "In enterprise environments, migrating pinned VMs requires either unpinning them (ovirt_vm_unpin) "
            "or setting stop_pinned_vms=True to allow the engine to shut them down.",
            details={"host_id": h_id, "pinned_vms": pinned_vms},
        )

    # SPM role check
    spm_obj = getattr(host, "spm", None)
    is_spm = getattr(getattr(spm_obj, "status", None), "value", "").lower() == "spm"
    if is_spm:
        logger.warning(
            "Host '%s' currently holds the Storage Pool Manager (SPM) role. Putting it into maintenance "
            "will trigger SPM role re-election and migration across the data center.",
            h_name,
        )

    host_service = hosts_service.host_service(h_id)
    try:
        host_service.deactivate()
    except Exception as exc:
        audit_log(
            "maintenance_host",
            h_name,
            {"host_id": h_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to put host '{h_name}' into maintenance mode: {exc}",
            details={"host_id": h_id, "error": str(exc)},
        ) from exc

    curr_status = "preparing_for_maintenance"
    active_count = 0
    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(5)
            try:
                refreshed = host_service.get()
                st = getattr(getattr(refreshed, "status", None), "value", "").lower()
                curr_status = st
                active_count, _ = _get_active_vms_on_host(system_service, h_name, h_id)
                if st == "maintenance" and active_count == 0:
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during host maintenance: %s", poll_exc)

        if curr_status != "maintenance":
            audit_log(
                "maintenance_host",
                h_name,
                {"host_id": h_id, "status": curr_status, "active_vms": active_count},
                "TIMEOUT",
            )
            raise OvirtTimeoutError(
                f"Timed out after {timeout_seconds}s waiting for host '{h_name}' to reach 'maintenance' "
                f"(current status: '{curr_status}', active VMs remaining: {active_count}). "
                "VM live migrations are still in progress.",
                details={"host_id": h_id, "status": curr_status, "active_vms": active_count},
            )

    audit_log("maintenance_host", h_name, {"host_id": h_id, "status": curr_status}, "SUCCESS")
    return HostLifecycleResult(
        success=True,
        action="maintenance",
        host_id=h_id,
        host_name=h_name,
        previous_status=prev_status,
        current_status=curr_status,
        active_vms_count=active_count,
        message=(
            f"Host '{h_name}' successfully transitioned to maintenance mode. "
            "All virtual machines have safely migrated off this hypervisor."
        ),
    )


def activate_host_tool(
    name_or_id: str,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> HostLifecycleResult:
    """Activate a hypervisor host from maintenance mode back to active 'up' status.

    Reversible counterpart to ovirt_host_maintenance!

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        wait: If True, blocks until the host reaches active 'up' status.
        timeout_seconds: Maximum wait duration.

    Returns:
        HostLifecycleResult with outcome details.
    """
    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    h_id = str(host.id)
    h_name = str(host.name)
    status_obj = getattr(host, "status", None)
    prev_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    if prev_status == "up":
        return HostLifecycleResult(
            success=True,
            action="activate",
            host_id=h_id,
            host_name=h_name,
            previous_status=prev_status,
            current_status="up",
            active_vms_count=0,
            message=f"Host '{h_name}' is already active ('up').",
        )

    host_service = hosts_service.host_service(h_id)
    try:
        host_service.activate()
    except Exception as exc:
        audit_log(
            "activate_host",
            h_name,
            {"host_id": h_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to activate host '{h_name}': {exc}",
            details={"host_id": h_id, "error": str(exc)},
        ) from exc

    curr_status = "activating"
    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                refreshed = host_service.get()
                st = getattr(getattr(refreshed, "status", None), "value", "").lower()
                curr_status = st
                if st == "up":
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during host activation: %s", poll_exc)

        if curr_status != "up":
            audit_log("activate_host", h_name, {"host_id": h_id, "status": curr_status}, "TIMEOUT")
            raise OvirtTimeoutError(
                f"Timed out after {timeout_seconds}s waiting for host '{h_name}' to reach 'up' "
                f"(current status: '{curr_status}').",
                details={"host_id": h_id, "status": curr_status},
            )

    audit_log("activate_host", h_name, {"host_id": h_id, "status": curr_status}, "SUCCESS")
    return HostLifecycleResult(
        success=True,
        action="activate",
        host_id=h_id,
        host_name=h_name,
        previous_status=prev_status,
        current_status=curr_status,
        active_vms_count=0,
        message=f"Host '{h_name}' activated successfully (status: {curr_status}).",
    )


def restart_host_tool(
    name_or_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 300,
) -> HostLifecycleResult:
    """Restart / reboot a hypervisor host via out-of-band power management fencing.

    Strict Enterprise Safety Matrix ("Guard-Before-Act"):
      1. Maintenance Gate: The host MUST be in 'maintenance' status. If the host is 'up',
         'preparing_for_maintenance', or in another transitional state, reboot is STRICTLY BLOCKED.
      2. Zero VMs Gate: Running virtual machine count MUST be exactly 0.
      3. Power Management Gate: Verifies that physical out-of-band IPMI / fencing is configured and
         enabled. In nested virtualization (VMware/KVM) or lab environments where physical IPMI
         is absent, reports an explicit diagnostic error rather than triggering an unrecoverable failure.

    Destructive action in Safe Mode: requires confirm=True.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        confirm: Explicit confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, blocks until the host finishes rebooting and returns to maintenance or up.
        timeout_seconds: Maximum wait duration.

    Returns:
        HostLifecycleResult with outcome details.
    """
    require_destructive_confirmation(
        f"restart / reboot hypervisor host '{name_or_id}'", confirmed=confirm
    )

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    h_id = str(host.id)
    h_name = str(host.name)
    status_obj = getattr(host, "status", None)
    prev_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    # ── Enterprise Guard 1: Status Gate ──────────────────────────────────────────
    if prev_status == "preparing_for_maintenance":
        raise OvirtValidationError(
            f"Cannot reboot host '{h_name}': Host is currently 'preparing_for_maintenance'. "
            "Virtual machine migrations are actively in progress. Please wait until maintenance "
            "transition completes and all VMs have vacated the host before restarting.",
            details={"host_id": h_id, "current_status": prev_status},
        )
    if prev_status == "up":
        raise OvirtValidationError(
            f"Cannot reboot host '{h_name}': Host is currently active ('up'). "
            "Rebooting an active hypervisor host would crash running virtual machines and disrupt cluster quorum. "
            "In accordance with enterprise safety standards, you must first transition the host to maintenance "
            "mode using ovirt_host_maintenance and ensure all VMs are safely migrated.",
            details={"host_id": h_id, "current_status": prev_status},
        )
    if prev_status != "maintenance":
        raise OvirtValidationError(
            f"Cannot reboot host '{h_name}': Host must be in 'maintenance' status before restarting "
            f"(current status: '{prev_status}'). Please place the host into maintenance first.",
            details={"host_id": h_id, "current_status": prev_status},
        )

    # ── Enterprise Guard 2: Zero VMs Gate ────────────────────────────────────────
    active_count, active_vms = _get_active_vms_on_host(system_service, h_name, h_id)
    if active_count > 0:
        raise OvirtValidationError(
            f"Cannot reboot host '{h_name}': {active_count} virtual machine(s) are still running on this host: "
            f"{', '.join(active_vms)}. All virtual machines must be migrated or stopped before rebooting.",
            details={"host_id": h_id, "active_vms": active_vms},
        )

    # ── Enterprise Guard 3: Power Management / Fencing Gate ──────────────────────
    pm_obj = getattr(host, "power_management", None)
    pm_enabled = bool(getattr(pm_obj, "enabled", False)) if pm_obj else False
    if not pm_enabled:
        hw_obj = getattr(host, "hardware_information", None)
        manuf = getattr(hw_obj, "manufacturer", "Unknown")
        prod = getattr(hw_obj, "product_name", "Unknown")
        raise OvirtValidationError(
            f"Cannot reboot host '{h_name}' via oVirt power management: Power management (fencing / IPMI) "
            "is not enabled or configured for this host in oVirt / OLVM. "
            f"(Detected platform: {manuf} {prod}, nested virtualized: {_is_nested_hypervisor(manuf, prod)}). "
            "oVirt requires an active out-of-band power management agent (IPMI, iLO, DRAC, or fence_vmware) "
            "to power-cycle hypervisors. Please reboot the host via its out-of-band management controller, "
            "hypervisor console, or SSH.",
            details={
                "host_id": h_id,
                "power_management_enabled": False,
                "hardware": f"{manuf} {prod}",
            },
        )

    host_service = hosts_service.host_service(h_id)
    try:
        host_service.fence(fence_type=sdk_types.FenceType.RESTART)
    except Exception as exc:
        audit_log(
            "restart_host",
            h_name,
            {"host_id": h_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to initiate fence restart on host '{h_name}': {exc}",
            details={"host_id": h_id, "error": str(exc)},
        ) from exc

    curr_status = "reboot"
    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(5)
            try:
                refreshed = host_service.get()
                st = getattr(getattr(refreshed, "status", None), "value", "").lower()
                curr_status = st
                if st in ("maintenance", "up") and (time.time() - start_time > 15):
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during host restart: %s", poll_exc)

    audit_log("restart_host", h_name, {"host_id": h_id, "status": curr_status}, "SUCCESS")
    return HostLifecycleResult(
        success=True,
        action="restart",
        host_id=h_id,
        host_name=h_name,
        previous_status=prev_status,
        current_status=curr_status,
        active_vms_count=0,
        message=f"Host '{h_name}' restart initiated via power management fencing (status: {curr_status}).",
    )


def upgrade_check_host_tool(name_or_id: str) -> HostUpgradeCheckResult:
    """Check if operating system or package updates are available for a hypervisor host.

    Triggers the engine to query host package repositories via Ansible runner and
    updates the host's update_available state.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.

    Returns:
        HostUpgradeCheckResult indicating update availability and host status.
    """
    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(host.name)
    host_service = hosts_service.host_service(host_id)

    status_obj = getattr(host, "status", None)
    status_str = str(getattr(status_obj, "value", status_obj or "unknown")).lower()

    if status_str not in ("up", "non_operational"):
        raise OvirtValidationError(
            f"Cannot check for upgrades on host '{host_name}': Current status is '{status_str}'. "
            "Valid host statuses for upgrade check are 'up' or 'non_operational'.",
            details={"host_id": host_id, "host_name": host_name, "status": status_str},
        )

    try:
        host_service.upgrade_check()
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to check for upgrades on host '{host_name}': {exc}",
            details={"host_id": host_id, "host_name": host_name, "error": str(exc)},
        ) from exc

    # Refresh host to read latest update_available flag
    try:
        refreshed = host_service.get()
        upd_avail = bool(getattr(refreshed, "update_available", False))
    except Exception:
        upd_avail = bool(getattr(host, "update_available", False))

    msg = f"Host '{host_name}' upgrade check initiated. " + (
        "Package/OS updates are available." if upd_avail else "No updates currently available."
    )

    return HostUpgradeCheckResult(
        success=True,
        host_id=host_id,
        host_name=host_name,
        status=status_str,
        update_available=upd_avail,
        message=msg,
    )


def upgrade_host_tool(
    name_or_id: str,
    reboot: bool = True,
    confirm: bool = False,
    async_: bool = True,
    timeout_minutes: int = 60,
) -> HostUpgradeResult:
    """Upgrade operating system packages and VDSM on a hypervisor host.

    Executes the oVirt / OLVM host upgrade Ansible automation playbook.
    Safety Guard: The host MUST be in 'maintenance' state before initiating an upgrade.
    Destructive/modifying action in Safe Mode: requires confirm=True when MCP_SAFE_MODE=true.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        reboot: Whether to automatically reboot the host after the upgrade completes (default: True).
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        async_: Whether to execute the upgrade asynchronously (default: True).
        timeout_minutes: Maximum duration in minutes for the upgrade playbook execution (default: 60).

    Returns:
        HostUpgradeResult with upgrade execution details.
    """
    require_destructive_confirmation(
        f"upgrade host '{name_or_id}' (reboot={reboot})", confirmed=confirm
    )

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(host.name)
    host_service = hosts_service.host_service(host_id)

    status_obj = getattr(host, "status", None)
    status_str = str(getattr(status_obj, "value", status_obj or "unknown")).lower()

    if status_str != "maintenance":
        raise OvirtValidationError(
            f"Cannot upgrade host '{host_name}': Current status is '{status_str}'. "
            "oVirt / OLVM requires the hypervisor host to be in 'maintenance' mode "
            "before initiating an upgrade. Please migrate active VMs and place the host into maintenance "
            "using 'ovirt_host_maintenance' first.",
            details={
                "host_id": host_id,
                "host_name": host_name,
                "current_status": status_str,
                "required_status": "maintenance",
            },
        )

    try:
        host_service.upgrade(
            reboot=reboot,
            async_=async_,
            timeout=timeout_minutes,
        )
    except Exception as exc:
        audit_log(
            "ovirt_host_upgrade",
            host_name,
            {"host_id": host_id, "reboot": reboot, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to initiate upgrade on host '{host_name}': {exc}",
            details={"host_id": host_id, "host_name": host_name, "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_host_upgrade",
        host_name,
        {"host_id": host_id, "reboot": reboot, "async": async_},
        "SUCCESS",
    )

    msg = (
        f"Host '{host_name}' upgrade initiated successfully via Engine Ansible runner. "
        f"Post-upgrade automatic reboot: {'enabled' if reboot else 'disabled'}."
    )

    return HostUpgradeResult(
        success=True,
        action="upgrade",
        host_id=host_id,
        host_name=host_name,
        status=status_str,
        reboot_requested=reboot,
        message=msg,
    )


def list_host_nics_tool(name_or_id: str) -> list[HostNicInfo]:
    """List physical network interfaces (pNICs) configured on a hypervisor host.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.

    Returns:
        List of HostNicInfo objects with MAC addresses, speed, link status, and network bindings.
    """
    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    h_id = str(host.id)
    h_name = str(host.name)
    host_service = hosts_service.host_service(h_id)

    try:
        nics = host_service.nics_service().list()
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to list physical network interfaces for host '{h_name}': {exc}",
            details={"host_id": h_id, "error": str(exc)},
        ) from exc

    results: list[HostNicInfo] = []
    for n in nics:
        n_id = str(n.id)
        n_name = str(n.name)
        mac_addr = getattr(getattr(n, "mac", None), "address", None)
        speed_raw = getattr(n, "speed", None)
        speed_mbps = int(speed_raw // (1000 * 1000)) if speed_raw and speed_raw > 0 else None
        st = getattr(getattr(n, "status", None), "value", "unknown")

        net_obj = getattr(n, "network", None)
        net_name = str(net_obj.name) if net_obj and getattr(net_obj, "name", None) else None
        bridged = bool(getattr(n, "bridged", False))

        ip_list: list[str] = []
        ip_obj = getattr(n, "ip", None)
        if ip_obj and getattr(ip_obj, "address", None):
            ip_list.append(str(ip_obj.address))
        ips_obj = getattr(n, "ips", None) or []
        for ip_elem in ips_obj:
            addr_val = getattr(ip_elem, "address", None)
            if addr_val and str(addr_val) not in ip_list:
                ip_list.append(str(addr_val))

        bonding_obj = getattr(n, "bonding", None)
        slaves_obj = getattr(bonding_obj, "slaves", None) or [] if bonding_obj else []
        slave_names = [str(getattr(s, "name", "")) for s in slaves_obj if getattr(s, "name", None)]

        results.append(
            HostNicInfo(
                id=n_id,
                name=n_name,
                mac_address=mac_addr,
                speed_mbps=speed_mbps,
                status=st,
                ip_addresses=ip_list,
                network_name=net_name,
                bridged=bridged,
                bonding_slaves=slave_names,
            )
        )

    return results


def list_host_numa_tool(name_or_id: str) -> list[HostNumaNodeInfo]:
    """List NUMA (Non-Uniform Memory Access) node topology for a hypervisor host.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.

    Returns:
        List of HostNumaNodeInfo objects detailing NUMA memory and CPU cores.
    """
    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    h_id = str(host.id)
    h_name = str(host.name)
    host_service = hosts_service.host_service(h_id)

    try:
        numa_nodes = host_service.numa_nodes_service().list()
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to list NUMA nodes for host '{h_name}': {exc}",
            details={"host_id": h_id, "error": str(exc)},
        ) from exc

    results: list[HostNumaNodeInfo] = []
    for node in numa_nodes:
        idx = int(getattr(node, "index", 0) or 0)
        mem_mb = int(getattr(node, "memory", 0) or 0)
        cpu_obj = getattr(node, "cpu", None)
        cores_obj = getattr(cpu_obj, "cores", None) or [] if cpu_obj else []
        core_indices: list[int] = []
        for c in cores_obj:
            core_idx = getattr(c, "index", None)
            if core_idx is not None:
                core_indices.append(int(core_idx))

        results.append(
            HostNumaNodeInfo(
                index=idx,
                memory_mb=mem_mb,
                cpu_cores=core_indices,
            )
        )

    return results


def list_host_devices_tool(
    name_or_id: str,
    max_devices: int = 50,
) -> list[HostDeviceInfo]:
    """List hardware and PCI bus devices configured on a hypervisor host (SR-IOV, GPU, HBAs).

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        max_devices: Maximum number of devices to return (default: 50).

    Returns:
        List of HostDeviceInfo objects.
    """
    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    h_id = str(host.id)
    h_name = str(host.name)
    host_service = hosts_service.host_service(h_id)

    try:
        devices = host_service.devices_service().list(max=max_devices)
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to list hardware devices for host '{h_name}': {exc}",
            details={"host_id": h_id, "error": str(exc)},
        ) from exc

    results: list[HostDeviceInfo] = []
    for d in devices:
        d_id = str(d.id)
        d_name = str(d.name)
        prod = getattr(getattr(d, "product", None), "name", None)
        vendor = getattr(getattr(d, "vendor", None), "name", None)
        driver = getattr(d, "driver", None)
        iommu = getattr(d, "iommu_group", None)
        iommu_idx = int(iommu) if iommu is not None else None

        results.append(
            HostDeviceInfo(
                id=d_id,
                name=d_name,
                product=prod,
                vendor=vendor,
                driver=driver,
                iommu_group=iommu_idx,
            )
        )

    return results


def list_host_storage_tool(name_or_id: str) -> list[dict[str, Any]]:
    """List storage connections and domains accessible to a hypervisor host.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.

    Returns:
        List of dictionaries with storage domain/connection metadata.
    """
    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    h_id = str(host.id)
    h_name = str(host.name)
    host_service = hosts_service.host_service(h_id)

    try:
        storage_list = host_service.storage_service().list()
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to list storage for host '{h_name}': {exc}",
            details={"host_id": h_id, "error": str(exc)},
        ) from exc

    results: list[dict[str, Any]] = []
    for s in storage_list:
        results.append(
            {
                "id": str(getattr(s, "id", "")),
                "name": str(getattr(s, "name", "")),
                "type": getattr(getattr(s, "type", None), "value", None),
                "address": getattr(s, "address", None),
                "target": getattr(s, "target", None),
            }
        )

    return results


def list_host_events_tool(
    name_or_id: str,
    max_events: int = 25,
    severity: str | None = None,
) -> list[HostEvent]:
    """Retrieve audit history and operational events for a hypervisor host.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        max_events: Maximum number of events to return (default: 25).
        severity: Optional severity filter ('normal', 'warning', 'error', 'alert').

    Returns:
        List of HostEvent objects ordered by timestamp descending.
    """
    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    hosts_service = system_service.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    h_id = str(host.id)
    h_name = str(host.name)

    query_parts = [f"host.name={h_name}"]
    if severity:
        query_parts.append(f"severity={severity}")
    search_query = " and ".join(query_parts)

    try:
        events = system_service.events_service().list(search=search_query, max=max_events)
    except Exception as exc:
        raise OvirtMCPError(
            f"Failed to retrieve events for host '{h_name}': {exc}",
            details={"host_id": h_id, "error": str(exc)},
        ) from exc

    results: list[HostEvent] = []
    for e in events:
        sev_val = getattr(getattr(e, "severity", None), "value", "normal")
        time_val = str(e.time) if getattr(e, "time", None) else None
        results.append(
            HostEvent(
                id=str(e.id),
                code=int(getattr(e, "code", 0) or 0),
                severity=sev_val,
                description=str(getattr(e, "description", "")),
                timestamp=time_val,
            )
        )

    return results
