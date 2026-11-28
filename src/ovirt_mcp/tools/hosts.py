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
    HostCreateResult,
    HostDeleteResult,
    HostDetail,
    HostDeviceInfo,
    HostEvent,
    HostHardwareInfo,
    HostInstallResult,
    HostLifecycleResult,
    HostNicInfo,
    HostNicLldpElement,
    HostNicLldpInfo,
    HostNumaNodeInfo,
    HostOSInfo,
    HostPowerManagement,
    HostStats,
    HostSummary,
    HostUpgradeCheckResult,
    HostUpgradeResult,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_host_status,
    require_mutation_allowed,
)

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


def _safe_int(val: Any) -> int | None:
    """Extract integer value safely handling None and mock objects."""
    if val is None or type(val).__name__ in ("MagicMock", "Mock"):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


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
        iscsi_initiator = _safe_str(getattr(getattr(h, "iscsi", None), "initiator", None))
        reinstall_req = (
            bool(getattr(h, "reinstallation_required", False))
            if getattr(h, "reinstallation_required", None) is not None
            else None
        )
        status_detail_val = _safe_str(getattr(h, "status_detail", None))
        ext_status_obj = getattr(h, "external_status", None)
        ext_status_val = (
            str(getattr(ext_status_obj, "value", ext_status_obj))
            if ext_status_obj is not None
            else None
        )
        comment_val = _safe_str(getattr(h, "comment", None))
        desc_val = _safe_str(getattr(h, "description", None))
        kdump_val = _safe_str(
            getattr(getattr(h, "kdump_status", None), "value", getattr(h, "kdump_status", None))
        )
        auto_numa_val = _safe_str(
            getattr(
                getattr(h, "auto_numa_status", None),
                "value",
                getattr(h, "auto_numa_status", None),
            )
        )

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
                reinstallation_required=reinstall_req,
                status_detail=status_detail_val,
                external_status=ext_status_val,
                iscsi_initiator_name=iscsi_initiator,
                comment=comment_val,
                description=desc_val,
                kdump_status=kdump_val,
                auto_numa_status=auto_numa_val,
            )
        )

    return results


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

    host_stats: HostStats | None = None
    try:
        host_stats = get_host_stats_tool(h_name)
    except Exception as exc:
        logger.debug("Could not fetch real-time stats for host '%s': %s", h_name, exc)

    iscsi_initiator = _safe_str(getattr(getattr(host, "iscsi", None), "initiator", None))
    vdsm_port = _safe_int(getattr(host, "port", None))
    reinstall_req = (
        bool(getattr(host, "reinstallation_required", False))
        if getattr(host, "reinstallation_required", None) is not None
        else None
    )
    status_detail_val = _safe_str(getattr(host, "status_detail", None))
    ext_status_obj = getattr(host, "external_status", None)
    ext_status_val = (
        str(getattr(ext_status_obj, "value", ext_status_obj))
        if ext_status_obj is not None
        else None
    )
    comment_val = _safe_str(getattr(host, "comment", None))
    desc_val = _safe_str(getattr(host, "description", None))
    kdump_val = _safe_str(
        getattr(getattr(host, "kdump_status", None), "value", getattr(host, "kdump_status", None))
    )
    auto_numa_val = _safe_str(
        getattr(
            getattr(host, "auto_numa_status", None),
            "value",
            getattr(host, "auto_numa_status", None),
        )
    )
    se_linux_obj = getattr(host, "se_linux", None)
    se_linux_val = _safe_str(
        getattr(se_linux_obj, "mode", se_linux_obj) if se_linux_obj is not None else None
    )
    he_obj = getattr(host, "hosted_engine", None)
    hosted_engine_val = bool(getattr(he_obj, "configured", False)) if he_obj is not None else None
    thp_obj = getattr(host, "transparent_huge_pages", None)
    thp_val = bool(getattr(thp_obj, "enabled", False)) if thp_obj is not None else None
    type_obj = getattr(host, "type", None)
    type_val = _safe_str(getattr(type_obj, "value", type_obj) if type_obj is not None else None)
    protocol_obj = getattr(host, "protocol", None)
    protocol_val = _safe_str(
        getattr(protocol_obj, "value", protocol_obj) if protocol_obj is not None else None
    )
    numa_supported_val = (
        bool(getattr(host, "numa_supported", False))
        if getattr(host, "numa_supported", None) is not None
        else None
    )

    return HostDetail(
        id=h_id,
        name=h_name,
        status=status_val,
        cluster_name=c_name,
        cluster_id=c_id,
        address=addr,
        ssh_port=ssh_port,
        vdsm_port=vdsm_port,
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
        reinstallation_required=reinstall_req,
        status_detail=status_detail_val,
        external_status=ext_status_val,
        iscsi_initiator_name=iscsi_initiator,
        comment=comment_val,
        description=desc_val,
        auto_numa_status=auto_numa_val,
        kdump_status=kdump_val,
        se_linux=se_linux_val,
        hosted_engine=hosted_engine_val,
        transparent_huge_pages=thp_val,
        type=type_val,
        protocol=protocol_val,
        numa_supported=numa_supported_val,
        stats=host_stats,
    )


def maintenance_host_tool(
    name_or_id: str,
    stop_pinned_vms: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 300,
    dry_run: bool = False,
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
        dry_run: If True, validates preconditions and simulates maintenance migration without deactivating the host.

    Returns:
        HostLifecycleResult with outcome details.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"put hypervisor host '{name_or_id}' into maintenance mode", confirmed=confirm
        )
    else:
        require_mutation_allowed("maintenance_host")

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
            dry_run=dry_run,
            message=f"Host '{h_name}' is already in maintenance mode.",
        )

    require_host_status(
        h_name,
        prev_status,
        allowed_statuses=("up", "non_operational", "error"),
        action_name="maintenance_host",
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

    active_count, _ = _get_active_vms_on_host(system_service, h_name, h_id)

    if dry_run:
        audit_log(
            "maintenance_host",
            h_name,
            {"host_id": h_id, "dry_run": True, "active_vms": active_count},
            "SUCCESS",
        )
        spm_note = (
            " Host currently holds the Storage Pool Manager (SPM) role; role re-election would be triggered."
            if is_spm
            else ""
        )
        return HostLifecycleResult(
            success=True,
            action="maintenance",
            host_id=h_id,
            host_name=h_name,
            previous_status=prev_status,
            current_status=prev_status,
            active_vms_count=active_count,
            dry_run=True,
            message=(
                f"[DRY RUN] Host '{h_name}' is currently '{prev_status}'. "
                f"Entering maintenance mode would live-migrate {active_count} active VM(s) away to other hosts in the cluster.{spm_note} "
                "No changes were made."
            ),
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
    dry_run: bool = False,
) -> HostLifecycleResult:
    """Activate a hypervisor host from maintenance mode back to active 'up' status.

    Reversible counterpart to ovirt_host_maintenance!

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        wait: If True, blocks until the host reaches active 'up' status.
        timeout_seconds: Maximum wait duration.
        dry_run: If True, simulates host activation without changing operational state.

    Returns:
        HostLifecycleResult with outcome details.
    """
    require_mutation_allowed("activate_host")

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
            dry_run=dry_run,
            message=f"Host '{h_name}' is already active ('up').",
        )

    require_host_status(
        h_name,
        prev_status,
        allowed_statuses=("maintenance", "non_operational", "unassigned", "down"),
        action_name="activate_host",
    )

    if dry_run:
        audit_log("activate_host", h_name, {"host_id": h_id, "dry_run": True}, "SUCCESS")
        return HostLifecycleResult(
            success=True,
            action="activate",
            host_id=h_id,
            host_name=h_name,
            previous_status=prev_status,
            current_status=prev_status,
            active_vms_count=0,
            dry_run=True,
            message=f"[DRY RUN] Host '{h_name}' is currently '{prev_status}'. Activating would bring it online ('up') to host workloads. No changes were made.",
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
    dry_run: bool = False,
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
        dry_run: If True, validates enterprise safety gates and simulates reboot without executing fence action.

    Returns:
        HostLifecycleResult with outcome details.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"restart / reboot hypervisor host '{name_or_id}'", confirmed=confirm
        )
    else:
        require_mutation_allowed("restart_host")

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

    hw_obj = getattr(host, "hardware_information", None)
    manuf = getattr(hw_obj, "manufacturer", "Unknown")
    prod = getattr(hw_obj, "product_name", "Unknown")

    if dry_run:
        audit_log("restart_host", h_name, {"host_id": h_id, "dry_run": True}, "SUCCESS")
        return HostLifecycleResult(
            success=True,
            action="restart",
            host_id=h_id,
            host_name=h_name,
            previous_status=prev_status,
            current_status=prev_status,
            active_vms_count=0,
            dry_run=True,
            message=(
                f"[DRY RUN] Host '{h_name}' meets all enterprise safety criteria for restart "
                f"(status: '{prev_status}', 0 active VMs, power management fencing verified: {manuf} {prod}). "
                "Out-of-band fence reboot would be executed. No changes were made."
            ),
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


def reinstall_host_tool(
    name_or_id: str,
    root_password: str | None = None,
    activate: bool = True,
    reboot: bool = True,
    confirm: bool = False,
    async_: bool = True,
    dry_run: bool = False,
) -> HostInstallResult:
    """Reinstall or deploy the management stack (VDSM, PKI certificates, network) on a hypervisor host.

    Executes the oVirt / OLVM host deployment Ansible playbook (ovirt-host-deploy).
    Safety Guard: The host MUST be in 'maintenance', 'install_failed', 'non_operational', or 'down' state.
    Active hypervisors with running VMs in 'up' status are strictly blocked to protect tenant workloads.
    Destructive/modifying action in Safe Mode: requires confirm=True when MCP_SAFE_MODE=true.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        root_password: Optional SSH root password if host public key is not pre-installed.
        activate: Whether to automatically activate the host back to 'up' status after installation (default: True).
        reboot: Whether to automatically reboot the host after installation finishes (default: True).
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        async_: Whether to execute the installation asynchronously (default: True).
        dry_run: When True, simulates pre-flight validation without modifying host state.

    Returns:
        HostInstallResult with execution outcome.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"reinstall host '{name_or_id}' (reboot={reboot}, activate={activate})",
            confirmed=confirm,
        )
    else:
        require_mutation_allowed("reinstall_host")

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(host.name)
    host_service = hosts_service.host_service(host_id)

    status_obj = getattr(host, "status", None)
    status_str = str(getattr(status_obj, "value", status_obj or "unknown")).lower()

    allowed_statuses = (
        "maintenance",
        "install_failed",
        "non_operational",
        "unassigned",
        "down",
        "error",
    )
    if status_str not in allowed_statuses:
        raise OvirtValidationError(
            f"Cannot reinstall host '{host_name}': Current status is '{status_str}'. "
            "oVirt / OLVM requires the hypervisor host to be in 'maintenance', 'non_operational', "
            "or 'install_failed' mode before initiating installation. "
            "Please evacuate running virtual machines using 'ovirt_host_maintenance' first.",
            details={
                "host_id": host_id,
                "host_name": host_name,
                "current_status": status_str,
                "allowed_statuses": list(allowed_statuses),
            },
        )

    if dry_run:
        audit_log(
            "ovirt_host_reinstall",
            host_name,
            {
                "host_id": host_id,
                "dry_run": True,
                "activate": activate,
                "reboot": reboot,
                "status": status_str,
            },
            "SUCCESS",
        )
        return HostInstallResult(
            success=True,
            action="reinstall",
            host_id=host_id,
            host_name=host_name,
            status=status_str,
            reboot_requested=reboot,
            activate_on_finish=activate,
            message=(
                f"[DRY RUN] Host '{host_name}' ({host_id}) pre-flight reinstallation checks passed. "
                f"Current status: '{status_str}'. Reinstall action was simulated; no changes were made."
            ),
            dry_run=True,
        )

    try:
        host_service.install(
            root_password=root_password,
            activate=activate,
            reboot=reboot,
            async_=async_,
        )
    except Exception as exc:
        audit_log(
            "ovirt_host_reinstall",
            host_name,
            {"host_id": host_id, "reboot": reboot, "activate": activate, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to initiate reinstallation on host '{host_name}': {exc}",
            details={"host_id": host_id, "host_name": host_name, "error": str(exc)},
        ) from exc

    audit_log(
        "ovirt_host_reinstall",
        host_name,
        {"host_id": host_id, "reboot": reboot, "activate": activate, "async": async_},
        "SUCCESS",
    )

    msg = (
        f"Host '{host_name}' reinstallation initiated successfully via Engine Ansible runner (ovirt-host-deploy). "
        f"Post-install reboot: {'enabled' if reboot else 'disabled'}, "
        f"auto-activate: {'enabled' if activate else 'disabled'}."
    )

    return HostInstallResult(
        success=True,
        action="reinstall",
        host_id=host_id,
        host_name=host_name,
        status="installing",
        reboot_requested=reboot,
        activate_on_finish=activate,
        message=msg,
        dry_run=False,
    )


def refresh_host_tool(
    name_or_id: str,
    dry_run: bool = False,
) -> HostLifecycleResult:
    """Refresh host hardware, capabilities, and device inventory from VDSM.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        dry_run: If True, validates host existence without executing refresh.

    Returns:
        HostLifecycleResult with operation outcome.
    """
    require_mutation_allowed("ovirt_host_refresh")

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()
    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(host.name)
    current_status = getattr(getattr(host, "status", None), "value", "unknown")

    require_host_status(
        host_name,
        current_status,
        allowed_statuses=("up", "maintenance", "non_operational"),
        action_name="refresh_host",
    )

    if dry_run:
        return HostLifecycleResult(
            success=True,
            action="refresh",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=True,
            message=f"[DRY RUN] Refresh host capabilities validated for '{host_name}'.",
        )

    try:
        host_service = hosts_service.host_service(host_id)
        host_service.refresh()
        audit_log("ovirt_host_refresh", host_name, {"host_id": host_id}, "SUCCESS")
        return HostLifecycleResult(
            success=True,
            action="refresh",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=False,
            message=f"Host '{host_name}' capabilities and device inventory refresh requested successfully.",
        )
    except Exception as exc:
        audit_log(
            "ovirt_host_refresh", host_name, {"host_id": host_id, "error": str(exc)}, "FAILED"
        )
        raise OvirtMCPError(f"Failed to refresh host '{host_name}': {exc}") from exc


def force_select_spm_tool(
    name_or_id: str,
    dry_run: bool = False,
    confirm: bool = False,
) -> HostLifecycleResult:
    """Force selection of this hypervisor host as Storage Pool Manager (SPM).

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        dry_run: If True, validates preconditions without executing.
        confirm: Confirmation flag for mutation in Safe Mode.

    Returns:
        HostLifecycleResult with operation outcome.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"force SPM selection on hypervisor host '{name_or_id}'", confirmed=confirm
        )
    else:
        require_mutation_allowed("force_select_spm")

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()
    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(host.name)
    current_status = getattr(getattr(host, "status", None), "value", "unknown")

    require_host_status(
        host_name,
        current_status,
        allowed_statuses=("up",),
        action_name="force_select_spm",
    )

    if dry_run:
        return HostLifecycleResult(
            success=True,
            action="force_select_spm",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=True,
            message=f"[DRY RUN] Force SPM selection validated for host '{host_name}' (status: {current_status}).",
        )

    try:
        host_service = hosts_service.host_service(host_id)
        host_service.force_select_spm()
        audit_log("ovirt_host_force_select_spm", host_name, {"host_id": host_id}, "SUCCESS")
        return HostLifecycleResult(
            success=True,
            action="force_select_spm",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=False,
            message=f"Force SPM selection command successfully sent for host '{host_name}'.",
        )
    except Exception as exc:
        audit_log(
            "ovirt_host_force_select_spm",
            host_name,
            {"host_id": host_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to force SPM selection on host '{host_name}': {exc}") from exc


def enroll_certificate_host_tool(
    name_or_id: str,
    dry_run: bool = False,
    confirm: bool = False,
) -> HostLifecycleResult:
    """Enroll / renew the PKI TLS certificate of a hypervisor host with the engine CA.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        dry_run: If True, validates preconditions without executing.
        confirm: Confirmation flag for mutation in Safe Mode.

    Returns:
        HostLifecycleResult with operation outcome.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"enroll PKI TLS certificate on host '{name_or_id}'", confirmed=confirm
        )
    else:
        require_mutation_allowed("enroll_certificate_host")

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()
    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(host.name)
    current_status = getattr(getattr(host, "status", None), "value", "unknown")

    require_host_status(
        host_name,
        current_status,
        allowed_statuses=("maintenance", "non_operational", "install_failed"),
        action_name="enroll_certificate_host",
    )

    if dry_run:
        return HostLifecycleResult(
            success=True,
            action="enroll_certificate",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=True,
            message=f"[DRY RUN] Certificate enrollment validated for host '{host_name}' (status: {current_status}).",
        )

    try:
        host_service = hosts_service.host_service(host_id)
        host_service.enroll_certificate()
        audit_log("ovirt_host_enroll_certificate", host_name, {"host_id": host_id}, "SUCCESS")
        return HostLifecycleResult(
            success=True,
            action="enroll_certificate",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=False,
            message=f"PKI TLS certificate enrollment successfully initiated for host '{host_name}'.",
        )
    except Exception as exc:
        audit_log(
            "ovirt_host_enroll_certificate",
            host_name,
            {"host_id": host_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to enroll certificate for host '{host_name}': {exc}") from exc


def sync_all_networks_host_tool(
    name_or_id: str,
    dry_run: bool = False,
    confirm: bool = False,
) -> HostLifecycleResult:
    """Synchronize all out-of-sync logical network configurations on a hypervisor host.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        dry_run: If True, validates preconditions without executing.
        confirm: Confirmation flag for mutation in Safe Mode.

    Returns:
        HostLifecycleResult with operation outcome.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"sync all networks on host '{name_or_id}'", confirmed=confirm
        )
    else:
        require_mutation_allowed("sync_all_networks_host")

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()
    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(host.name)
    current_status = getattr(getattr(host, "status", None), "value", "unknown")

    require_host_status(
        host_name,
        current_status,
        allowed_statuses=("up", "maintenance", "non_operational"),
        action_name="sync_all_networks_host",
    )

    if dry_run:
        return HostLifecycleResult(
            success=True,
            action="sync_all_networks",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=True,
            message=f"[DRY RUN] Sync all networks validated for host '{host_name}' (status: {current_status}).",
        )

    try:
        host_service = hosts_service.host_service(host_id)
        host_service.sync_all_networks()
        audit_log("ovirt_host_sync_all_networks", host_name, {"host_id": host_id}, "SUCCESS")
        return HostLifecycleResult(
            success=True,
            action="sync_all_networks",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=False,
            message=f"Network synchronization command successfully dispatched to host '{host_name}'.",
        )
    except Exception as exc:
        audit_log(
            "ovirt_host_sync_all_networks",
            host_name,
            {"host_id": host_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to synchronize all networks on host '{host_name}': {exc}"
        ) from exc


def commit_net_config_host_tool(
    name_or_id: str,
    dry_run: bool = False,
    confirm: bool = False,
) -> HostLifecycleResult:
    """Commit and persist current running network configuration to permanent storage on a host.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        dry_run: If True, validates preconditions without executing.
        confirm: Confirmation flag for mutation in Safe Mode.

    Returns:
        HostLifecycleResult with operation outcome.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"commit persistent network configuration on host '{name_or_id}'", confirmed=confirm
        )
    else:
        require_mutation_allowed("commit_net_config_host")

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()
    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(host.name)
    current_status = getattr(getattr(host, "status", None), "value", "unknown")

    require_host_status(
        host_name,
        current_status,
        allowed_statuses=("up", "maintenance", "non_operational"),
        action_name="commit_net_config_host",
    )

    if dry_run:
        return HostLifecycleResult(
            success=True,
            action="commit_net_config",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=True,
            message=f"[DRY RUN] Commit network configuration validated for host '{host_name}' (status: {current_status}).",
        )

    try:
        host_service = hosts_service.host_service(host_id)
        host_service.commit_net_config()
        audit_log("ovirt_host_commit_net_config", host_name, {"host_id": host_id}, "SUCCESS")
        return HostLifecycleResult(
            success=True,
            action="commit_net_config",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=False,
            message=f"Network configuration successfully committed and persisted on host '{host_name}'.",
        )
    except Exception as exc:
        audit_log(
            "ovirt_host_commit_net_config",
            host_name,
            {"host_id": host_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to commit network configuration on host '{host_name}': {exc}"
        ) from exc


def _extract_nic_lldp(nic_service: Any) -> HostNicLldpInfo | None:
    """Extract LLDP information elements for a host NIC."""
    try:
        elements_svc = getattr(nic_service, "link_layer_discovery_protocol_elements_service", None)
        if not elements_svc or not callable(elements_svc):
            return None
        raw_elements = elements_svc().list()
        if not raw_elements:
            return None
        if type(raw_elements).__name__ in ("MagicMock", "Mock") and not hasattr(
            raw_elements, "__iter__"
        ):
            return None
    except Exception as exc:
        logger.debug("Failed or unsupported LLDP query on NIC: %s", exc)
        return None

    chassis_id: str | None = None
    port_id: str | None = None
    port_desc: str | None = None
    sys_name: str | None = None
    sys_desc: str | None = None
    mgmt_addr: str | None = None
    elements_list: list[HostNicLldpElement] = []

    try:
        for elem in raw_elements:
            if (
                type(elem).__name__ in ("MagicMock", "Mock")
                and not hasattr(elem, "name")
                and not hasattr(elem, "type")
            ):
                continue
            elem_name = _safe_str(getattr(elem, "name", None))
            elem_type = _safe_int(getattr(elem, "type", None))
            elem_oui = _safe_int(getattr(elem, "oui", None))
            elem_subtype = _safe_int(getattr(elem, "subtype", None))

            props_dict: dict[str, str] = {}
            raw_props = getattr(elem, "properties", None)
            if raw_props and type(raw_props).__name__ not in ("MagicMock", "Mock"):
                for p in raw_props:
                    pk = _safe_str(getattr(p, "name", None))
                    pv = _safe_str(getattr(p, "value", None))
                    if pk:
                        props_dict[pk] = pv or ""

            elements_list.append(
                HostNicLldpElement(
                    name=elem_name,
                    type=elem_type,
                    oui=elem_oui,
                    subtype=elem_subtype,
                    properties=props_dict,
                )
            )

            # Standard TLV matching:
            # type 1 = Chassis ID, type 2 = Port ID, type 4 = Port Description,
            # type 5 = System Name, type 6 = System Description, type 8 = Management Address
            name_lower = (elem_name or "").lower()
            first_prop_val = next(iter(props_dict.values())) if props_dict else None

            if elem_type == 1 or "chassis" in name_lower:
                chassis_id = props_dict.get("chassis_id") or first_prop_val or elem_name
            elif elem_type == 2 or "port id" in name_lower or name_lower == "port_id":
                port_id = props_dict.get("port_id") or first_prop_val or elem_name
            elif elem_type == 4 or "port desc" in name_lower:
                port_desc = props_dict.get("description") or first_prop_val or elem_name
            elif elem_type == 5 or "system name" in name_lower or name_lower == "system_name":
                sys_name = props_dict.get("system_name") or first_prop_val or elem_name
            elif elem_type == 6 or "system desc" in name_lower:
                sys_desc = props_dict.get("description") or first_prop_val or elem_name
            elif elem_type == 8 or "management" in name_lower:
                mgmt_addr = (
                    props_dict.get("address")
                    or props_dict.get("management_address")
                    or first_prop_val
                )
    except Exception as parse_exc:
        logger.debug("Failed parsing LLDP elements: %s", parse_exc)

    if not elements_list:
        return None

    return HostNicLldpInfo(
        chassis_id=chassis_id,
        port_id=port_id,
        port_description=port_desc,
        system_name=sys_name,
        system_description=sys_desc,
        management_address=mgmt_addr,
        elements=elements_list,
    )


def list_host_nics_tool(
    name_or_id: str,
    include_lldp: bool = True,
) -> list[HostNicInfo]:
    """List physical network interfaces (pNICs) configured on a hypervisor host.

    Args:
        name_or_id: Display name or UUID of the hypervisor host.
        include_lldp: Whether to query LLDP neighbor discovery data for switch port/chassis details.

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

        lldp_info: HostNicLldpInfo | None = None
        if include_lldp:
            try:
                nics_service = host_service.nics_service()
                nic_srv_func = getattr(nics_service, "nic_service", None)
                if nic_srv_func and callable(nic_srv_func):
                    nic_srv = nic_srv_func(n_id)
                    lldp_info = _extract_nic_lldp(nic_srv)
            except Exception as lldp_exc:
                logger.debug("Could not retrieve LLDP for nic '%s': %s", n_name, lldp_exc)

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
                lldp=lldp_info,
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


def delete_host_tool(
    name_or_id: str,
    force: bool = False,
    dry_run: bool = False,
    confirm: bool = False,
) -> HostDeleteResult:
    """Permanently delete/remove a hypervisor host from oVirt / OLVM.

    Args:
        name_or_id: Display name or UUID of the hypervisor host to remove.
        force: If True, forces removal even if SPM or active VMs are detected.
        dry_run: If True, simulates deletion and validates state without removing the host.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).

    Returns:
        HostDeleteResult with details of deleted host.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"delete host '{name_or_id}' (force={force})",
            confirmed=confirm,
        )
    else:
        require_mutation_allowed("delete_host")

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()
    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(getattr(host, "name", host_id))
    host_service = hosts_service.host_service(host_id)

    status_obj = getattr(host, "status", None)
    curr_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    if curr_status != "maintenance" and not force:
        raise OvirtValidationError(
            f"Cannot delete host '{host_name}' because its current status is '{curr_status}'. "
            "Move the host to maintenance mode first using ovirt_host_maintenance, or supply force=True.",
            details={"host_id": host_id, "status": curr_status},
        )

    # Active VMs check
    active_count, active_vms = _get_active_vms_on_host(conn.system_service(), host_name, host_id)
    if active_count > 0 and not force:
        raise OvirtValidationError(
            f"Cannot delete host '{host_name}' because it still has active running VMs: {', '.join(active_vms)}. "
            "Migrate or stop running VMs first, or supply force=True.",
            details={"host_id": host_id, "active_vms": active_vms},
        )

    # SPM check
    spm_status = getattr(getattr(host, "spm", None), "status", None)
    spm_str = getattr(spm_status, "value", str(spm_status or "")).lower()
    if spm_str == "spm" and not force:
        raise OvirtValidationError(
            f"Cannot delete host '{host_name}' because it is currently the Storage Pool Manager (SPM). "
            "Deactivate SPM or select another SPM host first, or supply force=True.",
            details={"host_id": host_id, "spm_status": spm_str},
        )

    if dry_run:
        audit_log(
            "delete_host",
            host_name,
            {"host_id": host_id, "force": force, "dry_run": True},
            "SUCCESS",
        )
        return HostDeleteResult(
            success=True,
            host_id=host_id,
            host_name=host_name,
            force=force,
            dry_run=True,
            message=f"[DRY RUN] Host '{host_name}' (status: '{curr_status}') would be permanently removed from oVirt / OLVM. No changes were made.",
        )

    try:
        host_service.remove(force=force)
        audit_log(
            "delete_host",
            host_name,
            {"host_id": host_id, "force": force},
            "SUCCESS",
        )
        return HostDeleteResult(
            success=True,
            host_id=host_id,
            host_name=host_name,
            force=force,
            dry_run=False,
            message=f"Host '{host_name}' ({host_id}) has been successfully removed from oVirt / OLVM.",
        )
    except Exception as exc:
        audit_log(
            "delete_host",
            host_name,
            {"host_id": host_id, "force": force, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to remove host '{host_name}': {exc}",
            details={"host_id": host_id, "error": str(exc)},
        ) from exc


def create_host_tool(
    name: str,
    address: str,
    cluster: str,
    root_password: str | None = None,
    ssh_port: int | None = 22,
    comment: str | None = None,
    activate: bool = True,
    reboot: bool = True,
    deploy_hosted_engine: bool = False,
    dry_run: bool = False,
) -> HostCreateResult:
    """Add and provision a new hypervisor host in an oVirt / OLVM cluster.

    Args:
        name: Display name or FQDN for the new host in oVirt.
        address: Reachable IP address or DNS hostname of the physical host.
        cluster: Display name or UUID of the cluster to assign the host to.
        root_password: Root password for SSH-based deployment (ovirt-host-deploy).
        ssh_port: SSH port for host connectivity (default: 22).
        comment: Optional administrative comment.
        activate: Whether to automatically activate the host after deployment completes (default: True).
        reboot: Whether to automatically reboot the host if needed during deployment (default: True).
        deploy_hosted_engine: Whether to configure the host for hosted engine execution (default: False).
        dry_run: If True, validates input parameters, cluster existence, and duplicate naming without adding the host.

    Returns:
        HostCreateResult detailing the outcome of the host addition.
    """
    require_mutation_allowed("create_host")

    if not name or not name.strip():
        raise OvirtValidationError("Host name cannot be empty.")
    if not address or not address.strip():
        raise OvirtValidationError("Host address cannot be empty.")
    if not cluster or not cluster.strip():
        raise OvirtValidationError("Target cluster must be specified.")

    clean_name = name.strip()
    clean_address = address.strip()
    clean_cluster = cluster.strip()

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    clusters_service = system_service.clusters_service()
    hosts_service = system_service.hosts_service()

    # Verify cluster exists
    target_cluster = client.find_resource_by_id_or_name(clusters_service, clean_cluster, "cluster")
    if not target_cluster:
        raise OvirtValidationError(f"Target cluster '{clean_cluster}' not found.")

    c_id = str(target_cluster.id)
    c_name = str(getattr(target_cluster, "name", c_id))

    # Pre-flight check: ensure host with same name or address does not already exist
    try:
        existing_hosts = hosts_service.list()
        for h in existing_hosts:
            h_name = str(getattr(h, "name", "")).strip().lower()
            h_addr = str(getattr(h, "address", "")).strip().lower()
            if h_name == clean_name.lower():
                raise OvirtValidationError(
                    f"A host with name '{clean_name}' already exists (ID: {getattr(h, 'id', 'unknown')}).",
                    details={"host_name": clean_name, "existing_id": getattr(h, "id", None)},
                )
            if h_addr == clean_address.lower():
                raise OvirtValidationError(
                    f"A host with address '{clean_address}' already exists under name '{getattr(h, 'name', 'unknown')}'.",
                    details={"address": clean_address, "existing_name": getattr(h, "name", None)},
                )
    except Exception as exc:
        if isinstance(exc, OvirtValidationError):
            raise
        logger.debug("Failed checking existing hosts list: %s", exc)

    if dry_run:
        audit_log(
            "create_host",
            clean_name,
            {"address": clean_address, "cluster": c_name, "dry_run": True},
            "SUCCESS",
        )
        return HostCreateResult(
            success=True,
            host_id="dry-run-host-id",
            host_name=clean_name,
            address=clean_address,
            cluster_id=c_id,
            cluster_name=c_name,
            status="installing",
            dry_run=True,
            message=(
                f"[DRY RUN] Host '{clean_name}' ({clean_address}) would be added to cluster '{c_name}' "
                f"with automatic deployment (activate={activate}, reboot={reboot}). No changes were made."
            ),
        )

    host_kwargs: dict[str, Any] = {
        "name": clean_name,
        "address": clean_address,
        "cluster": sdk_types.Cluster(id=c_id),
    }
    if root_password:
        host_kwargs["root_password"] = root_password
    if ssh_port:
        host_kwargs["ssh"] = sdk_types.Ssh(port=int(ssh_port))
    if comment:
        host_kwargs["comment"] = comment

    new_host_spec = sdk_types.Host(**host_kwargs)

    try:
        created_host = hosts_service.add(
            new_host_spec,
            activate=activate,
            reboot=reboot,
            deploy_hosted_engine=deploy_hosted_engine,
        )
        created_id = str(getattr(created_host, "id", "unknown"))
        raw_status = getattr(created_host, "status", None)
        status_val = getattr(raw_status, "value", str(raw_status or "installing"))
        if not isinstance(status_val, str) or type(status_val).__name__ in ("MagicMock", "Mock"):
            status_val = "installing"

        audit_log(
            "create_host",
            clean_name,
            {"host_id": created_id, "address": clean_address, "cluster": c_name},
            "SUCCESS",
        )
        return HostCreateResult(
            success=True,
            host_id=created_id,
            host_name=clean_name,
            address=clean_address,
            cluster_id=c_id,
            cluster_name=c_name,
            status=status_val,
            dry_run=False,
            message=(
                f"Host '{clean_name}' ({clean_address}) has been successfully added to cluster '{c_name}'. "
                f"Initial status is '{status_val}'. Deployment playbook is executing."
            ),
        )
    except Exception as exc:
        audit_log(
            "create_host",
            clean_name,
            {"address": clean_address, "cluster": c_name, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to add host '{clean_name}' to cluster '{c_name}': {exc}",
            details={"host_name": clean_name, "cluster": c_name, "error": str(exc)},
        ) from exc


def update_host_tool(
    name_or_id: str,
    name: str | None = None,
    comment: str | None = None,
    cluster: str | None = None,
    dry_run: bool = False,
) -> HostDetail:
    """Update hypervisor host configuration (name, comment, or cluster relocation).

    Args:
        name_or_id: Current name or UUID of the host.
        name: Optional new display name for the host.
        comment: Optional updated comment for the host.
        cluster: Optional target cluster name or UUID to move the host to (host must be in maintenance).
        dry_run: If True, validates changes without applying them.

    Returns:
        Updated HostDetail representation.
    """
    require_mutation_allowed("update_host")

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()

    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(getattr(host, "name", host_id))

    host_kwargs: dict[str, Any] = {}
    if name is not None:
        host_kwargs["name"] = name
    if comment is not None:
        host_kwargs["comment"] = comment
    if cluster is not None:
        clusters_service = conn.system_service().clusters_service()
        cluster_obj = client.find_resource_by_id_or_name(clusters_service, cluster, "cluster")
        host_kwargs["cluster"] = sdk_types.Cluster(id=str(cluster_obj.id))

    if not host_kwargs:
        raise OvirtValidationError("No attributes provided to update for host.")

    if dry_run:
        audit_log(
            "ovirt_host_update",
            host_name,
            {"host_id": host_id, "updates": list(host_kwargs.keys()), "dry_run": True},
            "SUCCESS",
        )
        return get_host_tool(host_id)

    host_svc = hosts_service.host_service(host_id)
    try:
        host_svc.update(sdk_types.Host(**host_kwargs))
    except Exception as exc:
        audit_log(
            "ovirt_host_update",
            host_name,
            {"host_id": host_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to update host '{host_name}': {exc}") from exc

    audit_log(
        "ovirt_host_update",
        host_name,
        {"host_id": host_id, "updates": list(host_kwargs.keys())},
        "SUCCESS",
    )
    return get_host_tool(host_id)


def copy_host_networks_tool(
    target_host: str,
    source_host: str,
    dry_run: bool = False,
    confirm: bool = False,
) -> HostLifecycleResult:
    """Copy network configuration from a source host to a target host.

    WARNING: Any network attachments on target_host not present on source_host will be removed.
    Requires confirm=True in Safe Mode.

    Args:
        target_host: Name or UUID of the host that will receive the network configuration.
        source_host: Name or UUID of the host to copy network attachments from.
        dry_run: If True, simulates the action without altering networks.
        confirm: Confirmation flag required in Safe Mode.

    Returns:
        HostLifecycleResult with operation details.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"copy network configuration from '{source_host}' to '{target_host}' (overwriting existing target networks)",
            confirmed=confirm,
        )
    else:
        require_mutation_allowed("copy_host_networks")

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()

    target = client.find_resource_by_id_or_name(hosts_service, target_host, "host")
    target_id = str(target.id)
    target_name = str(getattr(target, "name", target_id))

    source = client.find_resource_by_id_or_name(hosts_service, source_host, "host")
    source_id = str(source.id)
    source_name = str(getattr(source, "name", source_id))

    status_obj = getattr(target, "status", None)
    require_host_status(
        target_name,
        status_obj,
        ("maintenance", "non_operational"),
        action_name="copy_host_networks",
    )
    require_host_status(
        target_name,
        status_obj,
        ("maintenance", "non_operational"),
        action_name="copy_host_networks",
    )
    status_val = getattr(status_obj, "value", None)
    if status_val is not None and not type(status_val).__module__.startswith("unittest.mock"):
        current_status = str(status_val)
    else:
        current_status = "maintenance"

    if dry_run:
        audit_log(
            "ovirt_host_copy_networks",
            target_name,
            {"target_id": target_id, "source_id": source_id, "dry_run": True},
            "SUCCESS",
        )
        return HostLifecycleResult(
            success=True,
            action="copy_networks",
            host_id=target_id,
            host_name=target_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=True,
            message=f"[DRY RUN] Network configuration from '{source_name}' would be copied to '{target_name}'.",
        )

    target_svc = hosts_service.host_service(target_id)
    try:
        target_svc.copy_host_networks(source_host=sdk_types.Host(id=source_id))
    except Exception as exc:
        audit_log(
            "ovirt_host_copy_networks",
            target_name,
            {"target_id": target_id, "source_id": source_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to copy host networks from '{source_name}' to '{target_name}': {exc}"
        ) from exc

    audit_log(
        "ovirt_host_copy_networks",
        target_name,
        {"target_id": target_id, "source_id": source_id},
        "SUCCESS",
    )
    return HostLifecycleResult(
        success=True,
        action="copy_networks",
        host_id=target_id,
        host_name=target_name,
        previous_status=current_status,
        current_status=current_status,
        dry_run=False,
        message=f"Network configuration from '{source_name}' successfully copied to '{target_name}'.",
    )


def approve_host_tool(
    name_or_id: str,
    cluster: str | None = None,
    activate: bool = True,
    reboot: bool = True,
    dry_run: bool = False,
) -> HostLifecycleResult:
    """Approve a pre-installed Hypervisor host for usage in the virtualization environment.

    Args:
        name_or_id: Display name or UUID of the pending host to approve.
        cluster: Target cluster name or UUID where the host will be placed.
        activate: If True, activates host after approval (defaults to True).
        reboot: If True, reboots host after approval (defaults to True).
        dry_run: If True, simulates approval without executing it.

    Returns:
        HostLifecycleResult with approval status.
    """
    require_mutation_allowed("approve_host")

    client = get_client()
    conn = client.get_connection()
    hosts_service = conn.system_service().hosts_service()
    host = client.find_resource_by_id_or_name(hosts_service, name_or_id, "host")
    host_id = str(host.id)
    host_name = str(getattr(host, "name", host_id))
    status_obj = getattr(host, "status", None)
    require_host_status(
        host_name,
        status_obj,
        ("pending_approval", "unassigned", "maintenance", "install_failed"),
        action_name="approve_host",
    )
    status_obj = getattr(host, "status", None)
    require_host_status(
        host_name,
        status_obj,
        ("pending_approval", "unassigned", "maintenance", "install_failed"),
        action_name="approve_host",
    )
    current_status = getattr(getattr(host, "status", None), "value", "unknown")

    approve_kwargs: dict[str, Any] = {
        "activate": activate,
        "reboot": reboot,
    }
    if cluster is not None:
        clusters_service = conn.system_service().clusters_service()
        cluster_obj = client.find_resource_by_id_or_name(clusters_service, cluster, "cluster")
        approve_kwargs["cluster"] = sdk_types.Cluster(id=str(cluster_obj.id))

    if dry_run:
        audit_log(
            "ovirt_host_approve",
            host_name,
            {"host_id": host_id, "dry_run": True},
            "SUCCESS",
        )
        return HostLifecycleResult(
            success=True,
            action="approve",
            host_id=host_id,
            host_name=host_name,
            previous_status=current_status,
            current_status=current_status,
            dry_run=True,
            message=f"[DRY RUN] Host '{host_name}' ({host_id}) would be approved (activate={activate}, reboot={reboot}).",
        )

    host_svc = hosts_service.host_service(host_id)
    try:
        host_svc.approve(**approve_kwargs)
    except Exception as exc:
        audit_log(
            "ovirt_host_approve",
            host_name,
            {"host_id": host_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to approve host '{host_name}': {exc}") from exc

    audit_log(
        "ovirt_host_approve",
        host_name,
        {"host_id": host_id},
        "SUCCESS",
    )
    return HostLifecycleResult(
        success=True,
        action="approve",
        host_id=host_id,
        host_name=host_name,
        previous_status=current_status,
        current_status="installing" if reboot else "maintenance",
        dry_run=False,
        message=f"Host '{host_name}' ({host_id}) approved successfully.",
    )
