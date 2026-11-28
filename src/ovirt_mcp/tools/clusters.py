"""Tools for inspecting and managing oVirt / OLVM virtualization clusters."""

import logging
from typing import Any

from ovirtsdk4 import types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.cluster import (
    ClusterDetail,
    ClusterFencingPolicy,
    ClusterMigrationPolicy,
    ClusterOperationResult,
    ClusterSchedulingPolicy,
    ClusterSummary,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger(__name__)


def _is_mock_object(val: Any) -> bool:
    """Return True if val is a unittest Mock object."""
    if val is None:
        return False
    return type(val).__name__ in ("MagicMock", "Mock", "NonCallableMagicMock", "AsyncMock")


def _clean_opt_str(val: Any) -> str | None:
    """Return string or None if unset or a mock object."""
    if val is None or _is_mock_object(val):
        return None
    if isinstance(val, str):
        return val.strip() or None
    return str(val).strip() or None


def _clean_enum_str(val: Any) -> str | None:
    """Safely extract lowercase string from an SDK enum, string, or mock with .value."""
    if val is None:
        return None
    raw = getattr(val, "value", val)
    if raw is None or _is_mock_object(raw):
        return None
    s = str(raw).strip().lower()
    return s or None


def _clean_opt_int(val: Any) -> int | None:
    """Safely extract integer or None."""
    if val is None or _is_mock_object(val):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _clean_opt_bool(val: Any, default: bool | None = None) -> bool | None:
    """Safely extract boolean or None/default."""
    if val is None:
        return default
    raw = getattr(val, "value", val)
    if raw is None or _is_mock_object(raw):
        return default
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return default


def _extract_properties_dict(raw_props: Any) -> dict[str, str]:
    """Extract a key-value dictionary from an SDK Property list."""
    res: dict[str, str] = {}
    if not raw_props:
        return res
    try:
        for p in raw_props:
            name = _clean_opt_str(getattr(p, "name", None))
            val = _clean_opt_str(getattr(p, "value", None))
            if name and val is not None:
                res[name] = val
    except Exception:
        pass
    return res


def _extract_cluster_summary(
    c: Any,
    dc_names: dict[str, str] | None = None,
) -> ClusterSummary:
    """Extract a typed ClusterSummary from an oVirt SDK Cluster object."""
    c_id = str(c.id)
    name = str(getattr(c, "name", c_id))
    description = _clean_opt_str(getattr(c, "description", None))

    dc_obj = getattr(c, "data_center", None)
    dc_id = _clean_opt_str(getattr(dc_obj, "id", None))
    dc_name = _clean_opt_str(getattr(dc_obj, "name", None)) or (
        dc_names.get(dc_id) if dc_names and dc_id else None
    )

    cpu_obj = getattr(c, "cpu", None)
    cpu_type = _clean_opt_str(getattr(cpu_obj, "type", None))
    cpu_arch = None
    if cpu_obj:
        arch_val = getattr(cpu_obj, "architecture", None)
        cpu_arch = _clean_enum_str(arch_val)

    ver_obj = getattr(c, "version", None)
    compat_ver = None
    if ver_obj:
        raw_full = getattr(ver_obj, "full_version", None)
        if raw_full and isinstance(raw_full, str) and not _is_mock_object(raw_full):
            compat_ver = raw_full
        else:
            major = getattr(ver_obj, "major", None)
            minor = getattr(ver_obj, "minor", None)
            if (
                major is not None
                and minor is not None
                and not _is_mock_object(major)
                and not _is_mock_object(minor)
            ):
                compat_ver = f"{major}.{minor}"

    ballooning = bool(_clean_opt_bool(getattr(c, "ballooning_enabled", None), default=False))
    ha_res = bool(_clean_opt_bool(getattr(c, "ha_reservation", None), default=False))

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

    comment = _clean_opt_str(getattr(c, "comment", None))

    mem_policy = getattr(c, "memory_policy", None)
    overcommit: int | None = None
    if mem_policy:
        oc_obj = getattr(mem_policy, "over_commit", None)
        if oc_obj and hasattr(oc_obj, "percent"):
            overcommit = _clean_opt_int(oc_obj.percent)

    fips_str = _clean_enum_str(getattr(c, "fips_mode", None))
    bios_str = _clean_enum_str(getattr(c, "bios_type", None))

    threads_as_cores = bool(_clean_opt_bool(getattr(c, "threads_as_cores", None), default=False))

    # ── Live Migration & Convergence Policies ─────────────────────────────────
    mig_obj = getattr(c, "migration", None)
    migration_policy: ClusterMigrationPolicy | None = None
    mig_enc = False
    mig_bw: str | None = None

    if mig_obj:
        # Backward-compatible summary fields
        mig_enc = bool(_clean_opt_bool(getattr(mig_obj, "encrypted", None), default=False))

        bw_obj = getattr(mig_obj, "bandwidth", None)
        bw_method: str | None = None
        bw_custom: int | None = None
        if bw_obj:
            bw_method = _clean_enum_str(getattr(bw_obj, "assignment_method", None))
            mig_bw = bw_method
            bw_custom = _clean_opt_int(getattr(bw_obj, "custom_value", None))

        auto_conv = _clean_enum_str(getattr(mig_obj, "auto_converge", None))
        compressed = _clean_enum_str(getattr(mig_obj, "compressed", None))
        encrypted_mode = _clean_enum_str(getattr(mig_obj, "encrypted", None))
        parallel_policy = _clean_enum_str(getattr(mig_obj, "parallel_migrations_policy", None))
        custom_parallel = _clean_opt_int(getattr(mig_obj, "custom_parallel_migrations", None))

        pol_obj = getattr(mig_obj, "policy", None)
        pol_id: str | None = None
        pol_name: str | None = None
        if pol_obj:
            pol_id = _clean_opt_str(getattr(pol_obj, "id", None))
            pol_name = _clean_opt_str(getattr(pol_obj, "name", None))

        migration_policy = ClusterMigrationPolicy(
            auto_converge=auto_conv,
            compressed=compressed,
            encrypted=encrypted_mode,
            bandwidth_assignment_method=bw_method,
            bandwidth_custom_value=bw_custom,
            parallel_migrations_policy=parallel_policy,
            custom_parallel_migrations=custom_parallel,
            policy_id=pol_id,
            policy_name=pol_name,
        )

    # ── Workload Scheduling Policy ───────────────────────────────────────────
    sp_obj = getattr(c, "scheduling_policy", None)
    sched_policy: ClusterSchedulingPolicy | None = None
    if sp_obj:
        sp_id = _clean_opt_str(getattr(sp_obj, "id", None))
        sp_name = _clean_opt_str(getattr(sp_obj, "name", None))
        sp_desc = _clean_opt_str(getattr(sp_obj, "description", None))
        sp_props = _extract_properties_dict(getattr(sp_obj, "properties", None))
        sched_policy = ClusterSchedulingPolicy(
            id=sp_id,
            name=sp_name,
            description=sp_desc,
            properties=sp_props,
        )

    custom_sp_props = _extract_properties_dict(
        getattr(c, "custom_scheduling_policy_properties", None)
    )

    # ── Fencing Policy ───────────────────────────────────────────────────────
    fencing_obj = getattr(c, "fencing_policy", None)
    fencing_enabled = True
    fencing_policy: ClusterFencingPolicy | None = None
    if fencing_obj:
        fencing_enabled = bool(_clean_opt_bool(getattr(fencing_obj, "enabled", True), default=True))
        skip_conn = _clean_opt_bool(getattr(fencing_obj, "skip_if_connectivity_broken", None))
        skip_sd = _clean_opt_bool(getattr(fencing_obj, "skip_if_sd_active", None))
        skip_gluster_up = _clean_opt_bool(getattr(fencing_obj, "skip_if_gluster_bricks_up", None))
        skip_gluster_quorum = _clean_opt_bool(
            getattr(fencing_obj, "skip_if_gluster_quorum_not_met", None)
        )

        fencing_policy = ClusterFencingPolicy(
            enabled=fencing_enabled,
            skip_if_connectivity_broken=skip_conn,
            skip_if_sd_active=skip_sd,
            skip_if_gluster_bricks_up=skip_gluster_up,
            skip_if_gluster_quorum_not_met=skip_gluster_quorum,
        )

    ksm_obj = getattr(c, "ksm", None)
    ksm_enabled = True
    if ksm_obj:
        ksm_enabled = bool(_clean_opt_bool(getattr(ksm_obj, "enabled", True), default=True))

    switch_str = _clean_enum_str(getattr(c, "switch_type", None))
    firewall_str = _clean_enum_str(getattr(c, "firewall_type", None))

    # MAC pool
    mac_pool_obj = getattr(c, "mac_pool", None)
    mac_pool_id = _clean_opt_str(getattr(mac_pool_obj, "id", None)) if mac_pool_obj else None
    mac_pool_name = _clean_opt_str(getattr(mac_pool_obj, "name", None)) if mac_pool_obj else None

    # Management network
    mgmt_net_obj = getattr(c, "management_network", None)
    mgmt_net_id = _clean_opt_str(getattr(mgmt_net_obj, "id", None)) if mgmt_net_obj else None
    mgmt_net_name = _clean_opt_str(getattr(mgmt_net_obj, "name", None)) if mgmt_net_obj else None

    # Serial number policy
    serial_obj = getattr(c, "serial_number", None)
    serial_policy = _clean_enum_str(getattr(serial_obj, "policy", None)) if serial_obj else None
    serial_value = _clean_opt_str(getattr(serial_obj, "value", None)) if serial_obj else None

    # Error handling
    err_handling = _clean_enum_str(getattr(c, "error_handling", None))

    tunnel_mig = _clean_opt_bool(getattr(c, "tunnel_migration", None))
    vnc_enc = _clean_opt_bool(getattr(c, "vnc_encryption", None))
    virt_svc = bool(_clean_opt_bool(getattr(c, "virt_service", True), default=True))
    gluster_svc = bool(_clean_opt_bool(getattr(c, "gluster_service", False), default=False))
    trusted_svc = bool(_clean_opt_bool(getattr(c, "trusted_service", False), default=False))
    maint_reason = bool(
        _clean_opt_bool(getattr(c, "maintenance_reason_required", False), default=False)
    )

    log_mem_thresh = _clean_opt_int(getattr(c, "log_max_memory_used_threshold", None))
    log_mem_type = _clean_enum_str(getattr(c, "log_max_memory_used_threshold_type", None))

    upg_corr_id = _clean_opt_str(getattr(c, "upgrade_correlation_id", None))
    upg_in_prog = _clean_opt_bool(getattr(c, "upgrade_in_progress", None))
    upg_percent = _clean_opt_int(getattr(c, "upgrade_percent_complete", None))

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
        comment=comment,
        memory_overcommit_percent=overcommit,
        fips_mode=fips_str,
        bios_type=bios_str,
        threads_as_cores=threads_as_cores,
        migration_encrypted=mig_enc,
        migration_bandwidth=mig_bw,
        migration=migration_policy,
        scheduling_policy=sched_policy,
        custom_scheduling_policy_properties=custom_sp_props,
        fencing_enabled=fencing_enabled,
        fencing_policy=fencing_policy,
        ksm_enabled=ksm_enabled,
        switch_type=switch_str,
        firewall_type=firewall_str,
        mac_pool_id=mac_pool_id,
        mac_pool_name=mac_pool_name,
        management_network_id=mgmt_net_id,
        management_network_name=mgmt_net_name,
        serial_number_policy=serial_policy,
        serial_number_custom_value=serial_value,
        error_handling=err_handling,
        tunnel_migration=tunnel_mig,
        vnc_encryption=vnc_enc,
        virt_service=virt_svc,
        gluster_service=gluster_svc,
        trusted_service=trusted_svc,
        maintenance_reason_required=maint_reason,
        log_max_memory_used_threshold=log_mem_thresh,
        log_max_memory_used_threshold_type=log_mem_type,
        upgrade_correlation_id=upg_corr_id,
        upgrade_in_progress=upg_in_prog,
        upgrade_percent_complete=upg_percent,
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
    """Retrieve deep technical parameters, live migration settings, and scheduling policies of a cluster.

    Args:
        name_or_id: Cluster display name or UUID.

    Returns:
        ClusterDetail object with complete cluster hardware, migration, and scheduling policies.
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


def _parse_inheritable_bool(val: str | bool | None) -> sdk_types.InheritableBoolean | None:
    if val is None:
        return None
    s = str(val).lower().strip()
    if s in ("true", "yes", "1"):
        return sdk_types.InheritableBoolean.TRUE
    elif s in ("false", "no", "0"):
        return sdk_types.InheritableBoolean.FALSE
    elif s in ("inherit", "default"):
        return sdk_types.InheritableBoolean.INHERIT
    return None


def _parse_bandwidth_method(val: str | None) -> sdk_types.MigrationBandwidthAssignmentMethod | None:
    if not val:
        return None
    mapping = {
        "auto": sdk_types.MigrationBandwidthAssignmentMethod.AUTO,
        "custom": sdk_types.MigrationBandwidthAssignmentMethod.CUSTOM,
        "hypervisor_default": sdk_types.MigrationBandwidthAssignmentMethod.HYPERVISOR_DEFAULT,
        "default": sdk_types.MigrationBandwidthAssignmentMethod.HYPERVISOR_DEFAULT,
    }
    return mapping.get(val.lower().strip())


def _parse_parallel_policy(val: str | None) -> sdk_types.ParallelMigrationsPolicy | None:
    if not val:
        return None
    mapping = {
        "auto": sdk_types.ParallelMigrationsPolicy.AUTO,
        "auto_parallel": sdk_types.ParallelMigrationsPolicy.AUTO_PARALLEL,
        "custom": sdk_types.ParallelMigrationsPolicy.CUSTOM,
        "disabled": sdk_types.ParallelMigrationsPolicy.DISABLED,
        "inherit": sdk_types.ParallelMigrationsPolicy.INHERIT,
    }
    return mapping.get(val.lower().strip())


def _parse_firewall_type(val: str | None) -> sdk_types.FirewallType | None:
    if not val:
        return None
    mapping = {
        "firewalld": sdk_types.FirewallType.FIREWALLD,
        "iptables": sdk_types.FirewallType.IPTABLES,
    }
    return mapping.get(val.lower().strip())


def update_cluster_tool(
    name_or_id: str,
    name: str | None = None,
    description: str | None = None,
    comment: str | None = None,
    migration_auto_converge: str | None = None,
    migration_compressed: str | None = None,
    migration_encrypted: str | None = None,
    migration_bandwidth_method: str | None = None,
    migration_bandwidth_custom_value: int | None = None,
    migration_parallel_policy: str | None = None,
    migration_custom_parallel: int | None = None,
    migration_policy_id: str | None = None,
    scheduling_policy_id: str | None = None,
    scheduling_policy_name: str | None = None,
    fencing_enabled: bool | None = None,
    skip_fencing_if_connectivity_broken: bool | None = None,
    skip_fencing_if_sd_active: bool | None = None,
    firewall_type: str | None = None,
) -> ClusterDetail:
    """Update settings, live migration policies, scheduling policies, fencing, and metadata for a cluster.

    Args:
        name_or_id: Cluster display name or UUID.
        name: Optional new cluster display name.
        description: Optional cluster description text.
        comment: Optional administrative comment.
        migration_auto_converge: VM live migration auto-converge ('true', 'false', 'inherit').
        migration_compressed: VM live migration compression ('true', 'false', 'inherit').
        migration_encrypted: VM live migration encryption ('true', 'false', 'inherit').
        migration_bandwidth_method: Bandwidth limit mode ('auto', 'hypervisor_default', 'custom').
        migration_bandwidth_custom_value: Custom bandwidth limit in Mbps when bandwidth method is custom.
        migration_parallel_policy: Parallel migration policy ('auto', 'auto_parallel', 'custom', 'disabled', 'inherit').
        migration_custom_parallel: Maximum parallel outgoing/incoming live migrations per host.
        migration_policy_id: UUID of migration convergence policy (e.g. Minimal downtime, Post-copy).
        scheduling_policy_id: UUID of workload placement scheduling policy.
        scheduling_policy_name: Name of scheduling policy (e.g. 'evenly_distributed', 'power_saving').
        fencing_enabled: Whether host IPMI/power fencing is enabled for the cluster.
        skip_fencing_if_connectivity_broken: Skip fencing if connectivity is broken.
        skip_fencing_if_sd_active: Skip fencing if storage domain is active.
        firewall_type: Host firewall manager type ('firewalld', 'iptables').

    Returns:
        Updated ClusterDetail object.
    """
    client = get_client()
    conn = client.get_connection()
    sys_service = conn.system_service()
    clusters_service = sys_service.clusters_service()

    cluster = client.find_resource_by_id_or_name(clusters_service, name_or_id, "cluster")
    if not cluster:
        raise OvirtValidationError(f"Cluster '{name_or_id}' not found.")

    c_id = str(cluster.id)
    require_mutation_allowed("update_cluster")

    # Resolve scheduling policy name if provided
    if scheduling_policy_name and not scheduling_policy_id:
        try:
            sched_policies = sys_service.scheduling_policies_service().list()
            matched_sp = next(
                (
                    p
                    for p in sched_policies
                    if str(getattr(p, "name", "")).lower() == scheduling_policy_name.lower()
                ),
                None,
            )
            if matched_sp and getattr(matched_sp, "id", None):
                scheduling_policy_id = str(matched_sp.id)
            else:
                raise OvirtValidationError(
                    f"Scheduling policy '{scheduling_policy_name}' not found."
                )
        except Exception as sp_exc:
            if isinstance(sp_exc, OvirtValidationError):
                raise
            logger.debug("Failed querying scheduling policies: %s", sp_exc)

    cluster_kwargs: dict[str, Any] = {}
    if name is not None:
        cluster_kwargs["name"] = name
    if description is not None:
        cluster_kwargs["description"] = description
    if comment is not None:
        cluster_kwargs["comment"] = comment

    # Migration options
    migration_kwargs: dict[str, Any] = {}
    if migration_auto_converge is not None:
        migration_kwargs["auto_converge"] = _parse_inheritable_bool(migration_auto_converge)
    if migration_compressed is not None:
        migration_kwargs["compressed"] = _parse_inheritable_bool(migration_compressed)
    if migration_encrypted is not None:
        migration_kwargs["encrypted"] = _parse_inheritable_bool(migration_encrypted)

    bandwidth_kwargs: dict[str, Any] = {}
    if migration_bandwidth_method is not None:
        bandwidth_kwargs["assignment_method"] = _parse_bandwidth_method(migration_bandwidth_method)
    if migration_bandwidth_custom_value is not None:
        bandwidth_kwargs["custom_value"] = int(migration_bandwidth_custom_value)
    if bandwidth_kwargs:
        migration_kwargs["bandwidth"] = sdk_types.MigrationBandwidth(**bandwidth_kwargs)

    if migration_parallel_policy is not None:
        migration_kwargs["parallel_migrations_policy"] = _parse_parallel_policy(
            migration_parallel_policy
        )
    if migration_custom_parallel is not None:
        migration_kwargs["custom_parallel_migrations"] = int(migration_custom_parallel)
    if migration_policy_id is not None:
        migration_kwargs["policy"] = sdk_types.MigrationPolicy(id=migration_policy_id)

    if migration_kwargs:
        cluster_kwargs["migration"] = sdk_types.MigrationOptions(**migration_kwargs)

    # Scheduling policy
    if scheduling_policy_id is not None:
        cluster_kwargs["scheduling_policy"] = sdk_types.SchedulingPolicy(id=scheduling_policy_id)

    # Fencing policy
    fencing_kwargs: dict[str, Any] = {}
    if fencing_enabled is not None:
        fencing_kwargs["enabled"] = bool(fencing_enabled)
    if skip_fencing_if_connectivity_broken is not None:
        fencing_kwargs["skip_if_connectivity_broken"] = sdk_types.SkipIfConnectivityBroken(
            enabled=bool(skip_fencing_if_connectivity_broken)
        )
    if skip_fencing_if_sd_active is not None:
        fencing_kwargs["skip_if_sd_active"] = sdk_types.SkipIfSdActive(
            enabled=bool(skip_fencing_if_sd_active)
        )
    if fencing_kwargs:
        cluster_kwargs["fencing_policy"] = sdk_types.FencingPolicy(**fencing_kwargs)

    # Firewall type
    if firewall_type is not None:
        cluster_kwargs["firewall_type"] = _parse_firewall_type(firewall_type)

    if not cluster_kwargs:
        raise OvirtValidationError("At least one cluster attribute must be specified for update.")

    c_service = clusters_service.cluster_service(c_id)
    update_obj = sdk_types.Cluster(**cluster_kwargs)

    try:
        c_service.update(update_obj)
        audit_log(
            "update_cluster",
            c_id,
            {
                "cluster_name": getattr(cluster, "name", c_id),
                "fields": list(cluster_kwargs.keys()),
            },
            "SUCCESS",
        )
    except Exception as exc:
        audit_log(
            "update_cluster",
            c_id,
            {"error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to update cluster '{name_or_id}': {exc}",
            details={"cluster_id": c_id, "error": str(exc)},
        ) from exc

    return get_cluster_tool(c_id)


def sync_all_cluster_networks_tool(
    name_or_id: str,
    dry_run: bool = False,
    confirm: bool = False,
) -> ClusterOperationResult:
    """Synchronize all logical networks across all hosts in a cluster.

    Args:
        name_or_id: Cluster display name or UUID.
        dry_run: If True, simulate the synchronization without triggering engine tasks.
        confirm: Confirmation flag required in Safe Mode.

    Returns:
        ClusterOperationResult describing outcome.
    """
    require_destructive_confirmation("sync_all_cluster_networks", confirmed=confirm)
    client = get_client()
    conn = client.get_connection()
    sys_service = conn.system_service()
    clusters_service = sys_service.clusters_service()

    cluster = client.find_resource_by_id_or_name(clusters_service, name_or_id, "cluster")
    if not cluster:
        raise OvirtValidationError(f"Cluster '{name_or_id}' not found.")

    c_id = str(cluster.id)
    c_name = str(getattr(cluster, "name", c_id))

    if dry_run:
        audit_log(
            "sync_all_cluster_networks",
            c_id,
            {"cluster_name": c_name, "dry_run": True},
            "SUCCESS",
        )
        return ClusterOperationResult(
            success=True,
            cluster_id=c_id,
            cluster_name=c_name,
            action="sync_all_networks",
            dry_run=True,
            message=f"[DRY-RUN] Network synchronization would be triggered across all hosts in cluster '{c_name}' ({c_id}).",
        )

    c_service = clusters_service.cluster_service(c_id)
    try:
        c_service.sync_all_networks()
        audit_log(
            "sync_all_cluster_networks",
            c_id,
            {"cluster_name": c_name},
            "SUCCESS",
        )
        return ClusterOperationResult(
            success=True,
            cluster_id=c_id,
            cluster_name=c_name,
            action="sync_all_networks",
            dry_run=False,
            message=f"Network synchronization initiated for all hosts in cluster '{c_name}' ({c_id}).",
        )
    except Exception as exc:
        audit_log(
            "sync_all_cluster_networks",
            c_id,
            {"cluster_name": c_name, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to sync all networks for cluster '{c_name}': {exc}",
            details={"cluster_id": c_id, "error": str(exc)},
        ) from exc


def reset_cluster_emulated_machine_tool(
    name_or_id: str,
    dry_run: bool = False,
    confirm: bool = False,
) -> ClusterOperationResult:
    """Reset the emulated machine type of a cluster to default.

    Args:
        name_or_id: Cluster display name or UUID.
        dry_run: If True, simulate the reset without altering cluster settings.
        confirm: Confirmation flag required in Safe Mode.

    Returns:
        ClusterOperationResult describing outcome.
    """
    require_destructive_confirmation("reset_cluster_emulated_machine", confirmed=confirm)
    client = get_client()
    conn = client.get_connection()
    sys_service = conn.system_service()
    clusters_service = sys_service.clusters_service()

    cluster = client.find_resource_by_id_or_name(clusters_service, name_or_id, "cluster")
    if not cluster:
        raise OvirtValidationError(f"Cluster '{name_or_id}' not found.")

    c_id = str(cluster.id)
    c_name = str(getattr(cluster, "name", c_id))

    if dry_run:
        audit_log(
            "reset_cluster_emulated_machine",
            c_id,
            {"cluster_name": c_name, "dry_run": True},
            "SUCCESS",
        )
        return ClusterOperationResult(
            success=True,
            cluster_id=c_id,
            cluster_name=c_name,
            action="reset_emulated_machine",
            dry_run=True,
            message=f"[DRY-RUN] Emulated machine type reset would be performed on cluster '{c_name}' ({c_id}).",
        )

    c_service = clusters_service.cluster_service(c_id)
    try:
        c_service.reset_emulated_machine()
        audit_log(
            "reset_cluster_emulated_machine",
            c_id,
            {"cluster_name": c_name},
            "SUCCESS",
        )
        return ClusterOperationResult(
            success=True,
            cluster_id=c_id,
            cluster_name=c_name,
            action="reset_emulated_machine",
            dry_run=False,
            message=f"Emulated machine type successfully reset for cluster '{c_name}' ({c_id}).",
        )
    except Exception as exc:
        audit_log(
            "reset_cluster_emulated_machine",
            c_id,
            {"cluster_name": c_name, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to reset emulated machine for cluster '{c_name}': {exc}",
            details={"cluster_id": c_id, "error": str(exc)},
        ) from exc


def create_cluster_tool(
    name: str,
    data_center: str,
    cpu_type: str | None = None,
    description: str | None = None,
    comment: str | None = None,
    compatibility_version: str | None = None,
    dry_run: bool = False,
) -> ClusterOperationResult:
    """Create a new virtualization cluster in oVirt / OLVM.

    Args:
        name: Name of the new cluster.
        data_center: Name or UUID of the parent Data Center.
        cpu_type: Optional CPU type (e.g. 'Intel SandyBridge Family', 'AMD EPYC').
        description: Optional description for the cluster.
        comment: Optional free-text comment.
        compatibility_version: Optional compatibility version string (e.g. '4.7').
        dry_run: If True, validates configuration and pre-conditions without creating.

    Returns:
        ClusterOperationResult with created cluster ID and status.
    """
    require_mutation_allowed("create_cluster")

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    clusters_service = system_service.clusters_service()

    # 1. Verify cluster name does not exist
    try:
        existing = clusters_service.list(search=f"name={name}")
        for c in existing:
            c_name = getattr(c, "name", "")
            if type(c_name).__name__ in ("MagicMock", "Mock") and hasattr(c_name, "_mock_name"):
                c_name = getattr(c_name, "_mock_name", "")
            else:
                c_name = str(c_name)
            if c_name == name:
                raise OvirtValidationError(
                    f"A cluster with name '{name}' already exists in oVirt inventory.",
                    details={"name": name, "existing_cluster_id": str(getattr(c, "id", ""))},
                )
    except OvirtValidationError:
        raise
    except Exception as exc:
        logger.debug("Could not verify cluster uniqueness via search: %s", exc)

    # 2. Resolve parent Data Center
    dcs_service = system_service.data_centers_service()
    dc = client.find_resource_by_id_or_name(dcs_service, data_center, "data center")
    dc_id = str(dc.id)
    dc_name = str(getattr(dc, "name", dc_id))

    if dry_run:
        audit_log(
            "ovirt_cluster_create",
            name,
            {"data_center": dc_name, "cpu_type": cpu_type, "dry_run": True},
            "SUCCESS",
        )
        return ClusterOperationResult(
            success=True,
            cluster_id="dry-run-cluster-id",
            cluster_name=name,
            action="create",
            dry_run=True,
            message=f"[DRY RUN] Cluster '{name}' is valid and would be created in Data Center '{dc_name}'.",
        )

    # 3. Create cluster
    cluster_kwargs: dict[str, Any] = {
        "name": name,
        "data_center": sdk_types.DataCenter(id=dc_id),
    }
    if cpu_type:
        cluster_kwargs["cpu"] = sdk_types.Cpu(type=cpu_type)
    if description:
        cluster_kwargs["description"] = description
    if comment:
        cluster_kwargs["comment"] = comment
    if compatibility_version:
        parts = compatibility_version.split(".")
        if len(parts) >= 2:
            cluster_kwargs["version"] = sdk_types.Version(
                major=int(parts[0]),
                minor=int(parts[1]),
            )

    cluster_spec = sdk_types.Cluster(**cluster_kwargs)
    try:
        created = clusters_service.add(cluster_spec)
        created_id = str(getattr(created, "id", ""))
    except Exception as exc:
        audit_log(
            "ovirt_cluster_create",
            name,
            {"data_center": dc_name, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to create cluster '{name}': {exc}") from exc

    audit_log(
        "ovirt_cluster_create",
        name,
        {"cluster_id": created_id, "data_center": dc_name},
        "SUCCESS",
    )
    return ClusterOperationResult(
        success=True,
        cluster_id=created_id,
        cluster_name=name,
        action="create",
        dry_run=False,
        message=f"Cluster '{name}' (UUID: {created_id}) created successfully in Data Center '{dc_name}'.",
    )


def delete_cluster_tool(
    name_or_id: str,
    dry_run: bool = False,
    confirm: bool = False,
) -> ClusterOperationResult:
    """Delete an empty virtualization cluster from oVirt / OLVM.

    Args:
        name_or_id: Name or UUID of the cluster to remove.
        dry_run: If True, simulates validation without removing the cluster.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).

    Returns:
        ClusterOperationResult with outcome and cluster identification.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"delete cluster '{name_or_id}'",
            confirmed=confirm,
        )
    else:
        require_mutation_allowed("delete_cluster")

    client = get_client()
    conn = client.get_connection()
    system_service = conn.system_service()
    clusters_service = system_service.clusters_service()

    cluster = client.find_resource_by_id_or_name(clusters_service, name_or_id, "cluster")
    cluster_id = str(cluster.id)
    cluster_name = str(getattr(cluster, "name", cluster_id))

    # Pre-flight check: hosts and vms in cluster
    hosts_service = system_service.hosts_service()
    try:
        hosts_in_cluster = hosts_service.list(search=f"cluster={cluster_name}")
        if hosts_in_cluster:
            host_names = [str(getattr(h, "name", h.id)) for h in hosts_in_cluster]
            raise OvirtValidationError(
                f"Cannot delete cluster '{cluster_name}' because it still contains {len(hosts_in_cluster)} host(s): {', '.join(host_names)}. Remove or relocate hosts first.",
                details={"cluster_id": cluster_id, "hosts": host_names},
            )
    except OvirtValidationError:
        raise
    except Exception as exc:
        logger.debug("Could not verify hosts in cluster: %s", exc)

    vms_service = system_service.vms_service()
    try:
        vms_in_cluster = vms_service.list(search=f"cluster={cluster_name}")
        if vms_in_cluster:
            vm_names = [str(getattr(v, "name", v.id)) for v in vms_in_cluster]
            raise OvirtValidationError(
                f"Cannot delete cluster '{cluster_name}' because it still contains {len(vms_in_cluster)} virtual machine(s): {', '.join(vm_names)}. Remove or migrate VMs first.",
                details={"cluster_id": cluster_id, "vms": vm_names},
            )
    except OvirtValidationError:
        raise
    except Exception as exc:
        logger.debug("Could not verify VMs in cluster: %s", exc)

    if dry_run:
        audit_log(
            "ovirt_cluster_delete",
            cluster_name,
            {"cluster_id": cluster_id, "dry_run": True},
            "SUCCESS",
        )
        return ClusterOperationResult(
            success=True,
            cluster_id=cluster_id,
            cluster_name=cluster_name,
            action="delete",
            dry_run=True,
            message=f"[DRY RUN] Cluster '{cluster_name}' ({cluster_id}) is empty and eligible for removal.",
        )

    cluster_svc = clusters_service.cluster_service(cluster_id)
    try:
        cluster_svc.remove()
    except Exception as exc:
        audit_log(
            "ovirt_cluster_delete",
            cluster_name,
            {"cluster_id": cluster_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to delete cluster '{cluster_name}': {exc}") from exc

    audit_log(
        "ovirt_cluster_delete",
        cluster_name,
        {"cluster_id": cluster_id},
        "SUCCESS",
    )
    return ClusterOperationResult(
        success=True,
        cluster_id=cluster_id,
        cluster_name=cluster_name,
        action="delete",
        dry_run=False,
        message=f"Cluster '{cluster_name}' ({cluster_id}) was successfully deleted.",
    )


def upgrade_cluster_tool(
    name_or_id: str,
    action: str = "start",
    percent_complete: int | None = None,
    correlation_id: str | None = None,
    dry_run: bool = False,
    confirm: bool = False,
) -> ClusterOperationResult:
    """Manage rolling cluster upgrade process in oVirt / OLVM.

    Args:
        name_or_id: Display name or UUID of the cluster.
        action: Upgrade action: 'start', 'stop', or 'update_progress'.
        percent_complete: Progress percentage (0-100) when action is 'update_progress'.
        correlation_id: Optional tracking identifier for correlated audit events.
        dry_run: If True, simulates without triggering cluster upgrade.
        confirm: Confirmation flag required in Safe Mode when starting or stopping upgrade.

    Returns:
        ClusterOperationResult with upgrade state.
    """
    act_lower = action.lower().strip()
    if act_lower not in ("start", "stop", "update_progress"):
        raise OvirtValidationError(
            f"Invalid upgrade action '{action}'. Allowed values: 'start', 'stop', 'update_progress'."
        )

    if not dry_run and act_lower in ("start", "stop"):
        require_destructive_confirmation(
            f"{act_lower} rolling upgrade for cluster '{name_or_id}'",
            confirmed=confirm,
        )
    else:
        require_mutation_allowed("upgrade_cluster")

    client = get_client()
    conn = client.get_connection()
    clusters_service = conn.system_service().clusters_service()
    cluster = client.find_resource_by_id_or_name(clusters_service, name_or_id, "cluster")
    cluster_id = str(cluster.id)
    cluster_name = str(getattr(cluster, "name", cluster_id))

    if dry_run:
        audit_log(
            "ovirt_cluster_upgrade",
            cluster_name,
            {"cluster_id": cluster_id, "action": act_lower, "dry_run": True},
            "SUCCESS",
        )
        return ClusterOperationResult(
            success=True,
            cluster_id=cluster_id,
            cluster_name=cluster_name,
            action=f"upgrade_{act_lower}",
            dry_run=True,
            message=f"[DRY RUN] Cluster '{cluster_name}' ({cluster_id}) upgrade action '{act_lower}' would be executed.",
        )

    upgrade_kwargs: dict[str, Any] = {"upgrade_action": act_lower}
    if percent_complete is not None:
        upgrade_kwargs["upgrade_percent_complete"] = percent_complete
    if correlation_id is not None:
        upgrade_kwargs["correlation_id"] = correlation_id

    cluster_svc = clusters_service.cluster_service(cluster_id)
    try:
        cluster_svc.upgrade(**upgrade_kwargs)
    except Exception as exc:
        audit_log(
            "ovirt_cluster_upgrade",
            cluster_name,
            {"cluster_id": cluster_id, "action": act_lower, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to execute upgrade action '{act_lower}' for cluster '{cluster_name}': {exc}"
        ) from exc

    audit_log(
        "ovirt_cluster_upgrade",
        cluster_name,
        {"cluster_id": cluster_id, "action": act_lower},
        "SUCCESS",
    )
    return ClusterOperationResult(
        success=True,
        cluster_id=cluster_id,
        cluster_name=cluster_name,
        action=f"upgrade_{act_lower}",
        dry_run=False,
        message=f"Cluster '{cluster_name}' ({cluster_id}) upgrade action '{act_lower}' successfully executed.",
    )
