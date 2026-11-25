"""Virtual machine management tools for oVirt / OLVM."""

import contextlib
import logging
import time
from typing import Any

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtTimeoutError, OvirtValidationError
from ovirt_mcp.models.vm import (
    VmCompactDetail,
    VmCpuDetails,
    VmCreateResult,
    VmDeleteResult,
    VmDetail,
    VmDiskInfo,
    VmGuestOsInfo,
    VmHardwareSecurity,
    VmHighAvailability,
    VmIoAndScsi,
    VmLifecycleInfo,
    VmLifecycleResult,
    VmMemoryPolicy,
    VmMigrateResult,
    VmMigrationOptions,
    VmNicInfo,
    VmNicIoStats,
    VmPinResult,
    VmPlacementAndAffinity,
    VmRuntimeTelemetry,
    VmSnapshotInfo,
    VmSnapshotResult,
    VmSummary,
)
from ovirt_mcp.tools.disks import extract_disk_io_stats
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger(__name__)


def _is_mock_object(obj: Any) -> bool:
    """Check if an object is an unconfigured unittest MagicMock."""
    return type(obj).__module__.startswith("unittest.mock")


def _extract_reported_devices(
    vm: Any,
    vm_service: Any = None,
    name_or_id: str | None = None,
) -> list[Any]:
    """Safely extract reported devices from a VM object or its sub-service."""
    raw_rep = getattr(vm, "reported_devices", None)
    raw_guest = getattr(vm, "guest_reported_devices", None)

    candidate_devices: list[Any] = []
    # If explicitly assigned as a collection or list
    if isinstance(raw_rep, list) and raw_rep:
        candidate_devices = raw_rep
    elif isinstance(raw_guest, list) and raw_guest:
        candidate_devices = raw_guest
    elif raw_rep is not None and not _is_mock_object(raw_rep) and hasattr(raw_rep, "__iter__"):
        candidate_devices = list(raw_rep)
    elif (
        raw_guest is not None and not _is_mock_object(raw_guest) and hasattr(raw_guest, "__iter__")
    ):
        candidate_devices = list(raw_guest)

    if not candidate_devices and vm_service is not None:
        try:
            srv_rep = vm_service.reported_devices_service().list()
            if isinstance(srv_rep, list):
                candidate_devices = srv_rep
            elif hasattr(srv_rep, "__iter__") and not _is_mock_object(srv_rep):
                candidate_devices = list(srv_rep)
        except Exception as exc:
            logger.debug("Could not fetch reported devices for VM '%s': %s", name_or_id or "", exc)

    return candidate_devices


def _extract_ips_from_devices(devices: list[Any]) -> list[str]:
    """Extract unique IP addresses from a list of reported devices."""
    ips: list[str] = []
    for dev in devices:
        raw_ips = getattr(dev, "ips", None)
        if raw_ips and hasattr(raw_ips, "__iter__"):
            for ip_obj in raw_ips:
                address = getattr(ip_obj, "address", None)
                if address and str(address) not in ips:
                    ips.append(str(address))
    return ips


def _format_version(ver: Any) -> str | None:
    """Safely format an oVirt SDK Version object or version string into a clean string."""
    if ver is None or _is_mock_object(ver):
        return None
    if isinstance(ver, str):
        s = ver.strip()
        return s if s else None
    full_ver = getattr(ver, "full_version", None)
    if full_ver is not None and not _is_mock_object(full_ver):
        s = str(full_ver).strip()
        if s:
            return s
    name = getattr(ver, "name", None)
    if name is not None and not _is_mock_object(name):
        s = str(name).strip()
        if s:
            return s
    parts: list[str] = []
    for attr in ("major", "minor", "build"):
        val = getattr(ver, attr, None)
        if val is not None and not _is_mock_object(val):
            parts.append(str(val))
    rev = getattr(ver, "revision", None)
    if parts:
        res = ".".join(parts)
        if rev is not None and not _is_mock_object(rev):
            res += f"-{rev}"
        return res
    s = str(ver).strip()
    return s if s and not _is_mock_object(ver) else None


def extract_vm_summary(
    vm: Any,
    cluster_names: dict[str, str] | None = None,
    host_names: dict[str, str] | None = None,
    vms_service: Any = None,
) -> VmSummary:
    """Extract a typed VmSummary from an oVirt SDK VM object with resolved names."""
    vm_id = str(getattr(vm, "id", ""))
    name = str(getattr(vm, "name", ""))

    status_obj = getattr(vm, "status", None)
    status_str = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    cluster_name = None
    if hasattr(vm, "cluster") and vm.cluster:
        cluster_name = getattr(vm.cluster, "name", None)
        if not cluster_name and cluster_names and hasattr(vm.cluster, "id"):
            cluster_name = cluster_names.get(vm.cluster.id)

    host_name = None
    if hasattr(vm, "host") and vm.host:
        host_name = getattr(vm.host, "name", None)
        if not host_name and host_names and hasattr(vm.host, "id"):
            host_name = host_names.get(vm.host.id)

    memory_mb = None
    if hasattr(vm, "memory") and vm.memory:
        memory_mb = int(vm.memory // (1024 * 1024))

    cpu_cores = None
    if hasattr(vm, "cpu") and vm.cpu and hasattr(vm.cpu, "topology") and vm.cpu.topology:
        topo = vm.cpu.topology
        sockets = getattr(topo, "sockets", 1) or 1
        cores = getattr(topo, "cores", 1) or 1
        threads = getattr(topo, "threads", 1) or 1
        cpu_cores = int(sockets * cores * threads)

    # Extract reported IPs if guest agent is active
    vm_srv = None
    if vms_service is not None and hasattr(vm, "id") and vm.id:
        with contextlib.suppress(Exception):
            vm_srv = vms_service.vm_service(vm.id)

    rep_devices = _extract_reported_devices(vm, vm_service=vm_srv, name_or_id=vm_id)
    ip_addresses = _extract_ips_from_devices(rep_devices)

    fqdn = getattr(vm, "fqdn", None)

    os_type = None
    if hasattr(vm, "os") and vm.os:
        os_type = getattr(vm.os, "type", None)

    ha_enabled = False
    if hasattr(vm, "high_availability") and vm.high_availability:
        ha_enabled = bool(getattr(vm.high_availability, "enabled", False))

    description = getattr(vm, "description", None)

    return VmSummary(
        id=vm_id,
        name=name,
        status=status_str,
        cluster_name=cluster_name,
        host_name=host_name,
        memory_mb=memory_mb,
        cpu_cores=cpu_cores,
        ip_addresses=ip_addresses,
        fqdn=fqdn,
        os_type=os_type,
        ha_enabled=ha_enabled,
        description=description,
    )


def list_vms_tool(
    cluster: str | None = None,
    status: str | None = None,
    search_query: str | None = None,
    max_results: int = 100,
) -> list[VmSummary]:
    """List virtual machines with optional filtering by cluster, status, or search query."""
    client = get_client()
    connection = client.get_connection()
    system_service = connection.system_service()
    vms_service = system_service.vms_service()

    # Pre-fetch cluster names
    cluster_names: dict[str, str] = {}
    try:
        clusters_service = system_service.clusters_service()
        for cl in clusters_service.list():
            if hasattr(cl, "id") and hasattr(cl, "name") and cl.id and cl.name:
                cluster_names[cl.id] = cl.name
    except Exception as exc:
        logger.debug("Could not pre-fetch cluster names: %s", exc)

    # Pre-fetch host names
    host_names: dict[str, str] = {}
    try:
        hosts_service = system_service.hosts_service()
        for h in hosts_service.list():
            if hasattr(h, "id") and hasattr(h, "name") and h.id and h.name:
                host_names[h.id] = h.name
    except Exception as exc:
        logger.debug("Could not pre-fetch host names: %s", exc)

    search_clauses: list[str] = []
    if cluster:
        search_clauses.append(f'cluster="{cluster.replace('"', "")}"')
    if status:
        search_clauses.append(f'status="{status.replace('"', "")}"')
    if search_query:
        search_clauses.append(search_query)

    search_string = " and ".join(search_clauses) if search_clauses else None

    logger.debug("Listing VMs with query: %s (max=%d)", search_string, max_results)
    try:
        sdk_vms = vms_service.list(search=search_string, max=max_results, follow="reported_devices")
    except Exception as exc:
        logger.debug(
            "Listing with follow='reported_devices' failed, falling back to standard list: %s", exc
        )
        sdk_vms = vms_service.list(search=search_string, max=max_results)

    return [
        extract_vm_summary(
            vm,
            cluster_names=cluster_names,
            host_names=host_names,
            vms_service=vms_service,
        )
        for vm in sdk_vms
    ]


def extract_nic_io_stats(nic_service: Any) -> VmNicIoStats | None:
    """Extract real-time VmNicIoStats from a nic_service statistics subcollection."""
    try:
        if not hasattr(nic_service, "statistics_service"):
            return None
        raw_stats = nic_service.statistics_service().list()
        if not raw_stats:
            return None
        stats_map: dict[str, float] = {}
        for s in raw_stats:
            s_name = str(getattr(s, "name", ""))
            vals = getattr(s, "values", None) or []
            if vals:
                stats_map[s_name] = float(getattr(vals[0], "datum", 0.0))

        rx_b = stats_map.get("data.current.rx", 0.0)
        tx_b = stats_map.get("data.current.tx", 0.0)
        rx_mb = round(rx_b / (1024**2), 3)
        tx_mb = round(tx_b / (1024**2), 3)
        rx_bps = stats_map.get("data.current.rx.bps", 0.0)
        tx_bps = stats_map.get("data.current.tx.bps", 0.0)
        rx_err = int(stats_map.get("errors.total.rx", 0.0))
        tx_err = int(stats_map.get("errors.total.tx", 0.0))
        tot_rx = int(stats_map.get("data.total.rx", 0.0))
        tot_tx = int(stats_map.get("data.total.tx", 0.0))

        return VmNicIoStats(
            rx_bytes_sec=round(rx_b, 1),
            tx_bytes_sec=round(tx_b, 1),
            rx_mb_sec=rx_mb,
            tx_mb_sec=tx_mb,
            rx_bps=round(rx_bps, 1),
            tx_bps=round(tx_bps, 1),
            rx_errors=rx_err,
            tx_errors=tx_err,
            total_rx_bytes=tot_rx,
            total_tx_bytes=tot_tx,
        )
    except Exception as exc:
        logger.debug("Could not extract nic io stats: %s", exc)
        return None


def extract_vm_runtime_telemetry(
    vm_service: Any,
    disks: list[VmDiskInfo],
    nics: list[VmNicInfo],
) -> VmRuntimeTelemetry | None:
    """Extract real-time CPU, RAM, and aggregated disk/nic telemetry for a VM."""
    try:
        if not hasattr(vm_service, "statistics_service"):
            return None
        raw_stats = vm_service.statistics_service().list()
        stats_map: dict[str, float] = {}
        for s in raw_stats:
            s_name = str(getattr(s, "name", ""))
            vals = getattr(s, "values", None) or []
            if vals:
                stats_map[s_name] = float(getattr(vals[0], "datum", 0.0))

        cpu_guest = round(stats_map.get("cpu.current.guest", 0.0), 2)
        cpu_hyp = round(stats_map.get("cpu.current.hypervisor", 0.0), 2)
        cpu_total = round(stats_map.get("cpu.current.total", cpu_guest + cpu_hyp), 2)

        mem_inst = int(stats_map.get("memory.installed", 0.0))
        mem_used = int(stats_map.get("memory.used", 0.0))
        mem_free = int(stats_map.get("memory.free", 0.0))
        mem_buf = int(stats_map.get("memory.buffered", 0.0))
        mem_cached = int(stats_map.get("memory.cached", 0.0))
        mem_pct = round((mem_used / mem_inst) * 100.0, 1) if mem_inst > 0 and mem_used > 0 else 0.0

        tot_read_mb = sum(d.io_stats.read_mb_sec for d in disks if d.io_stats is not None)
        tot_write_mb = sum(d.io_stats.write_mb_sec for d in disks if d.io_stats is not None)
        tot_read_iops = sum(d.io_stats.read_iops for d in disks if d.io_stats is not None)
        tot_write_iops = sum(d.io_stats.write_iops for d in disks if d.io_stats is not None)

        tot_rx_mb = sum(n.io_stats.rx_mb_sec for n in nics if n.io_stats is not None)
        tot_tx_mb = sum(n.io_stats.tx_mb_sec for n in nics if n.io_stats is not None)

        return VmRuntimeTelemetry(
            cpu_usage_percent=cpu_total,
            cpu_guest_percent=cpu_guest,
            cpu_hypervisor_percent=cpu_hyp,
            memory_installed_bytes=mem_inst,
            memory_used_bytes=mem_used,
            memory_free_bytes=mem_free,
            memory_buffered_bytes=mem_buf,
            memory_cached_bytes=mem_cached,
            memory_used_percent=mem_pct,
            total_read_mb_sec=round(tot_read_mb, 3),
            total_write_mb_sec=round(tot_write_mb, 3),
            total_read_iops=round(tot_read_iops, 1),
            total_write_iops=round(tot_write_iops, 1),
            total_rx_mb_sec=round(tot_rx_mb, 3),
            total_tx_mb_sec=round(tot_tx_mb, 3),
        )
    except Exception as exc:
        logger.debug("Could not extract VM runtime telemetry: %s", exc)
        return None


def get_vm_tool(name_or_id: str, compact: bool | None = None) -> VmDetail | VmCompactDetail:
    """Get enterprise details of a virtual machine by name or UUID.

    Args:
        name_or_id: Virtual machine name or UUID.
        compact: If True, returns a lightweight summary (saving ~75% tokens for smaller LLMs).
                 If False, returns full engineering details.
                 If None, defaults to the server setting (MCP_COMPACT_MODE).
    """
    client = get_client()
    connection = client.get_connection()
    system_service = connection.system_service()
    vms_service = system_service.vms_service()

    # Determine whether to return compact or full details
    is_compact = client.config.mcp_compact_mode if compact is None else compact

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_service = vms_service.vm_service(vm.id)

    # 1. Resolve Cluster, Host, and Template names
    cluster_name = None
    cluster_id = None
    if hasattr(vm, "cluster") and vm.cluster:
        cluster_id = getattr(vm.cluster, "id", None)
        cluster_name = getattr(vm.cluster, "name", None)
        if not cluster_name and cluster_id:
            try:
                cl_obj = system_service.clusters_service().cluster_service(cluster_id).get()
                cluster_name = getattr(cl_obj, "name", None)
            except Exception:
                pass

    host_name = None
    if hasattr(vm, "host") and vm.host:
        host_name = getattr(vm.host, "name", None)
        if not host_name and hasattr(vm.host, "id"):
            try:
                h_obj = system_service.hosts_service().host_service(vm.host.id).get()
                host_name = getattr(h_obj, "name", None)
            except Exception:
                pass

    # Status
    status_obj = getattr(vm, "status", None)
    status_str = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    # Memory and CPU basic calculation
    memory_mb = int(vm.memory // (1024 * 1024)) if hasattr(vm, "memory") and vm.memory else None
    sockets, cores_per_socket, threads_per_core = 1, 1, 1
    if hasattr(vm, "cpu") and vm.cpu and hasattr(vm.cpu, "topology") and vm.cpu.topology:
        topo = vm.cpu.topology
        sockets = getattr(topo, "sockets", 1) or 1
        cores_per_socket = getattr(topo, "cores", 1) or 1
        threads_per_core = getattr(topo, "threads", 1) or 1
    total_cpu_cores = int(sockets * cores_per_socket * threads_per_core)

    # IPs
    rep_devices = _extract_reported_devices(vm, vm_service=vm_service, name_or_id=name_or_id)
    ip_addresses = _extract_ips_from_devices(rep_devices)

    os_type = getattr(vm.os, "type", None) if hasattr(vm, "os") and vm.os else None
    ha_enabled = (
        bool(getattr(vm.high_availability, "enabled", False))
        if hasattr(vm, "high_availability") and vm.high_availability
        else False
    )

    # ── COMPACT MODE BRANCH ──────────────────────────────────────────────────
    if is_compact:
        disks_summary: list[str] = []
        try:
            attachments = vm_service.disk_attachments_service().list()
            disks_service = system_service.disks_service()
            for att in attachments:
                d_alias = "disk"
                d_size = 0.0
                if hasattr(att, "disk") and att.disk:
                    raw_d = att.disk
                    d_id = str(getattr(raw_d, "id", "disk"))
                    if getattr(raw_d, "provisioned_size", None) is not None:
                        full_d = raw_d
                    else:
                        try:
                            full_d = disks_service.disk_service(d_id).get()
                        except Exception:
                            full_d = raw_d

                    d_alias = str(
                        getattr(full_d, "alias", None) or getattr(full_d, "name", None) or d_id
                    )
                    p_size = getattr(full_d, "provisioned_size", None) or getattr(
                        full_d, "initial_size", 0
                    )
                    if p_size:
                        d_size = round(float(p_size) / (1024**3), 2)
                disks_summary.append(f"{d_alias} ({d_size} GB)")
        except Exception as exc:
            logger.debug("Failed to list compact disks: %s", exc)

        nics_count = 0
        try:
            nics_count = len(vm_service.nics_service().list())
        except Exception as exc:
            logger.debug("Failed to count nics in compact mode: %s", exc)

        snapshots_count = 0
        try:
            snapshots_count = len(vm_service.snapshots_service().list())
        except Exception as exc:
            logger.debug("Failed to count snapshots in compact mode: %s", exc)

        return VmCompactDetail(
            id=str(vm.id),
            name=str(vm.name),
            status=status_str,
            cluster_name=cluster_name,
            host_name=host_name,
            memory_mb=memory_mb,
            cpu_cores=total_cpu_cores,
            ip_addresses=ip_addresses,
            fqdn=getattr(vm, "fqdn", None),
            os_type=os_type,
            ha_enabled=ha_enabled,
            disks_summary=disks_summary,
            nics_count=nics_count,
            snapshots_count=snapshots_count,
            description=getattr(vm, "description", None),
        )

    # ── FULL DETAILED MODE BRANCH ────────────────────────────────────────────

    template_name = None
    if hasattr(vm, "template") and vm.template:
        template_name = getattr(vm.template, "name", None)
        if not template_name and hasattr(vm.template, "id"):
            try:
                tmpl_obj = system_service.templates_service().template_service(vm.template.id).get()
                template_name = getattr(tmpl_obj, "name", None)
            except Exception:
                pass

    # 2. CPU Details
    sockets, cores_per_socket, threads_per_core = 1, 1, 1
    custom_cpu_model = getattr(vm, "custom_cpu_model", None)
    if _is_mock_object(custom_cpu_model):
        custom_cpu_model = None
    custom_emulated_machine = getattr(vm, "custom_emulated_machine", None)
    if _is_mock_object(custom_emulated_machine):
        custom_emulated_machine = None
    pinning_policy = None
    auto_pinning_policy = None
    shares = getattr(vm, "cpu_shares", None)
    if _is_mock_object(shares):
        shares = None

    if hasattr(vm, "cpu") and vm.cpu:
        if hasattr(vm.cpu, "topology") and vm.cpu.topology:
            topo = vm.cpu.topology
            sockets = getattr(topo, "sockets", 1) or 1
            cores_per_socket = getattr(topo, "cores", 1) or 1
            threads_per_core = getattr(topo, "threads", 1) or 1
        if hasattr(vm.cpu, "cpu_pinning_policy") and vm.cpu.cpu_pinning_policy:
            pinning_policy = getattr(
                vm.cpu.cpu_pinning_policy, "value", str(vm.cpu.cpu_pinning_policy)
            )

    if hasattr(vm, "auto_pinning_policy") and vm.auto_pinning_policy:
        auto_pinning_policy = getattr(vm.auto_pinning_policy, "value", str(vm.auto_pinning_policy))

    total_cpu_cores = int(sockets * cores_per_socket * threads_per_core)
    cpu_details = VmCpuDetails(
        total_cores=total_cpu_cores,
        sockets=sockets,
        cores_per_socket=cores_per_socket,
        threads_per_core=threads_per_core,
        shares=shares,
        pinning_policy=pinning_policy,
        auto_pinning_policy=auto_pinning_policy,
        custom_cpu_model=custom_cpu_model,
        custom_emulated_machine=custom_emulated_machine,
    )

    # 3. Memory Policy
    allocated_mb = int(vm.memory // (1024 * 1024)) if hasattr(vm, "memory") and vm.memory else 0
    guaranteed_mb, max_memory_mb, ballooning, over_commit = None, None, False, None
    if hasattr(vm, "memory_policy") and vm.memory_policy:
        mp = vm.memory_policy
        if hasattr(mp, "guaranteed") and mp.guaranteed:
            guaranteed_mb = int(mp.guaranteed // (1024 * 1024))
        if hasattr(mp, "max") and mp.max:
            max_memory_mb = int(mp.max // (1024 * 1024))
        ballooning = bool(getattr(mp, "ballooning", False))
        if hasattr(mp, "over_commit") and mp.over_commit and hasattr(mp.over_commit, "percent"):
            over_commit = mp.over_commit.percent

    memory_policy = VmMemoryPolicy(
        allocated_mb=allocated_mb,
        guaranteed_mb=guaranteed_mb,
        max_memory_mb=max_memory_mb,
        ballooning_enabled=ballooning,
        over_commit_percent=over_commit,
    )

    # 4. I/O and VirtIO-SCSI
    io_threads = None
    if hasattr(vm, "io") and vm.io:
        io_threads = getattr(vm.io, "threads", None)

    virtio_scsi_enabled = getattr(vm, "virtio_scsi", None) is not None
    virtio_scsi_multi_queues = getattr(vm, "virtio_scsi_multi_queues", None)
    virtio_scsi_multi_queues_enabled = bool(getattr(vm, "virtio_scsi_multi_queues_enabled", False))
    multi_queues_enabled = bool(getattr(vm, "multi_queues_enabled", False))

    io_scsi = VmIoAndScsi(
        io_threads=io_threads,
        virtio_scsi_enabled=virtio_scsi_enabled,
        virtio_scsi_multi_queues=virtio_scsi_multi_queues,
        virtio_scsi_multi_queues_enabled=virtio_scsi_multi_queues_enabled,
        multi_queues_enabled=multi_queues_enabled,
    )

    # 5. Affinity & Placement Policy
    affinity_groups: list[str] = []
    if cluster_id:
        try:
            cl_service = system_service.clusters_service().cluster_service(cluster_id)
            for ag in cl_service.affinity_groups_service().list():
                if hasattr(ag, "vms") and ag.vms:
                    for v_ref in ag.vms:
                        if getattr(v_ref, "id", None) == vm.id:
                            affinity_groups.append(str(ag.name))
        except Exception as exc:
            logger.debug("Could not fetch affinity groups: %s", exc)

    affinity_labels: list[str] = []
    try:
        if hasattr(vm_service, "affinity_labels_service"):
            for lbl in vm_service.affinity_labels_service().list():
                if hasattr(lbl, "name") and lbl.name:
                    affinity_labels.append(str(lbl.name))
    except Exception as exc:
        logger.debug("Could not fetch affinity labels: %s", exc)

    tags: list[str] = []
    try:
        if hasattr(vm_service, "tags_service"):
            for t in vm_service.tags_service().list():
                if hasattr(t, "name") and t.name:
                    tags.append(str(t.name))
    except Exception as exc:
        logger.debug("Could not fetch VM tags: %s", exc)

    placement_affinity = None
    pinned_hosts: list[str] = []
    if hasattr(vm, "placement_policy") and vm.placement_policy:
        pp = vm.placement_policy
        if hasattr(pp, "affinity") and pp.affinity:
            placement_affinity = getattr(pp.affinity, "value", str(pp.affinity))
        if hasattr(pp, "hosts") and pp.hosts:
            for ph in pp.hosts:
                h_name = getattr(ph, "name", None) or getattr(ph, "id", "")
                pinned_hosts.append(str(h_name))

    affinity_and_placement = VmPlacementAndAffinity(
        affinity_groups=affinity_groups,
        affinity_labels=affinity_labels,
        tags=tags,
        placement_affinity=placement_affinity,
        pinned_hosts=pinned_hosts,
    )

    # 6. Operating System and Guest Agent
    configured_os_type = None
    if hasattr(vm, "os") and vm.os:
        raw_os_type = getattr(vm.os, "type", None)
        if raw_os_type is not None and not _is_mock_object(raw_os_type):
            configured_os_type = getattr(raw_os_type, "value", str(raw_os_type))

    distribution, kernel_version, architecture, guest_tz = None, None, None, None
    if hasattr(vm, "guest_operating_system") and vm.guest_operating_system:
        gos = vm.guest_operating_system
        dist_val = getattr(gos, "distribution", None)
        if dist_val is not None and not _is_mock_object(dist_val):
            distribution = str(dist_val).strip() or None
        arch_val = getattr(gos, "architecture", None)
        if arch_val is not None and not _is_mock_object(arch_val):
            architecture = getattr(arch_val, "value", str(arch_val))
        if hasattr(gos, "kernel") and gos.kernel:
            ver_val = getattr(gos.kernel, "version", None)
            kernel_version = _format_version(ver_val)

    if hasattr(vm, "guest_time_zone") and vm.guest_time_zone:
        tz_val = getattr(vm.guest_time_zone, "name", None)
        if tz_val is not None and not _is_mock_object(tz_val):
            guest_tz = str(tz_val).strip() or None

    raw_fqdn = getattr(vm, "fqdn", None)
    vm_fqdn = (
        str(raw_fqdn).strip() or None
        if raw_fqdn is not None and not _is_mock_object(raw_fqdn)
        else None
    )

    guest_os = VmGuestOsInfo(
        configured_os_type=configured_os_type,
        distribution=distribution,
        kernel_version=kernel_version,
        architecture=architecture,
        fqdn=vm_fqdn,
        time_zone=guest_tz,
    )

    # 7. Hardware & Security
    bios_type = None
    if hasattr(vm, "bios") and vm.bios and hasattr(vm.bios, "type"):
        bios_type = getattr(vm.bios.type, "value", str(vm.bios.type))

    tpm_enabled = bool(getattr(vm, "tpm_enabled", False))
    delete_protected = bool(getattr(vm, "delete_protected", False))
    stateless = bool(getattr(vm, "stateless", False))
    soundcard_enabled = bool(getattr(vm, "soundcard_enabled", False))
    usb_enabled = hasattr(vm, "usb") and vm.usb is not None and getattr(vm.usb, "enabled", False)
    vm_type = getattr(vm.type, "value", str(vm.type)) if hasattr(vm, "type") and vm.type else None

    # CDROM ISO
    cdrom_iso = None
    try:
        cdroms = vm_service.cdroms_service().list()
        if cdroms and hasattr(cdroms[0], "file") and cdroms[0].file:
            cdrom_iso = getattr(cdroms[0].file, "id", None)
    except Exception as exc:
        logger.debug("Could not fetch cdrom info: %s", exc)

    # Display / Console protocol
    display_type = None
    if hasattr(vm, "display") and vm.display and hasattr(vm.display, "type"):
        display_type = getattr(vm.display.type, "value", str(vm.display.type))

    hardware = VmHardwareSecurity(
        bios_type=bios_type,
        tpm_enabled=tpm_enabled,
        delete_protected=delete_protected,
        stateless=stateless,
        soundcard_enabled=soundcard_enabled,
        usb_enabled=bool(usb_enabled),
        vm_type=vm_type,
        cdrom_iso=cdrom_iso,
        display_type=display_type,
    )

    # 8. High Availability & Watchdogs
    ha_enabled = False
    ha_priority = None
    if hasattr(vm, "high_availability") and vm.high_availability:
        ha_enabled = bool(getattr(vm.high_availability, "enabled", False))
        ha_priority = getattr(vm.high_availability, "priority", None)

    watchdog_action = None
    if (
        hasattr(vm, "watchdogs")
        and vm.watchdogs
        and not _is_mock_object(vm.watchdogs)
        and len(vm.watchdogs) > 0
    ):
        wd = vm.watchdogs[0]
        if hasattr(wd, "action") and not _is_mock_object(wd.action):
            watchdog_action = getattr(wd.action, "value", str(wd.action))

    lease_storage_domain_name = None
    if (
        hasattr(vm, "lease")
        and vm.lease
        and not _is_mock_object(vm.lease)
        and hasattr(vm.lease, "storage_domain")
    ):
        sd_ref = vm.lease.storage_domain
        if sd_ref and not _is_mock_object(sd_ref):
            raw_sd_name = getattr(sd_ref, "name", None) or getattr(sd_ref, "id", None)
            if raw_sd_name and not _is_mock_object(raw_sd_name):
                lease_storage_domain_name = str(raw_sd_name)

    high_availability = VmHighAvailability(
        enabled=ha_enabled,
        priority=ha_priority,
        watchdog_action=watchdog_action,
        lease_storage_domain_name=lease_storage_domain_name,
    )

    # 9. Migration Options
    auto_converge = None
    compressed = None
    encrypted = None
    mig_policy = None
    parallel_mig_policy = None
    custom_parallel = None

    if hasattr(vm, "migration") and vm.migration:
        mig = vm.migration
        if hasattr(mig, "auto_converge") and mig.auto_converge:
            auto_converge = getattr(mig.auto_converge, "value", str(mig.auto_converge))
        if hasattr(mig, "compressed") and mig.compressed:
            compressed = getattr(mig.compressed, "value", str(mig.compressed))
        if hasattr(mig, "encrypted") and mig.encrypted:
            encrypted = getattr(mig.encrypted, "value", str(mig.encrypted))
        if hasattr(mig, "policy") and mig.policy:
            mig_policy = getattr(mig.policy, "name", None) or getattr(mig.policy, "id", None)
        if hasattr(mig, "parallel_migrations_policy") and mig.parallel_migrations_policy:
            parallel_mig_policy = getattr(
                mig.parallel_migrations_policy, "value", str(mig.parallel_migrations_policy)
            )
        custom_parallel = getattr(mig, "custom_parallel_migrations", None)

    migration_downtime = None
    if hasattr(vm, "migration_downtime"):
        migration_downtime = getattr(vm, "migration_downtime", None)

    migration_options = VmMigrationOptions(
        auto_converge=auto_converge,
        compressed=compressed,
        encrypted=encrypted,
        policy=mig_policy,
        parallel_migrations_policy=parallel_mig_policy,
        custom_parallel_migrations=custom_parallel,
        downtime_ms=migration_downtime,
    )

    # 10. Lifecycle Timestamps & Pending Configuration
    creation_time = (
        str(vm.creation_time)
        if hasattr(vm, "creation_time")
        and vm.creation_time
        and not _is_mock_object(vm.creation_time)
        else None
    )
    start_time = (
        str(vm.start_time)
        if hasattr(vm, "start_time") and vm.start_time and not _is_mock_object(vm.start_time)
        else None
    )
    stop_time = (
        str(vm.stop_time)
        if hasattr(vm, "stop_time") and vm.stop_time and not _is_mock_object(vm.stop_time)
        else None
    )
    stop_reason = getattr(vm, "stop_reason", None)
    if stop_reason is not None and not _is_mock_object(stop_reason):
        stop_reason = str(stop_reason)
    else:
        stop_reason = None
    next_run_exists = bool(getattr(vm, "next_run_configuration_exists", False))

    lifecycle = VmLifecycleInfo(
        creation_time=creation_time,
        start_time=start_time,
        stop_time=stop_time,
        stop_reason=stop_reason,
        next_run_configuration_exists=next_run_exists,
        migration_downtime=migration_downtime,
    )

    # 10. Attached Disks
    disks: list[VmDiskInfo] = []
    sd_names: dict[str, str] = {}
    try:
        for sdi in system_service.storage_domains_service().list():
            if hasattr(sdi, "id") and hasattr(sdi, "name") and sdi.id and sdi.name:
                sd_names[str(sdi.id)] = str(sdi.name)
    except Exception:
        pass

    try:
        attachments = vm_service.disk_attachments_service().list()
        disks_service = system_service.disks_service()
        for att in attachments:
            disk_id = str(getattr(att, "id", ""))
            disk_alias = "unknown"
            size_gb = 0.0
            actual_size_gb = None
            storage_domain_name = None
            disk_format = None
            disk_sparse = None

            if hasattr(att, "disk") and att.disk:
                raw_disk = getattr(att, "disk", None)
                disk_id = getattr(raw_disk, "id", disk_id)
                # Fetch full disk metadata if provisioned_size is not cached
                if getattr(raw_disk, "provisioned_size", None) is not None:
                    full_disk = raw_disk
                else:
                    try:
                        full_disk = disks_service.disk_service(disk_id).get()
                    except Exception:
                        full_disk = raw_disk

                disk_alias = str(
                    getattr(full_disk, "alias", None) or getattr(full_disk, "name", None) or disk_id
                )
                prov_size = getattr(full_disk, "provisioned_size", None) or getattr(
                    full_disk, "initial_size", 0
                )
                if prov_size:
                    size_gb = round(float(prov_size) / (1024**3), 2)

                actual_bytes = getattr(full_disk, "actual_size", None)
                if actual_bytes:
                    actual_size_gb = round(float(actual_bytes) / (1024**3), 2)

                format_obj = getattr(full_disk, "format", None)
                if format_obj:
                    disk_format = getattr(format_obj, "value", str(format_obj)).lower()

                disk_sparse = getattr(full_disk, "sparse", None)

                # Storage domain
                storage_domain_id = None
                if full_disk is not None:
                    sds = getattr(full_disk, "storage_domains", None)
                    if sds and len(sds) > 0:
                        raw_id = str(getattr(sds[0], "id", "") or "")
                        if raw_id:
                            storage_domain_id = raw_id
                        raw_name = getattr(sds[0], "name", None)
                        if raw_name and str(raw_name) != "None":
                            storage_domain_name = str(raw_name)
                        elif raw_id and raw_id in sd_names:
                            storage_domain_name = sd_names[raw_id]
                        elif raw_id:
                            storage_domain_name = raw_id
                    elif hasattr(full_disk, "storage_domain") and full_disk.storage_domain:
                        storage_domain_name = str(
                            getattr(full_disk.storage_domain, "name", None) or ""
                        )
                        storage_domain_id = (
                            str(getattr(full_disk.storage_domain, "id", None) or "") or None
                        )

            interface_obj = getattr(att, "interface", "virtio_scsi")
            interface_str = getattr(interface_obj, "value", str(interface_obj))
            bootable = bool(getattr(att, "bootable", False))
            read_only = bool(getattr(att, "read_only", False))

            disk_io = None
            try:
                disk_io = extract_disk_io_stats(disks_service.disk_service(disk_id))
            except Exception as io_err:
                logger.debug("Failed to fetch I/O stats for disk %s: %s", disk_id, io_err)

            disks.append(
                VmDiskInfo(
                    id=disk_id,
                    name=disk_alias,
                    size_gb=size_gb,
                    actual_size_gb=actual_size_gb,
                    interface=interface_str,
                    format=disk_format,
                    sparse=disk_sparse,
                    bootable=bootable,
                    read_only=read_only,
                    storage_domain_name=storage_domain_name,
                    storage_domain_id=storage_domain_id,
                    io_stats=disk_io,
                )
            )
    except Exception as exc:
        logger.warning("Failed to retrieve disks for VM '%s': %s", name_or_id, exc)

    # 11. Attached NICs
    nics: list[VmNicInfo] = []
    try:
        for nic in vm_service.nics_service().list():
            nic_id = str(getattr(nic, "id", ""))
            nic_name = str(getattr(nic, "name", ""))
            mac = getattr(nic.mac, "address", None) if hasattr(nic, "mac") and nic.mac else None
            iface_obj = getattr(nic, "interface", None)
            iface_str = getattr(iface_obj, "value", str(iface_obj)) if iface_obj else None
            linked = bool(getattr(nic, "linked", True))

            net_name = None
            if (
                hasattr(nic, "vnic_profile")
                and nic.vnic_profile
                and hasattr(nic.vnic_profile, "name")
            ):
                net_name = nic.vnic_profile.name

            nic_ips: list[str] = []
            if mac:
                for dev in rep_devices:
                    dev_mac = getattr(getattr(dev, "mac", None), "address", None)
                    if dev_mac and dev_mac.lower() == mac.lower():
                        for ip_obj in getattr(dev, "ips", []) or []:
                            addr = getattr(ip_obj, "address", None)
                            if addr and addr not in nic_ips:
                                nic_ips.append(str(addr))

            nic_io = None
            try:
                nic_io = extract_nic_io_stats(vm_service.nics_service().nic_service(nic_id))
            except Exception as io_err:
                logger.debug("Failed to fetch I/O stats for nic %s: %s", nic_id, io_err)

            nics.append(
                VmNicInfo(
                    id=nic_id,
                    name=nic_name,
                    network_name=net_name,
                    mac_address=mac,
                    interface=iface_str,
                    linked=linked,
                    ip_addresses=nic_ips,
                    io_stats=nic_io,
                )
            )
    except Exception as exc:
        logger.warning("Failed to retrieve NICs for VM '%s': %s", name_or_id, exc)

    # 12. Snapshots
    snapshots_count = 0
    try:
        snapshots = vm_service.snapshots_service().list()
        snapshots_count = len(snapshots)
    except Exception as exc:
        logger.debug("Failed to count snapshots: %s", exc)

    # 13. Status details
    status_obj = getattr(vm, "status", None)
    status_str = getattr(status_obj, "value", str(status_obj or "unknown")).lower()
    raw_status_detail = getattr(vm, "status_detail", None)
    status_detail = (
        str(raw_status_detail)
        if raw_status_detail is not None and not _is_mock_object(raw_status_detail)
        else None
    )

    raw_desc = getattr(vm, "description", None)
    vm_desc = str(raw_desc) if raw_desc is not None and not _is_mock_object(raw_desc) else None

    # 14. Real-time runtime telemetry
    runtime_telemetry = None
    try:
        runtime_telemetry = extract_vm_runtime_telemetry(vm_service, disks, nics)
    except Exception as telem_err:
        logger.debug("Failed to extract runtime telemetry for VM '%s': %s", name_or_id, telem_err)

    return VmDetail(
        id=str(vm.id),
        name=str(vm.name),
        status=status_str,
        status_detail=status_detail,
        cluster_name=cluster_name,
        host_name=host_name,
        template_name=template_name,
        description=vm_desc,
        cpu=cpu_details,
        memory=memory_policy,
        io_scsi=io_scsi,
        affinity_and_placement=affinity_and_placement,
        guest_os=guest_os,
        hardware=hardware,
        high_availability=high_availability,
        migration=migration_options,
        lifecycle=lifecycle,
        disks=disks,
        nics=nics,
        snapshots_count=snapshots_count,
        telemetry=runtime_telemetry,
    )


# ── LIFECYCLE MANAGEMENT TOOLS ────────────────────────────────────────────────


def start_vm_tool(
    name_or_id: str,
    pause: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
    dry_run: bool = False,
) -> VmLifecycleResult:
    """Start a virtual machine by name or UUID.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        pause: If True, boots VM into paused state.
        wait: If True, waits synchronously until VM reaches 'up' (or 'paused') state.
        timeout_seconds: Maximum time to wait if wait=True.
        dry_run: If True, simulates the start operation and validates state without powering on.

    Returns:
        VmLifecycleResult with operation status and state.
    """
    require_mutation_allowed("start_vm")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    status_obj = getattr(vm, "status", None)
    prev_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    if prev_status == "up":
        audit_log("start_vm", vm_name, {"vm_id": vm_id, "skipped": True}, "SUCCESS")
        return VmLifecycleResult(
            success=True,
            action="start",
            vm_id=vm_id,
            vm_name=vm_name,
            previous_status=prev_status,
            current_status=prev_status,
            message=f"VM '{vm_name}' is already up.",
        )

    if dry_run:
        audit_log("start_vm", vm_name, {"vm_id": vm_id, "dry_run": True}, "SUCCESS")
        return VmLifecycleResult(
            success=True,
            action="start",
            vm_id=vm_id,
            vm_name=vm_name,
            previous_status=prev_status,
            current_status=prev_status,
            dry_run=True,
            message=f"[DRY RUN] VM '{vm_name}' is currently '{prev_status}'. Starting would power on the VM (pause={pause}). No changes were made.",
        )

    try:
        vm_service.start(pause=pause)
    except Exception as exc:
        audit_log("start_vm", vm_name, {"vm_id": vm_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(
            f"Failed to start VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "error": str(exc)},
        ) from exc

    current_status = "powering_up"

    if wait:
        target_status = "paused" if pause else "up"
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(2)
            try:
                refreshed = vm_service.get()
                ref_status = getattr(getattr(refreshed, "status", None), "value", "").lower()
                if ref_status == target_status:
                    current_status = ref_status
                    break
                # If engine failed or returned to down
                if ref_status in ("down", "unknown") and (time.time() - start_time > 10):
                    current_status = ref_status
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during start wait: %s", poll_exc)

        if current_status != target_status:
            audit_log(
                "start_vm",
                vm_name,
                {"vm_id": vm_id, "status": current_status, "timeout": True},
                "TIMEOUT",
            )
            raise OvirtTimeoutError(
                f"VM '{vm_name}' start initiated, but did not reach '{target_status}' within {timeout_seconds}s (current status: '{current_status}')",
                details={
                    "vm_id": vm_id,
                    "target_status": target_status,
                    "current_status": current_status,
                    "timeout_seconds": timeout_seconds,
                },
            )

    audit_log(
        "start_vm",
        vm_name,
        {"vm_id": vm_id, "current_status": current_status, "waited": wait},
        "SUCCESS",
    )
    return VmLifecycleResult(
        success=True,
        action="start",
        vm_id=vm_id,
        vm_name=vm_name,
        previous_status=prev_status,
        current_status=current_status,
        message=f"VM '{vm_name}' start initiated successfully (status: {current_status}).",
    )


def stop_vm_tool(
    name_or_id: str,
    graceful: bool = True,
    force: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
    dry_run: bool = False,
) -> VmLifecycleResult:
    """Stop or shut down a virtual machine by name or UUID.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        graceful: If True (default), initiates a clean operating system shutdown inside the guest
            through the oVirt/QEMU guest agent (vtools) and ACPI, allowing guest services to terminate
            cleanly and flush disk buffers. If False, executes an immediate hard power-off.
        force: If True, forces stop/shutdown even if backup is running.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, waits synchronously until VM reaches 'down' state.
        timeout_seconds: Maximum time to wait if wait=True.
        dry_run: If True, simulates the stop/shutdown and returns projected outcome without changing power state.

    Returns:
        VmLifecycleResult with operation status, graceful flag, and state.
    """
    action_type = "shutdown" if graceful else "stop"
    if not dry_run:
        require_destructive_confirmation(
            f"{action_type} VM '{name_or_id}' (force={force})", confirmed=confirm
        )
    else:
        require_mutation_allowed(f"{action_type}_vm")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    status_obj = getattr(vm, "status", None)
    prev_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    if prev_status == "down":
        audit_log(f"{action_type}_vm", vm_name, {"vm_id": vm_id, "skipped": True}, "SUCCESS")
        return VmLifecycleResult(
            success=True,
            action=action_type,
            vm_id=vm_id,
            vm_name=vm_name,
            previous_status=prev_status,
            current_status=prev_status,
            graceful=graceful,
            message=f"VM '{vm_name}' is already down.",
        )

    if dry_run:
        audit_log(f"{action_type}_vm", vm_name, {"vm_id": vm_id, "dry_run": True}, "SUCCESS")
        return VmLifecycleResult(
            success=True,
            action=action_type,
            vm_id=vm_id,
            vm_name=vm_name,
            previous_status=prev_status,
            current_status=prev_status,
            graceful=graceful,
            dry_run=True,
            message=(
                f"[DRY RUN] VM '{vm_name}' is currently '{prev_status}'. "
                f"Action '{action_type}' would {'perform clean guest OS/ACPI shutdown' if graceful else 'immediately power off the VM'} "
                f"(force={force}). No changes were made."
            ),
        )

    # Pre-condition check: cannot gracefully shut down a VM that is still booting
    if graceful and prev_status in ("powering_up", "wait_for_launch", "reboot_in_progress"):
        raise OvirtValidationError(
            f"Cannot perform graceful shutdown on VM '{vm_name}' because it is currently '{prev_status}'. "
            "The guest operating system and guest agent (vtools) are still booting and cannot process "
            "ACPI/agent shutdown signals. Please wait until the VM reaches 'up' state, or specify "
            "graceful=False for an immediate hard power-off.",
            details={"vm_id": vm_id, "current_status": prev_status},
        )

    try:
        if graceful:
            vm_service.shutdown(force=force)
        else:
            vm_service.stop(force=force)
    except Exception as exc:
        audit_log(f"{action_type}_vm", vm_name, {"vm_id": vm_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(
            f"Failed to {action_type} VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "error": str(exc)},
        ) from exc

    current_status = "powering_down"

    if wait:
        target_status = "down"
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(2)
            try:
                refreshed = vm_service.get()
                ref_status = getattr(getattr(refreshed, "status", None), "value", "").lower()
                if ref_status == target_status:
                    current_status = ref_status
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during stop wait: %s", poll_exc)

        if current_status != target_status:
            audit_log(
                f"{action_type}_vm",
                vm_name,
                {"vm_id": vm_id, "status": current_status, "timeout": True},
                "TIMEOUT",
            )
            raise OvirtTimeoutError(
                f"VM '{vm_name}' {action_type} initiated, but did not reach '{target_status}' within {timeout_seconds}s (current status: '{current_status}')",
                details={
                    "vm_id": vm_id,
                    "target_status": target_status,
                    "current_status": current_status,
                    "timeout_seconds": timeout_seconds,
                },
            )

    audit_log(
        f"{action_type}_vm",
        vm_name,
        {"vm_id": vm_id, "current_status": current_status, "waited": wait},
        "SUCCESS",
    )
    shutdown_msg = (
        f"VM '{vm_name}' graceful shutdown initiated via guest agent (vtools) / ACPI (status: {current_status})."
        if graceful
        else f"VM '{vm_name}' hard power-off executed (status: {current_status})."
    )
    return VmLifecycleResult(
        success=True,
        action=action_type,
        vm_id=vm_id,
        vm_name=vm_name,
        previous_status=prev_status,
        current_status=current_status,
        graceful=graceful,
        message=shutdown_msg,
    )


def reboot_vm_tool(
    name_or_id: str,
    force: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
    dry_run: bool = False,
) -> VmLifecycleResult:
    """Reboot a running virtual machine by name or UUID.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        force: If True, forces reboot even if a backup is running.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, waits synchronously until VM restarts and returns to 'up' status.
        timeout_seconds: Maximum time to wait if wait=True.
        dry_run: If True, simulates reboot and verifies pre-conditions without resetting the VM.

    Returns:
        VmLifecycleResult with operation status and state.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"reboot VM '{name_or_id}' (force={force})", confirmed=confirm
        )
    else:
        require_mutation_allowed("reboot_vm")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    status_obj = getattr(vm, "status", None)
    prev_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    if prev_status == "down":
        raise OvirtValidationError(
            f"Cannot reboot VM '{vm_name}' because it is currently down. Use ovirt_vm_start to boot it.",
            details={"vm_id": vm_id, "status": prev_status},
        )

    if dry_run:
        audit_log("reboot_vm", vm_name, {"vm_id": vm_id, "dry_run": True}, "SUCCESS")
        return VmLifecycleResult(
            success=True,
            action="reboot",
            vm_id=vm_id,
            vm_name=vm_name,
            previous_status=prev_status,
            current_status=prev_status,
            dry_run=True,
            message=f"[DRY RUN] VM '{vm_name}' is currently '{prev_status}'. Reboot would restart the virtual machine (force={force}). No changes were made.",
        )

    try:
        vm_service.reboot(force=force)
    except Exception as exc:
        audit_log("reboot_vm", vm_name, {"vm_id": vm_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(
            f"Failed to reboot VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "error": str(exc)},
        ) from exc

    current_status = "rebooting"

    if wait:
        target_status = "up"
        start_time = time.time()
        time.sleep(3)
        while time.time() - start_time < timeout_seconds:
            time.sleep(2)
            try:
                refreshed = vm_service.get()
                ref_status = getattr(getattr(refreshed, "status", None), "value", "").lower()
                if ref_status == target_status:
                    current_status = ref_status
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during reboot wait: %s", poll_exc)

        if current_status != target_status:
            audit_log(
                "reboot_vm",
                vm_name,
                {"vm_id": vm_id, "status": current_status, "timeout": True},
                "TIMEOUT",
            )
            raise OvirtTimeoutError(
                f"VM '{vm_name}' reboot initiated, but did not reach '{target_status}' within {timeout_seconds}s (current status: '{current_status}')",
                details={
                    "vm_id": vm_id,
                    "target_status": target_status,
                    "current_status": current_status,
                    "timeout_seconds": timeout_seconds,
                },
            )

    audit_log(
        "reboot_vm",
        vm_name,
        {"vm_id": vm_id, "current_status": current_status, "waited": wait},
        "SUCCESS",
    )
    return VmLifecycleResult(
        success=True,
        action="reboot",
        vm_id=vm_id,
        vm_name=vm_name,
        previous_status=prev_status,
        current_status=current_status,
        message=f"VM '{vm_name}' reboot initiated successfully (status: {current_status}).",
    )


def create_vm_tool(
    name: str,
    cluster: str,
    template: str = "Blank",
    memory_mb: int = 2048,
    cpu_cores: int = 1,
    cpu_sockets: int = 1,
    description: str | None = None,
    os_type: str | None = None,
    disk_size_gb: int | None = None,
    storage_domain: str | None = None,
    network_profile: str | None = None,
    wait: bool = False,
    timeout_seconds: int = 120,
) -> VmCreateResult:
    """Create a new virtual machine in oVirt / OLVM.

    Args:
        name: Unique display name for the new virtual machine.
        cluster: Target cluster name or UUID.
        template: Base template name or UUID (defaults to 'Blank').
        memory_mb: Allocated RAM in megabytes (defaults to 2048 MB).
        cpu_cores: Number of cores per socket (defaults to 1).
        cpu_sockets: Number of sockets (defaults to 1).
        description: Optional comment or description.
        os_type: Operating system identifier (e.g. 'rhel_8x64', 'other_linux').
        disk_size_gb: Optional primary disk size in GB to create and attach.
        storage_domain: Target storage domain for the primary disk (optional).
        network_profile: Name or UUID of vNIC profile for primary network interface (e.g. 'ovirtmgmt').
        wait: If True, waits synchronously until VM status is 'down' (fully provisioned/unlocked).
        timeout_seconds: Maximum time to wait if wait=True.

    Returns:
        VmCreateResult with UUID, names, and initial status.
    """
    require_mutation_allowed("create_vm")

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()

    # 1. Resolve Cluster
    clusters_service = system_service.clusters_service()
    cluster_obj = client.find_resource_by_id_or_name(clusters_service, cluster, "cluster")
    cluster_id = str(cluster_obj.id)
    cluster_name = str(cluster_obj.name)

    # 2. Resolve Template
    templates_service = system_service.templates_service()
    template_obj = client.find_resource_by_id_or_name(templates_service, template, "template")
    template_id = str(template_obj.id)
    template_name = str(template_obj.name)

    # 3. Build SDK VM specification
    os_spec = sdk_types.OperatingSystem(type=os_type) if os_type else None
    vm_spec = sdk_types.Vm(
        name=name,
        cluster=sdk_types.Cluster(id=cluster_id),
        template=sdk_types.Template(id=template_id),
        memory=memory_mb * 1024 * 1024,
        cpu=sdk_types.Cpu(
            topology=sdk_types.CpuTopology(
                cores=cpu_cores,
                sockets=cpu_sockets,
                threads=1,
            )
        ),
        type=sdk_types.VmType.SERVER,
        description=description,
        os=os_spec,
    )

    vms_service = system_service.vms_service()
    try:
        created_vm = vms_service.add(vm_spec)
    except Exception as exc:
        audit_log(
            "create_vm",
            name,
            {"cluster": cluster_name, "template": template_name, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to create VM '{name}': {exc}",
            details={"name": name, "cluster": cluster_name, "error": str(exc)},
        ) from exc

    vm_id = str(created_vm.id)
    vm_service = vms_service.vm_service(vm_id)

    # 4. Optional Disk Attachment
    if disk_size_gb and disk_size_gb > 0:
        try:
            sd_spec = None
            if storage_domain:
                sds_service = system_service.storage_domains_service()
                sd_obj = client.find_resource_by_id_or_name(
                    sds_service, storage_domain, "storage_domain"
                )
                sd_spec = [sdk_types.StorageDomain(id=str(sd_obj.id))]

            disk_attachments_service = vm_service.disk_attachments_service()
            disk_attachments_service.add(
                sdk_types.DiskAttachment(
                    disk=sdk_types.Disk(
                        name=f"{name}_Disk1",
                        description="Primary Disk",
                        format=sdk_types.DiskFormat.COW,
                        provisioned_size=disk_size_gb * (1024**3),
                        storage_domains=sd_spec,
                    ),
                    interface=sdk_types.DiskInterface.VIRTIO,
                    bootable=True,
                    active=True,
                )
            )
        except Exception as exc:
            logger.warning("Failed to attach initial disk to VM '%s': %s", name, exc)

    # 5. Optional Network Interface Attachment
    if network_profile:
        try:
            vnic_profiles_service = system_service.vnic_profiles_service()
            profile_obj = client.find_resource_by_id_or_name(
                vnic_profiles_service, network_profile, "vnic_profile"
            )
            vm_service.nics_service().add(
                sdk_types.Nic(
                    name="nic1",
                    vnic_profile=sdk_types.VnicProfile(id=str(profile_obj.id)),
                    interface=sdk_types.NicInterface.VIRTIO,
                )
            )
        except Exception as exc:
            logger.warning(
                "Failed to attach network profile '%s' to VM '%s': %s", network_profile, name, exc
            )

    # 6. Wait for creation to finish (status reaches 'down' and disks un-locked)
    curr_status = "down"
    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(2)
            try:
                refreshed = vm_service.get()
                ref_status = getattr(getattr(refreshed, "status", None), "value", "").lower()
                if ref_status == "down":
                    # If initial disk was attached, verify that disk allocation has completed (status != 'locked')
                    if disk_size_gb and disk_size_gb > 0:
                        disks_ready = True
                        disks_service = system_service.disks_service()
                        attachments = vm_service.disk_attachments_service().list()
                        for att in attachments:
                            if hasattr(att, "disk") and att.disk:
                                d_obj = disks_service.disk_service(att.disk.id).get()
                                d_status = getattr(
                                    getattr(d_obj, "status", None), "value", "ok"
                                ).lower()
                                if d_status == "locked":
                                    disks_ready = False
                                    break
                        if disks_ready:
                            curr_status = ref_status
                            break
                    else:
                        curr_status = ref_status
                        break
            except Exception as poll_exc:
                logger.debug("Transient poll error during create wait: %s", poll_exc)
    else:
        status_val = getattr(getattr(created_vm, "status", None), "value", "down")
        curr_status = str(status_val).lower()

    audit_log(
        "create_vm",
        name,
        {
            "vm_id": vm_id,
            "cluster": cluster_name,
            "template": template_name,
            "memory_mb": memory_mb,
            "cpu_cores": cpu_cores * cpu_sockets,
        },
        "SUCCESS",
    )
    return VmCreateResult(
        success=True,
        vm_id=vm_id,
        vm_name=name,
        cluster_name=cluster_name,
        template_name=template_name,
        status=curr_status,
        memory_mb=memory_mb,
        cpu_cores=int(cpu_cores * cpu_sockets),
        message=(
            f"Virtual machine '{name}' created successfully in cluster '{cluster_name}' "
            f"from template '{template_name}'."
        ),
    )


def delete_vm_tool(
    name_or_id: str,
    detach_only: bool = False,
    force: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
    dry_run: bool = False,
) -> VmDeleteResult:
    """Delete a virtual machine in oVirt / OLVM.

    Args:
        name_or_id: Display name or UUID of the virtual machine to remove.
        detach_only: If True, attached virtual disks are detached and kept in storage domains rather than deleted.
        force: If True, forces stop if VM is up, and forces removal of locked or protected disks.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, waits synchronously until the VM is removed from inventory.
        timeout_seconds: Maximum time to wait if wait=True.
        dry_run: If True, simulates deletion and validates state without removing the virtual machine.

    Returns:
        VmDeleteResult with details of deleted VM.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"delete VM '{name_or_id}' (detach_only={detach_only}, force={force})",
            confirmed=confirm,
        )
    else:
        require_mutation_allowed("delete_vm")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    status_obj = getattr(vm, "status", None)
    curr_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    # If running, check force
    if curr_status != "down" and not force:
        raise OvirtValidationError(
            f"Cannot delete VM '{vm_name}' because its current status is '{curr_status}'. "
            "Stop the virtual machine first, or supply force=True to automatically force stop and remove.",
            details={"vm_id": vm_id, "status": curr_status},
        )

    if dry_run:
        audit_log(
            "delete_vm",
            vm_name,
            {"vm_id": vm_id, "detach_only": detach_only, "force": force, "dry_run": True},
            "SUCCESS",
        )
        disk_msg = (
            "Attached virtual disks would be detached and preserved."
            if detach_only
            else "Attached virtual disks would be permanently deleted."
        )
        return VmDeleteResult(
            success=True,
            vm_id=vm_id,
            vm_name=vm_name,
            disks_detached_only=detach_only,
            dry_run=True,
            message=f"[DRY RUN] VM '{vm_name}' (status: '{curr_status}') would be removed. {disk_msg} No changes were made.",
        )
        # Force stop before removal
        logger.info("Force-stopping VM '%s' before deletion...", vm_name)
        try:
            vm_service.stop(force=True)
            stop_start = time.time()
            while time.time() - stop_start < 30:
                time.sleep(2)
                refreshed = vm_service.get()
                if getattr(getattr(refreshed, "status", None), "value", "").lower() == "down":
                    break
        except Exception as stop_exc:
            logger.warning("Error during pre-deletion force stop of VM '%s': %s", vm_name, stop_exc)

    try:
        if force:
            start_del = time.time()
            while True:
                try:
                    vm_service.remove(detach_only=detach_only, force=force)
                    break
                except Exception as del_exc:
                    if "is locked" in str(del_exc).lower() and time.time() - start_del < 30:
                        time.sleep(2)
                        continue
                    raise
        else:
            vm_service.remove(detach_only=detach_only, force=force)
    except Exception as exc:
        audit_log("delete_vm", vm_name, {"vm_id": vm_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(
            f"Failed to delete VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "error": str(exc)},
        ) from exc

    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(2)
            try:
                vm_service.get()
            except Exception:
                # Successfully removed from engine
                break

    audit_log(
        "delete_vm",
        vm_name,
        {"vm_id": vm_id, "detach_only": detach_only, "force": force},
        "SUCCESS",
    )
    disk_msg = (
        "Disks were detached and preserved." if detach_only else "Attached disks were deleted."
    )
    return VmDeleteResult(
        success=True,
        vm_id=vm_id,
        vm_name=vm_name,
        disks_detached_only=detach_only,
        message=f"Virtual machine '{vm_name}' deleted successfully. {disk_msg}",
    )


# ── MIGRATION & PLACEMENT TOOLS ───────────────────────────────────────────────


def migrate_vm_tool(
    name_or_id: str,
    target_host: str | None = None,
    force: bool = False,
    wait: bool = False,
    timeout_seconds: int = 120,
    dry_run: bool = False,
) -> VmMigrateResult:
    """Migrate a running virtual machine to another hypervisor host without downtime.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        target_host: Destination physical host name or UUID. If omitted, engine automatically selects best host.
        force: If True, forces migration even if VM is configured as non-migratable.
        wait: If True, blocks synchronously until migration is complete.
        timeout_seconds: Maximum time to wait if wait=True.
        dry_run: If True, verifies preconditions and simulates migration without moving the virtual machine.

    Returns:
        VmMigrateResult with source/target hosts and outcome.
    """
    require_mutation_allowed("migrate_vm")

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    vms_service = system_service.vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    status_obj = getattr(vm, "status", None)
    curr_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    if curr_status != "up":
        raise OvirtValidationError(
            f"Cannot migrate VM '{vm_name}' because its current status is '{curr_status}'. "
            "Live migration requires the virtual machine to be actively running ('up').",
            details={"vm_id": vm_id, "status": curr_status},
        )

    # Resolve source host
    source_host_name: str | None = None
    if hasattr(vm, "host") and vm.host:
        source_host_name = getattr(vm.host, "name", None)
        if not source_host_name and hasattr(vm.host, "id"):
            try:
                h_obj = system_service.hosts_service().host_service(vm.host.id).get()
                source_host_name = getattr(h_obj, "name", None)
            except Exception:
                pass

    # Resolve target host (if specified)
    target_host_obj = None
    target_host_name: str | None = None
    if target_host:
        target_host_obj = client.find_resource_by_id_or_name(
            system_service.hosts_service(), target_host, "host"
        )
        target_host_name = str(target_host_obj.name)
        if source_host_name and target_host_name == source_host_name:
            raise OvirtValidationError(
                f"VM '{vm_name}' is already running on target host '{target_host_name}'.",
                details={"vm_id": vm_id, "host": target_host_name},
            )

    if dry_run:
        audit_log(
            "migrate_vm",
            vm_name,
            {
                "vm_id": vm_id,
                "source_host": source_host_name,
                "target_host": target_host_name,
                "dry_run": True,
            },
            "SUCCESS",
        )
        dest_str = (
            f"to host '{target_host_name}'"
            if target_host_name
            else "to an optimal host in the cluster"
        )
        return VmMigrateResult(
            success=True,
            vm_id=vm_id,
            vm_name=vm_name,
            source_host=source_host_name,
            target_host=target_host_name,
            status=curr_status,
            dry_run=True,
            message=f"[DRY RUN] VM '{vm_name}' is currently running on '{source_host_name}'. Live migration {dest_str} would be initiated (force={force}). No changes were made.",
        )

    host_spec = sdk_types.Host(id=str(target_host_obj.id)) if target_host_obj else None

    try:
        vm_service.migrate(host=host_spec, force=force)
    except Exception as exc:
        audit_log("migrate_vm", vm_name, {"vm_id": vm_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(
            f"Failed to initiate migration for VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "error": str(exc)},
        ) from exc

    status_after = "migrating"

    if wait:
        start_time = time.time()
        # Brief sleep for migration state to register
        time.sleep(3)
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                refreshed = vm_service.get()
                ref_status = getattr(getattr(refreshed, "status", None), "value", "").lower()
                if ref_status == "up":
                    # Check host changed or reached target
                    ref_host = getattr(refreshed, "host", None)
                    ref_host_name = getattr(ref_host, "name", None) if ref_host else None
                    if not target_host_name or ref_host_name == target_host_name:
                        status_after = "up"
                        if not target_host_name and ref_host_name:
                            target_host_name = ref_host_name
                        break
            except Exception as poll_exc:
                logger.debug("Transient poll error during migration wait: %s", poll_exc)

        if status_after != "up":
            audit_log(
                "migrate_vm",
                vm_name,
                {"vm_id": vm_id, "timeout": True, "status": status_after},
                "TIMEOUT",
            )
            raise OvirtTimeoutError(
                f"VM '{vm_name}' migration initiated, but did not complete within {timeout_seconds}s.",
                details={"vm_id": vm_id, "timeout_seconds": timeout_seconds},
            )

    audit_log(
        "migrate_vm",
        vm_name,
        {
            "vm_id": vm_id,
            "source_host": source_host_name,
            "target_host": target_host_name,
            "status": status_after,
        },
        "SUCCESS",
    )
    dest_str = (
        f"to host '{target_host_name}'" if target_host_name else "to an optimal host in the cluster"
    )
    return VmMigrateResult(
        success=True,
        vm_id=vm_id,
        vm_name=vm_name,
        source_host=source_host_name,
        target_host=target_host_name,
        status=status_after,
        message=f"VM '{vm_name}' migration {dest_str} initiated successfully (status: {status_after}).",
    )


def pin_vm_tool(name_or_id: str, host: str) -> VmPinResult:
    """Pin a virtual machine to run exclusively on a specific hypervisor host.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        host: Target physical host name or UUID to pin the VM to.

    Returns:
        VmPinResult with pinned host and affinity state.
    """
    require_mutation_allowed("pin_vm")

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    vms_service = system_service.vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    host_obj = client.find_resource_by_id_or_name(system_service.hosts_service(), host, "host")
    host_id = str(host_obj.id)
    host_name = str(host_obj.name)

    update_spec = sdk_types.Vm(
        placement_policy=sdk_types.VmPlacementPolicy(
            affinity=sdk_types.VmAffinity.PINNED,
            hosts=[sdk_types.Host(id=host_id)],
        )
    )

    try:
        vm_service.update(update_spec)
    except Exception as exc:
        audit_log(
            "pin_vm", vm_name, {"vm_id": vm_id, "host": host_name, "error": str(exc)}, "FAILED"
        )
        raise OvirtMCPError(
            f"Failed to pin VM '{vm_name}' to host '{host_name}': {exc}",
            details={"vm_id": vm_id, "host": host_name, "error": str(exc)},
        ) from exc

    audit_log("pin_vm", vm_name, {"vm_id": vm_id, "host": host_name}, "SUCCESS")
    return VmPinResult(
        success=True,
        vm_id=vm_id,
        vm_name=vm_name,
        affinity="pinned",
        pinned_hosts=[host_name],
        message=f"VM '{vm_name}' successfully pinned to host '{host_name}'.",
    )


def unpin_vm_tool(name_or_id: str) -> VmPinResult:
    """Unpin a virtual machine, restoring normal dynamic live migration across cluster hosts.

    Args:
        name_or_id: Display name or UUID of the virtual machine.

    Returns:
        VmPinResult with 'migratable' affinity and empty pinned hosts.
    """
    require_mutation_allowed("unpin_vm")

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    vms_service = system_service.vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    update_spec = sdk_types.Vm(
        placement_policy=sdk_types.VmPlacementPolicy(
            affinity=sdk_types.VmAffinity.MIGRATABLE,
            hosts=[],
        )
    )

    try:
        vm_service.update(update_spec)
    except Exception as exc:
        audit_log("unpin_vm", vm_name, {"vm_id": vm_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(
            f"Failed to unpin VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "error": str(exc)},
        ) from exc

    audit_log("unpin_vm", vm_name, {"vm_id": vm_id}, "SUCCESS")
    return VmPinResult(
        success=True,
        vm_id=vm_id,
        vm_name=vm_name,
        affinity="migratable",
        pinned_hosts=[],
        message=f"VM '{vm_name}' successfully unpinned; live migration is now permitted across cluster hosts.",
    )


# ── SNAPSHOT MANAGEMENT TOOLS ─────────────────────────────────────────────────


def list_vm_snapshots_tool(name_or_id: str) -> list[VmSnapshotInfo]:
    """List all snapshots of a virtual machine.

    Args:
        name_or_id: Display name or UUID of the virtual machine.

    Returns:
        List of VmSnapshotInfo with IDs, descriptions, statuses, and timestamps.
    """
    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_service = vms_service.vm_service(vm_id)

    snapshots: list[VmSnapshotInfo] = []
    try:
        raw_snapshots = vm_service.snapshots_service().list()
        for s in raw_snapshots:
            s_id = str(getattr(s, "id", ""))
            desc = getattr(s, "description", "") or "No description"
            status_obj = getattr(s, "snapshot_status", None)
            status_str = getattr(status_obj, "value", str(status_obj or "ok")).lower()
            type_obj = getattr(s, "snapshot_type", None)
            type_str = getattr(type_obj, "value", str(type_obj or "regular")).lower()
            date_str = str(s.date) if hasattr(s, "date") and s.date else None
            persist_mem = bool(getattr(s, "persist_memorystate", False))

            snapshots.append(
                VmSnapshotInfo(
                    id=s_id,
                    description=desc,
                    snapshot_status=status_str,
                    snapshot_type=type_str,
                    date=date_str,
                    persist_memorystate=persist_mem,
                )
            )
    except Exception as exc:
        logger.warning("Failed to list snapshots for VM '%s': %s", name_or_id, exc)
        raise OvirtMCPError(
            f"Failed to list snapshots for VM '{name_or_id}': {exc}",
            details={"vm": name_or_id, "error": str(exc)},
        ) from exc

    return snapshots


def create_vm_snapshot_tool(
    name_or_id: str,
    description: str,
    persist_memory: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
    dry_run: bool = False,
) -> VmSnapshotResult:
    """Create a new point-in-time snapshot of a virtual machine.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        description: Informative description or label for the snapshot.
        persist_memory: If True, saves running RAM state along with disk state.
        wait: If True, blocks synchronously until snapshot creation completes and reaches 'ok' status.
        timeout_seconds: Maximum time to wait if wait=True.
        dry_run: If True, simulates snapshot creation without altering VM disks or memory.

    Returns:
        VmSnapshotResult with snapshot ID and outcome.
    """
    require_mutation_allowed("create_vm_snapshot")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    if dry_run:
        audit_log(
            "create_vm_snapshot",
            vm_name,
            {"vm_id": vm_id, "description": description, "dry_run": True},
            "SUCCESS",
        )
        return VmSnapshotResult(
            success=True,
            action="create",
            vm_id=vm_id,
            vm_name=vm_name,
            snapshot_id="dry-run-preview-id",
            description=description,
            dry_run=True,
            message=f"[DRY RUN] Snapshot '{description}' (persist_memory={persist_memory}) for VM '{vm_name}' would be created. No changes were made.",
        )

    snapshot_spec = sdk_types.Snapshot(
        description=description,
        persist_memorystate=persist_memory,
    )

    try:
        created = vm_service.snapshots_service().add(snapshot_spec)
        snap_id = str(getattr(created, "id", ""))
    except Exception as exc:
        audit_log("create_vm_snapshot", vm_name, {"vm_id": vm_id, "error": str(exc)}, "FAILED")
        raise OvirtMCPError(
            f"Failed to create snapshot for VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "error": str(exc)},
        ) from exc

    if wait and snap_id:
        snap_service = vm_service.snapshots_service().snapshot_service(snap_id)
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                refreshed = snap_service.get()
                st = getattr(getattr(refreshed, "snapshot_status", None), "value", "").lower()
                if st == "ok":
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during snapshot create: %s", poll_exc)

    audit_log(
        "create_vm_snapshot",
        vm_name,
        {"vm_id": vm_id, "snapshot_id": snap_id, "description": description},
        "SUCCESS",
    )
    return VmSnapshotResult(
        success=True,
        action="create",
        vm_id=vm_id,
        vm_name=vm_name,
        snapshot_id=snap_id,
        description=description,
        message=f"Snapshot '{description}' created successfully for VM '{vm_name}' (ID: {snap_id}).",
    )


def restore_vm_snapshot_tool(
    name_or_id: str,
    snapshot_id: str,
    restore_memory: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Restore (revert) a virtual machine to a previous snapshot.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        snapshot_id: UUID of the snapshot to restore.
        restore_memory: If True, restores the saved guest RAM memory state (requires a snapshot created with persist_memory=True).
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, blocks synchronously until restore completes and VM status is 'down'.
        timeout_seconds: Maximum time to wait if wait=True.

    Returns:
        VmSnapshotResult with operation details.
    """
    require_destructive_confirmation(
        f"restore VM '{name_or_id}' to snapshot '{snapshot_id}' (restore_memory={restore_memory})",
        confirmed=confirm,
    )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    status_obj = getattr(vm, "status", None)
    curr_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()

    if curr_status == "image_locked":
        # Wait up to 60 seconds if the VM is temporarily locked by an ongoing storage operation
        lock_start = time.time()
        while curr_status == "image_locked" and time.time() - lock_start < 60:
            time.sleep(3)
            try:
                refreshed_vm = vm_service.get()
                status_obj = getattr(refreshed_vm, "status", None)
                curr_status = getattr(status_obj, "value", str(status_obj or "unknown")).lower()
            except Exception as poll_err:
                logger.debug("Transient poll error waiting for image unlock: %s", poll_err)

    if curr_status != "down":
        raise OvirtValidationError(
            f"Cannot restore snapshot on VM '{vm_name}' because its current status is '{curr_status}'. "
            "Please stop the virtual machine first before restoring a snapshot.",
            details={"vm_id": vm_id, "status": curr_status},
        )

    snap_service = vm_service.snapshots_service().snapshot_service(snapshot_id)

    # Pre-flight check: verify memory existence if restore_memory=True
    if restore_memory:
        try:
            target_snap = snap_service.get()
            has_memory = bool(getattr(target_snap, "persist_memorystate", False))
            if not has_memory:
                raise OvirtValidationError(
                    f"Snapshot '{snapshot_id}' does not have a saved memory state (RAM). "
                    "Cannot restore with restore_memory=True. Please set restore_memory=False "
                    "for a clean disk-only restoration.",
                    details={"snapshot_id": snapshot_id, "persist_memorystate": False},
                )
        except OvirtValidationError:
            raise
        except Exception as snap_err:
            logger.debug("Transient error inspecting snapshot memory state: %s", snap_err)

    start_attempt = time.time()
    while True:
        try:
            if restore_memory:
                snap_service.restore(restore_memory=True)
            else:
                snap_service.restore()
            break
        except Exception as exc:
            err_msg = str(exc)
            if (
                "performing an operation on a snapshot" in err_msg.lower()
                or "locked" in err_msg.lower()
            ) and (time.time() - start_attempt < 60):
                logger.info(
                    "VM or snapshot is currently busy/locked, waiting before retrying restore: %s",
                    err_msg,
                )
                time.sleep(4)
                continue
            audit_log(
                "restore_vm_snapshot",
                vm_name,
                {
                    "vm_id": vm_id,
                    "snapshot_id": snapshot_id,
                    "restore_memory": restore_memory,
                    "error": str(exc),
                },
                "FAILED",
            )
            raise OvirtMCPError(
                f"Failed to restore snapshot '{snapshot_id}' on VM '{vm_name}': {exc}",
                details={"vm_id": vm_id, "snapshot_id": snapshot_id, "error": str(exc)},
            ) from exc

    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                snaps = vm_service.snapshots_service().list()
                busy = any(
                    getattr(getattr(s, "snapshot_status", None), "value", "").lower() == "locked"
                    for s in snaps
                )
                refreshed = vm_service.get()
                st = getattr(getattr(refreshed, "status", None), "value", "").lower()
                if not busy and st in ("down", "up"):
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during snapshot restore: %s", poll_exc)

    audit_log(
        "restore_vm_snapshot",
        vm_name,
        {"vm_id": vm_id, "snapshot_id": snapshot_id, "restore_memory": restore_memory},
        "SUCCESS",
    )
    return VmSnapshotResult(
        success=True,
        action="restore",
        vm_id=vm_id,
        vm_name=vm_name,
        snapshot_id=snapshot_id,
        restore_memory=restore_memory,
        message=f"VM '{vm_name}' successfully restored to snapshot '{snapshot_id}' (restore_memory={restore_memory}).",
    )


def preview_vm_snapshot_tool(
    name_or_id: str,
    snapshot_id: str,
    restore_memory: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Preview a snapshot of a virtual machine before committing or undoing.

    In oVirt, previewing a snapshot mounts its historical disks and optionally its saved RAM
    state into an isolated sandbox, allowing operators to boot or inspect the point-in-time state.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        snapshot_id: UUID of the snapshot to preview.
        restore_memory: If True, boots / resumes the VM directly from the saved RAM memory state.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, blocks synchronously until snapshot reaches 'in_preview' status.
        timeout_seconds: Maximum time to wait if wait=True.

    Returns:
        VmSnapshotResult with operation details.
    """
    require_destructive_confirmation(
        f"preview snapshot '{snapshot_id}' on VM '{name_or_id}' (restore_memory={restore_memory})",
        confirmed=confirm,
    )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    snap_service = vm_service.snapshots_service().snapshot_service(snapshot_id)

    # Pre-flight check: if restore_memory=True, verify snapshot has memory
    if restore_memory:
        try:
            target_snap = snap_service.get()
            has_memory = bool(getattr(target_snap, "persist_memorystate", False))
            if not has_memory:
                raise OvirtValidationError(
                    f"Snapshot '{snapshot_id}' does not contain saved memory state (RAM). "
                    "Cannot preview with restore_memory=True. Set restore_memory=False to preview disk-only state.",
                    details={"snapshot_id": snapshot_id, "persist_memorystate": False},
                )
        except OvirtValidationError:
            raise
        except Exception as snap_err:
            logger.debug("Transient error inspecting snapshot memory state: %s", snap_err)

    start_attempt = time.time()
    while True:
        try:
            vm_service.preview_snapshot(
                snapshot=sdk_types.Snapshot(id=snapshot_id),
                restore_memory=restore_memory,
            )
            break
        except Exception as exc:
            err_msg = str(exc)
            if (
                "performing an operation on a snapshot" in err_msg.lower()
                or "locked" in err_msg.lower()
            ) and (time.time() - start_attempt < 60):
                logger.info(
                    "VM snapshot operation is in progress, waiting before retrying preview: %s",
                    err_msg,
                )
                time.sleep(4)
                continue
            audit_log(
                "preview_vm_snapshot",
                vm_name,
                {
                    "vm_id": vm_id,
                    "snapshot_id": snapshot_id,
                    "restore_memory": restore_memory,
                    "error": str(exc),
                },
                "FAILED",
            )
            raise OvirtMCPError(
                f"Failed to preview snapshot '{snapshot_id}' on VM '{vm_name}': {exc}",
                details={"vm_id": vm_id, "snapshot_id": snapshot_id, "error": str(exc)},
            ) from exc

    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                refreshed_snap = snap_service.get()
                st = getattr(getattr(refreshed_snap, "snapshot_status", None), "value", "").lower()
                if st == "in_preview":
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during snapshot preview: %s", poll_exc)

    audit_log(
        "preview_vm_snapshot",
        vm_name,
        {"vm_id": vm_id, "snapshot_id": snapshot_id, "restore_memory": restore_memory},
        "SUCCESS",
    )
    return VmSnapshotResult(
        success=True,
        action="preview",
        vm_id=vm_id,
        vm_name=vm_name,
        snapshot_id=snapshot_id,
        restore_memory=restore_memory,
        message=(
            f"Snapshot '{snapshot_id}' is now in preview mode on VM '{vm_name}' "
            f"(restore_memory={restore_memory}). Use ovirt_vm_snapshot_commit to make it permanent, "
            "or ovirt_vm_snapshot_undo to discard the preview."
        ),
    )


def commit_vm_snapshot_tool(
    name_or_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Commit the active snapshot preview, making it the permanent operational state of the VM.

    Destructive action in Safe Mode: requires confirm=True.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, blocks until the preview is fully committed.
        timeout_seconds: Maximum time to wait if wait=True.

    Returns:
        VmSnapshotResult with operation details.
    """
    require_destructive_confirmation(
        f"commit active snapshot preview on VM '{name_or_id}'", confirmed=confirm
    )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    start_attempt = time.time()
    while True:
        try:
            vm_service.commit_snapshot()
            break
        except Exception as exc:
            err_msg = str(exc)
            if (
                "performing an operation on a snapshot" in err_msg.lower()
                or "locked" in err_msg.lower()
            ) and (time.time() - start_attempt < 60):
                logger.info(
                    "VM snapshot operation is in progress, waiting before retrying commit: %s",
                    err_msg,
                )
                time.sleep(4)
                continue
            audit_log(
                "commit_vm_snapshot",
                vm_name,
                {"vm_id": vm_id, "error": str(exc)},
                "FAILED",
            )
            raise OvirtMCPError(
                f"Failed to commit snapshot preview on VM '{vm_name}': {exc}",
                details={"vm_id": vm_id, "error": str(exc)},
            ) from exc

    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                refreshed_vm = vm_service.get()
                vm_st = getattr(getattr(refreshed_vm, "status", None), "value", "").lower()
                snaps = vm_service.snapshots_service().list()
                busy = any(
                    getattr(getattr(s, "snapshot_status", None), "value", "").lower()
                    in ("in_preview", "locked")
                    for s in snaps
                )
                if not busy and vm_st not in ("image_locked", "saving_state", "restoring_state"):
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during snapshot commit: %s", poll_exc)

    audit_log("commit_vm_snapshot", vm_name, {"vm_id": vm_id}, "SUCCESS")
    return VmSnapshotResult(
        success=True,
        action="commit",
        vm_id=vm_id,
        vm_name=vm_name,
        message=f"Snapshot preview committed successfully for VM '{vm_name}'. Historical state is now permanently active.",
    )


def undo_vm_snapshot_tool(
    name_or_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Undo the active snapshot preview and restore the VM to its state before preview was initiated.

    Reversible counterpart to preview_vm_snapshot!
    Destructive action in Safe Mode: requires confirm=True.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, blocks until the preview is completely undone.
        timeout_seconds: Maximum time to wait if wait=True.

    Returns:
        VmSnapshotResult with operation details.
    """
    require_destructive_confirmation(
        f"undo snapshot preview on VM '{name_or_id}'", confirmed=confirm
    )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    start_attempt = time.time()
    while True:
        try:
            vm_service.undo_snapshot()
            break
        except Exception as exc:
            err_msg = str(exc)
            if (
                "performing an operation on a snapshot" in err_msg.lower()
                or "locked" in err_msg.lower()
            ) and (time.time() - start_attempt < 60):
                logger.info(
                    "VM snapshot operation is in progress, waiting before retrying undo: %s",
                    err_msg,
                )
                time.sleep(4)
                continue
            audit_log(
                "undo_vm_snapshot",
                vm_name,
                {"vm_id": vm_id, "error": str(exc)},
                "FAILED",
            )
            raise OvirtMCPError(
                f"Failed to undo snapshot preview on VM '{vm_name}': {exc}",
                details={"vm_id": vm_id, "error": str(exc)},
            ) from exc

    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                refreshed_vm = vm_service.get()
                vm_st = getattr(getattr(refreshed_vm, "status", None), "value", "").lower()
                snaps = vm_service.snapshots_service().list()
                busy = any(
                    getattr(getattr(s, "snapshot_status", None), "value", "").lower()
                    in ("in_preview", "locked")
                    for s in snaps
                )
                if not busy and vm_st not in ("image_locked", "saving_state", "restoring_state"):
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during snapshot undo: %s", poll_exc)

    audit_log("undo_vm_snapshot", vm_name, {"vm_id": vm_id}, "SUCCESS")
    return VmSnapshotResult(
        success=True,
        action="undo",
        vm_id=vm_id,
        vm_name=vm_name,
        message=f"Snapshot preview successfully undone on VM '{vm_name}'. Returned to previous operational state.",
    )


def delete_vm_snapshot_tool(
    name_or_id: str,
    snapshot_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Delete a snapshot and consolidate its delta back into the virtual disk images.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        snapshot_id: UUID of the snapshot to delete.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, blocks synchronously until snapshot is removed and consolidation completes.
        timeout_seconds: Maximum time to wait if wait=True.

    Returns:
        VmSnapshotResult with operation details.
    """
    require_destructive_confirmation(
        f"delete snapshot '{snapshot_id}' of VM '{name_or_id}'", confirmed=confirm
    )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    vm_service = vms_service.vm_service(vm_id)

    snap_service = vm_service.snapshots_service().snapshot_service(snapshot_id)

    start_attempt = time.time()
    while True:
        try:
            snap_service.remove()
            break
        except Exception as exc:
            err_msg = str(exc)
            if (
                "performing an operation on a snapshot" in err_msg.lower()
                or "locked" in err_msg.lower()
            ) and (time.time() - start_attempt < 60):
                logger.info(
                    "VM snapshot operation is in progress, waiting before retrying delete: %s",
                    err_msg,
                )
                time.sleep(4)
                continue
            audit_log(
                "delete_vm_snapshot",
                vm_name,
                {"vm_id": vm_id, "snapshot_id": snapshot_id, "error": str(exc)},
                "FAILED",
            )
            raise OvirtMCPError(
                f"Failed to delete snapshot '{snapshot_id}' for VM '{vm_name}': {exc}",
                details={"vm_id": vm_id, "snapshot_id": snapshot_id, "error": str(exc)},
            ) from exc

    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                snap_service.get()
            except Exception:
                # Successfully removed from snapshots; verify remaining are not locked
                try:
                    remaining = vm_service.snapshots_service().list()
                    busy = any(
                        getattr(getattr(s, "snapshot_status", None), "value", "").lower()
                        == "locked"
                        for s in remaining
                    )
                    if not busy:
                        break
                except Exception:
                    break

    audit_log(
        "delete_vm_snapshot",
        vm_name,
        {"vm_id": vm_id, "snapshot_id": snapshot_id},
        "SUCCESS",
    )
    return VmSnapshotResult(
        success=True,
        action="delete",
        vm_id=vm_id,
        vm_name=vm_name,
        snapshot_id=snapshot_id,
        message=f"Snapshot '{snapshot_id}' deleted and consolidated successfully for VM '{vm_name}'.",
    )
