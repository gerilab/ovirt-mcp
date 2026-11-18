"""Affinity Labels and Cluster Affinity Groups management tools for oVirt / OLVM."""

import contextlib
import logging
import uuid
from typing import Any

from ovirtsdk4 import types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import NotFoundError, OvirtValidationError
from ovirt_mcp.models.affinity import (
    AffinityGroupInfo,
    AffinityGroupResult,
    AffinityLabelInfo,
    AffinityLabelResult,
    AffinityRuleConfig,
    EntityLabelResult,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)

logger = logging.getLogger("ovirt_mcp.tools.affinity")


def _is_uuid(val: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError):
        return False


def _find_label_by_id_or_name(labels_service: Any, identifier: str) -> Any:
    """Find an affinity label by UUID or exact name."""
    if _is_uuid(identifier):
        try:
            lbl_svc = labels_service.label_service(identifier)
            lbl = lbl_svc.get()
            if lbl is not None:
                return lbl
        except Exception:
            pass

    for lbl in labels_service.list():
        if lbl.name == identifier or lbl.id == identifier:
            return lbl

    raise NotFoundError(
        resource_type="affinity_label",
        identifier=identifier,
    )


def _find_affinity_group_by_id_or_name(groups_service: Any, identifier: str) -> Any:
    """Find an affinity group in a cluster by UUID or exact name."""
    if _is_uuid(identifier):
        try:
            group_svc = groups_service.group_service(identifier)
            ag = group_svc.get()
            if ag is not None:
                return ag
        except Exception:
            pass

    for ag in groups_service.list():
        if ag.name == identifier or ag.id == identifier:
            return ag

    raise NotFoundError(
        resource_type="affinity_group",
        identifier=identifier,
    )


def _extract_rule(
    rule_obj: Any, legacy_pos: bool | None, legacy_enf: bool | None
) -> AffinityRuleConfig | None:
    """Extract AffinityRuleConfig handling modern AffinityRule and legacy fields."""
    if rule_obj is not None:
        return AffinityRuleConfig(
            enabled=bool(rule_obj.enabled)
            if hasattr(rule_obj, "enabled") and rule_obj.enabled is not None
            else True,
            positive=bool(rule_obj.positive)
            if hasattr(rule_obj, "positive") and rule_obj.positive is not None
            else True,
            enforcing=bool(rule_obj.enforcing)
            if hasattr(rule_obj, "enforcing") and rule_obj.enforcing is not None
            else False,
        )
    if legacy_pos is not None:
        return AffinityRuleConfig(
            enabled=True,
            positive=bool(legacy_pos),
            enforcing=bool(legacy_enf) if legacy_enf is not None else False,
        )
    return None


def _build_affinity_group_info(
    groups_service: Any,
    ag: Any,
    cluster_id: str,
    cluster_name: str,
    host_map: dict[str, str],
    vm_map: dict[str, str],
) -> AffinityGroupInfo:
    """Build AffinityGroupInfo from SDK AffinityGroup and sub-collections."""
    ag_svc = groups_service.group_service(ag.id)
    ag_detail = ag_svc.get()

    vms_rule = _extract_rule(
        getattr(ag_detail, "vms_rule", None),
        getattr(ag_detail, "positive", None),
        getattr(ag_detail, "enforcing", None),
    )
    hosts_rule = _extract_rule(
        getattr(ag_detail, "hosts_rule", None),
        None,
        None,
    )

    # Sub-collection member queries
    member_vms: list[str] = []
    try:
        for v in ag_svc.vms_service().list():
            member_vms.append(v.name or vm_map.get(str(v.id), str(v.id)))
    except Exception as e:
        logger.debug("Failed querying VMs for affinity group %s: %s", ag.id, e)

    member_hosts: list[str] = []
    try:
        for h in ag_svc.hosts_service().list():
            member_hosts.append(h.name or host_map.get(str(h.id), str(h.id)))
    except Exception as e:
        logger.debug("Failed querying hosts for affinity group %s: %s", ag.id, e)

    member_vm_labels: list[str] = []
    try:
        for lbl in ag_svc.vm_labels_service().list():
            member_vm_labels.append(lbl.name or str(lbl.id))
    except Exception as e:
        logger.debug("Failed querying VM labels for affinity group %s: %s", ag.id, e)

    member_host_labels: list[str] = []
    try:
        for lbl in ag_svc.host_labels_service().list():
            member_host_labels.append(lbl.name or str(lbl.id))
    except Exception as e:
        logger.debug("Failed querying host labels for affinity group %s: %s", ag.id, e)

    priority_val: float | None = None
    if getattr(ag_detail, "priority", None) is not None:
        with contextlib.suppress(ValueError, TypeError):
            priority_val = float(ag_detail.priority)

    return AffinityGroupInfo(
        id=str(ag_detail.id),
        name=str(ag_detail.name),
        cluster_id=cluster_id,
        cluster_name=cluster_name,
        description=str(ag_detail.description) if ag_detail.description else None,
        priority=priority_val,
        vms_rule=vms_rule,
        hosts_rule=hosts_rule,
        vms=member_vms,
        hosts=member_hosts,
        vm_labels=member_vm_labels,
        host_labels=member_host_labels,
    )


# =========================================================================
# 1. Global Affinity Labels
# =========================================================================


def ovirt_affinity_label_list() -> list[AffinityLabelInfo]:
    """List all global Affinity Labels with their assigned hosts and VMs.

    Returns:
        List of AffinityLabelInfo objects containing label IDs, names, and member entities.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    labels_svc = sys_svc.affinity_labels_service()

    # Pre-fetch lookup maps to minimize round-trips
    host_map = {str(h.id): str(h.name) for h in sys_svc.hosts_service().list()}
    vm_map = {str(v.id): str(v.name) for v in sys_svc.vms_service().list()}

    labels = labels_svc.list()
    result: list[AffinityLabelInfo] = []

    for lbl in labels:
        lbl_svc = labels_svc.label_service(lbl.id)
        assigned_hosts: list[str] = []
        assigned_vms: list[str] = []

        try:
            for h in lbl_svc.hosts_service().list():
                assigned_hosts.append(host_map.get(str(h.id), str(h.name or h.id)))
        except Exception as e:
            logger.debug("Error listing hosts for label %s: %s", lbl.id, e)

        try:
            for v in lbl_svc.vms_service().list():
                assigned_vms.append(vm_map.get(str(v.id), str(v.name or v.id)))
        except Exception as e:
            logger.debug("Error listing VMs for label %s: %s", lbl.id, e)

        result.append(
            AffinityLabelInfo(
                id=str(lbl.id),
                name=str(lbl.name),
                hosts=assigned_hosts,
                vms=assigned_vms,
            )
        )

    return result


def ovirt_affinity_label_create(name: str) -> AffinityLabelResult:
    """Create a new global Affinity Label.

    Args:
        name: Name of the affinity label to create.

    Returns:
        AffinityLabelResult with creation status.
    """
    require_mutation_allowed("ovirt_affinity_label_create")

    name_clean = name.strip()
    if not name_clean:
        raise OvirtValidationError("Affinity label name must not be empty.")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    labels_svc = sys_svc.affinity_labels_service()

    # Pre-check existence
    for existing in labels_svc.list():
        if existing.name == name_clean:
            raise OvirtValidationError(
                f"Affinity label '{name_clean}' already exists (id: {existing.id}).",
                details={"label_name": name_clean, "label_id": str(existing.id)},
            )

    created = labels_svc.add(sdk_types.AffinityLabel(name=name_clean))
    audit_log(
        "ovirt_affinity_label_create",
        name_clean,
        {"label_id": str(created.id)},
        "SUCCESS",
    )

    return AffinityLabelResult(
        success=True,
        label_id=str(created.id),
        label_name=str(created.name),
        action="create",
        message=f"Affinity label '{created.name}' created successfully with UUID {created.id}.",
    )


def ovirt_affinity_label_delete(
    name_or_id: str,
    confirm: bool = False,
    detach_first: bool = False,
) -> AffinityLabelResult:
    """Delete an existing Affinity Label.

    Args:
        name_or_id: UUID or name of the affinity label to delete.
        confirm: Confirmation flag required in safe-mode.
        detach_first: If True, automatically detaches the label from all assigned hosts and VMs
                     before deleting, avoiding HTTP 409 conflict errors.

    Returns:
        AffinityLabelResult with deletion status.
    """
    require_destructive_confirmation("ovirt_affinity_label_delete", confirm)

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    labels_svc = sys_svc.affinity_labels_service()

    label = _find_label_by_id_or_name(labels_svc, name_or_id)
    lbl_svc = labels_svc.label_service(label.id)

    # Check attached entities
    attached_hosts = lbl_svc.hosts_service().list()
    attached_vms = lbl_svc.vms_service().list()

    if attached_hosts or attached_vms:
        if not detach_first:
            host_ids = [str(h.id) for h in attached_hosts]
            vm_ids = [str(v.id) for v in attached_vms]
            raise OvirtValidationError(
                f"Cannot delete affinity label '{label.name}' because it is currently assigned to "
                f"{len(attached_hosts)} host(s) ({host_ids}) and {len(attached_vms)} VM(s) ({vm_ids}). "
                "Remove the label from all entities first, or pass detach_first=True to detach automatically.",
                details={
                    "label_id": str(label.id),
                    "label_name": str(label.name),
                    "hosts_count": len(attached_hosts),
                    "vms_count": len(attached_vms),
                },
            )

        # Detach automatically when detach_first is True
        for h in attached_hosts:
            lbl_svc.hosts_service().host_service(h.id).remove()
        for v in attached_vms:
            lbl_svc.vms_service().vm_service(v.id).remove()

    lbl_svc.remove()
    audit_log(
        "ovirt_affinity_label_delete",
        str(label.name),
        {"label_id": str(label.id), "detach_first": detach_first},
        "SUCCESS",
    )

    return AffinityLabelResult(
        success=True,
        label_id=str(label.id),
        label_name=str(label.name),
        action="delete",
        message=f"Affinity label '{label.name}' deleted successfully.",
    )


# =========================================================================
# 2. Host Affinity Labels
# =========================================================================


def ovirt_host_label_list(host_name_or_id: str) -> list[str]:
    """List all Affinity Labels currently assigned to a hypervisor host.

    Args:
        host_name_or_id: UUID or name of the hypervisor host.

    Returns:
        List of affinity label names attached to the host.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    h_svc = hosts_svc.host_service(host.id)
    labels = h_svc.affinity_labels_service().list()

    return [str(lbl.name or lbl.id) for lbl in labels]


def ovirt_host_label_assign(host_name_or_id: str, label_name_or_id: str) -> EntityLabelResult:
    """Assign an Affinity Label to a hypervisor host.

    Args:
        host_name_or_id: UUID or name of the hypervisor host.
        label_name_or_id: UUID or name of the affinity label to assign.

    Returns:
        EntityLabelResult detailing assignment status and current labels.
    """
    require_mutation_allowed("ovirt_host_label_assign")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()
    labels_svc = sys_svc.affinity_labels_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    label = _find_label_by_id_or_name(labels_svc, label_name_or_id)

    h_svc = hosts_svc.host_service(host.id)
    h_labels_svc = h_svc.affinity_labels_service()

    # Check if already assigned
    existing = h_labels_svc.list()
    if any(lbl.id == label.id for lbl in existing):
        current_names = [str(lbl.name or lbl.id) for lbl in existing]
        return EntityLabelResult(
            success=True,
            entity_type="host",
            entity_id=str(host.id),
            entity_name=str(host.name),
            label_id=str(label.id),
            label_name=str(label.name),
            action="assign",
            current_labels=current_names,
            message=f"Host '{host.name}' already has affinity label '{label.name}'.",
        )

    h_labels_svc.add(sdk_types.AffinityLabel(id=label.id))
    current_names = [str(lbl.name or lbl.id) for lbl in h_labels_svc.list()]

    audit_log(
        "ovirt_host_label_assign",
        str(host.name),
        {"label_id": str(label.id), "label_name": str(label.name)},
        "SUCCESS",
    )

    return EntityLabelResult(
        success=True,
        entity_type="host",
        entity_id=str(host.id),
        entity_name=str(host.name),
        label_id=str(label.id),
        label_name=str(label.name),
        action="assign",
        current_labels=current_names,
        message=f"Affinity label '{label.name}' successfully assigned to host '{host.name}'.",
    )


def ovirt_host_label_unassign(host_name_or_id: str, label_name_or_id: str) -> EntityLabelResult:
    """Unassign an Affinity Label from a hypervisor host (reversible counterpart of assign).

    Args:
        host_name_or_id: UUID or name of the hypervisor host.
        label_name_or_id: UUID or name of the affinity label to remove.

    Returns:
        EntityLabelResult detailing unassignment status and remaining labels.
    """
    require_mutation_allowed("ovirt_host_label_unassign")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    hosts_svc = sys_svc.hosts_service()
    labels_svc = sys_svc.affinity_labels_service()

    host = client.find_resource_by_id_or_name(hosts_svc, host_name_or_id, "host")
    label = _find_label_by_id_or_name(labels_svc, label_name_or_id)

    h_svc = hosts_svc.host_service(host.id)
    h_labels_svc = h_svc.affinity_labels_service()

    existing = h_labels_svc.list()
    matching = [lbl for lbl in existing if lbl.id == label.id]

    if not matching:
        current_names = [str(lbl.name or lbl.id) for lbl in existing]
        return EntityLabelResult(
            success=True,
            entity_type="host",
            entity_id=str(host.id),
            entity_name=str(host.name),
            label_id=str(label.id),
            label_name=str(label.name),
            action="unassign",
            current_labels=current_names,
            message=f"Host '{host.name}' does not have affinity label '{label.name}'. No action taken.",
        )

    h_labels_svc.label_service(label.id).remove()
    current_names = [str(lbl.name or lbl.id) for lbl in h_labels_svc.list()]

    audit_log(
        "ovirt_host_label_unassign",
        str(host.name),
        {"label_id": str(label.id), "label_name": str(label.name)},
        "SUCCESS",
    )

    return EntityLabelResult(
        success=True,
        entity_type="host",
        entity_id=str(host.id),
        entity_name=str(host.name),
        label_id=str(label.id),
        label_name=str(label.name),
        action="unassign",
        current_labels=current_names,
        message=f"Affinity label '{label.name}' removed from host '{host.name}'.",
    )


# =========================================================================
# 3. VM Affinity Labels
# =========================================================================


def ovirt_vm_label_list(vm_name_or_id: str) -> list[str]:
    """List all Affinity Labels currently assigned to a virtual machine.

    Args:
        vm_name_or_id: UUID or name of the virtual machine.

    Returns:
        List of affinity label names attached to the VM.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    vms_svc = sys_svc.vms_service()

    vm = client.find_resource_by_id_or_name(vms_svc, vm_name_or_id, "vm")
    v_svc = vms_svc.vm_service(vm.id)
    labels = v_svc.affinity_labels_service().list()

    return [str(lbl.name or lbl.id) for lbl in labels]


def ovirt_vm_label_assign(vm_name_or_id: str, label_name_or_id: str) -> EntityLabelResult:
    """Assign an Affinity Label to a virtual machine.

    Args:
        vm_name_or_id: UUID or name of the virtual machine.
        label_name_or_id: UUID or name of the affinity label to assign.

    Returns:
        EntityLabelResult detailing assignment status and current labels.
    """
    require_mutation_allowed("ovirt_vm_label_assign")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    vms_svc = sys_svc.vms_service()
    labels_svc = sys_svc.affinity_labels_service()

    vm = client.find_resource_by_id_or_name(vms_svc, vm_name_or_id, "vm")
    label = _find_label_by_id_or_name(labels_svc, label_name_or_id)

    v_svc = vms_svc.vm_service(vm.id)
    v_labels_svc = v_svc.affinity_labels_service()

    # Check if already assigned
    existing = v_labels_svc.list()
    if any(lbl.id == label.id for lbl in existing):
        current_names = [str(lbl.name or lbl.id) for lbl in existing]
        return EntityLabelResult(
            success=True,
            entity_type="vm",
            entity_id=str(vm.id),
            entity_name=str(vm.name),
            label_id=str(label.id),
            label_name=str(label.name),
            action="assign",
            current_labels=current_names,
            message=f"VM '{vm.name}' already has affinity label '{label.name}'.",
        )

    v_labels_svc.add(sdk_types.AffinityLabel(id=label.id))
    current_names = [str(lbl.name or lbl.id) for lbl in v_labels_svc.list()]

    audit_log(
        "ovirt_vm_label_assign",
        str(vm.name),
        {"label_id": str(label.id), "label_name": str(label.name)},
        "SUCCESS",
    )

    return EntityLabelResult(
        success=True,
        entity_type="vm",
        entity_id=str(vm.id),
        entity_name=str(vm.name),
        label_id=str(label.id),
        label_name=str(label.name),
        action="assign",
        current_labels=current_names,
        message=f"Affinity label '{label.name}' successfully assigned to VM '{vm.name}'.",
    )


def ovirt_vm_label_unassign(vm_name_or_id: str, label_name_or_id: str) -> EntityLabelResult:
    """Unassign an Affinity Label from a virtual machine (reversible counterpart of assign).

    Args:
        vm_name_or_id: UUID or name of the virtual machine.
        label_name_or_id: UUID or name of the affinity label to remove.

    Returns:
        EntityLabelResult detailing unassignment status and remaining labels.
    """
    require_mutation_allowed("ovirt_vm_label_unassign")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    vms_svc = sys_svc.vms_service()
    labels_svc = sys_svc.affinity_labels_service()

    vm = client.find_resource_by_id_or_name(vms_svc, vm_name_or_id, "vm")
    label = _find_label_by_id_or_name(labels_svc, label_name_or_id)

    v_svc = vms_svc.vm_service(vm.id)
    v_labels_svc = v_svc.affinity_labels_service()

    existing = v_labels_svc.list()
    matching = [lbl for lbl in existing if lbl.id == label.id]

    if not matching:
        current_names = [str(lbl.name or lbl.id) for lbl in existing]
        return EntityLabelResult(
            success=True,
            entity_type="vm",
            entity_id=str(vm.id),
            entity_name=str(vm.name),
            label_id=str(label.id),
            label_name=str(label.name),
            action="unassign",
            current_labels=current_names,
            message=f"VM '{vm.name}' does not have affinity label '{label.name}'. No action taken.",
        )

    v_labels_svc.label_service(label.id).remove()
    current_names = [str(lbl.name or lbl.id) for lbl in v_labels_svc.list()]

    audit_log(
        "ovirt_vm_label_unassign",
        str(vm.name),
        {"label_id": str(label.id), "label_name": str(label.name)},
        "SUCCESS",
    )

    return EntityLabelResult(
        success=True,
        entity_type="vm",
        entity_id=str(vm.id),
        entity_name=str(vm.name),
        label_id=str(label.id),
        label_name=str(label.name),
        action="unassign",
        current_labels=current_names,
        message=f"Affinity label '{label.name}' removed from VM '{vm.name}'.",
    )


# =========================================================================
# 4. Cluster Affinity Groups
# =========================================================================


def ovirt_cluster_affinity_group_list(cluster_name_or_id: str) -> list[AffinityGroupInfo]:
    """List all Affinity Groups defined within a cluster.

    Args:
        cluster_name_or_id: UUID or name of the cluster.

    Returns:
        List of AffinityGroupInfo objects describing rules, member VMs, and member Hosts.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    clusters_svc = sys_svc.clusters_service()

    cluster = client.find_resource_by_id_or_name(clusters_svc, cluster_name_or_id, "cluster")
    c_svc = clusters_svc.cluster_service(cluster.id)
    ag_svc = c_svc.affinity_groups_service()

    host_map = {str(h.id): str(h.name) for h in sys_svc.hosts_service().list()}
    vm_map = {str(v.id): str(v.name) for v in sys_svc.vms_service().list()}

    groups = ag_svc.list()
    result: list[AffinityGroupInfo] = []

    for ag in groups:
        info = _build_affinity_group_info(
            ag_svc,
            ag,
            str(cluster.id),
            str(cluster.name),
            host_map,
            vm_map,
        )
        result.append(info)

    return result


def ovirt_cluster_affinity_group_get(
    cluster_name_or_id: str,
    group_name_or_id: str,
) -> AffinityGroupInfo:
    """Get detailed configuration and members of a specific Affinity Group in a cluster.

    Args:
        cluster_name_or_id: UUID or name of the cluster.
        group_name_or_id: UUID or name of the affinity group.

    Returns:
        AffinityGroupInfo object.
    """
    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    clusters_svc = sys_svc.clusters_service()

    cluster = client.find_resource_by_id_or_name(clusters_svc, cluster_name_or_id, "cluster")
    c_svc = clusters_svc.cluster_service(cluster.id)
    ag_svc = c_svc.affinity_groups_service()

    ag = _find_affinity_group_by_id_or_name(ag_svc, group_name_or_id)

    host_map = {str(h.id): str(h.name) for h in sys_svc.hosts_service().list()}
    vm_map = {str(v.id): str(v.name) for v in sys_svc.vms_service().list()}

    return _build_affinity_group_info(
        ag_svc,
        ag,
        str(cluster.id),
        str(cluster.name),
        host_map,
        vm_map,
    )


def ovirt_cluster_affinity_group_create(
    cluster_name_or_id: str,
    name: str,
    description: str | None = None,
    priority: float | None = None,
    vm_positive: bool = True,
    vm_enforcing: bool = False,
    vm_enabled: bool = True,
    host_positive: bool = True,
    host_enforcing: bool = False,
    host_enabled: bool = True,
    vms: list[str] | None = None,
    hosts: list[str] | None = None,
    vm_labels: list[str] | None = None,
    host_labels: list[str] | None = None,
) -> AffinityGroupResult:
    """Create a new Affinity Group in a cluster.

    Args:
        cluster_name_or_id: UUID or name of the cluster.
        name: Name of the affinity group.
        description: Optional description.
        priority: Priority value for scheduling (1-5 or float).
        vm_positive: Positive VM affinity (run together) if True, negative (anti-affinity) if False.
        vm_enforcing: Mandatory enforcement if True, soft preference if False.
        vm_enabled: Whether the VM rule is enabled.
        host_positive: Positive Host affinity (run on these hosts) if True, negative (forbidden) if False.
        host_enforcing: Mandatory host enforcement if True, soft preference if False.
        host_enabled: Whether the Host rule is enabled.
        vms: Optional list of VM names or UUIDs to include in this group.
        hosts: Optional list of Host names or UUIDs to include in this group.
        vm_labels: Optional list of VM affinity label names or UUIDs.
        host_labels: Optional list of Host affinity label names or UUIDs.

    Returns:
        AffinityGroupResult with status and created group UUID.
    """
    require_mutation_allowed("ovirt_cluster_affinity_group_create")

    name_clean = name.strip()
    if not name_clean:
        raise OvirtValidationError("Affinity group name must not be empty.")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    clusters_svc = sys_svc.clusters_service()

    cluster = client.find_resource_by_id_or_name(clusters_svc, cluster_name_or_id, "cluster")
    c_svc = clusters_svc.cluster_service(cluster.id)
    ag_svc = c_svc.affinity_groups_service()

    # Pre-check existence in cluster
    for existing in ag_svc.list():
        if existing.name == name_clean:
            raise OvirtValidationError(
                f"Affinity group '{name_clean}' already exists in cluster '{cluster.name}'.",
                details={"group_name": name_clean, "group_id": str(existing.id)},
            )

    # Resolve member VMs
    sdk_vms: list[sdk_types.Vm] = []
    if vms:
        vms_svc = sys_svc.vms_service()
        for vm_id_or_name in vms:
            target_vm = client.find_resource_by_id_or_name(vms_svc, vm_id_or_name, "vm")
            sdk_vms.append(sdk_types.Vm(id=target_vm.id))

    # Resolve member Hosts
    sdk_hosts: list[sdk_types.Host] = []
    if hosts:
        hosts_svc = sys_svc.hosts_service()
        for host_id_or_name in hosts:
            target_host = client.find_resource_by_id_or_name(hosts_svc, host_id_or_name, "host")
            sdk_hosts.append(sdk_types.Host(id=target_host.id))

    # Resolve member Labels
    sdk_vm_labels: list[sdk_types.AffinityLabel] = []
    labels_svc = sys_svc.affinity_labels_service()
    if vm_labels:
        for lbl_id_or_name in vm_labels:
            target_lbl = _find_label_by_id_or_name(labels_svc, lbl_id_or_name)
            sdk_vm_labels.append(sdk_types.AffinityLabel(id=target_lbl.id))

    sdk_host_labels: list[sdk_types.AffinityLabel] = []
    if host_labels:
        for lbl_id_or_name in host_labels:
            target_lbl = _find_label_by_id_or_name(labels_svc, lbl_id_or_name)
            sdk_host_labels.append(sdk_types.AffinityLabel(id=target_lbl.id))

    # Construct AffinityGroup SDK specification
    vms_rule = sdk_types.AffinityRule(
        enabled=vm_enabled,
        positive=vm_positive,
        enforcing=vm_enforcing,
    )
    hosts_rule = sdk_types.AffinityRule(
        enabled=host_enabled,
        positive=host_positive,
        enforcing=host_enforcing,
    )

    new_ag = sdk_types.AffinityGroup(
        name=name_clean,
        description=description,
        priority=priority,
        vms_rule=vms_rule,
        hosts_rule=hosts_rule,
        vms=sdk_vms if sdk_vms else None,
        hosts=sdk_hosts if sdk_hosts else None,
        vm_labels=sdk_vm_labels if sdk_vm_labels else None,
        host_labels=sdk_host_labels if sdk_host_labels else None,
    )

    created = ag_svc.add(new_ag)
    audit_log(
        "ovirt_cluster_affinity_group_create",
        name_clean,
        {
            "cluster_id": str(cluster.id),
            "group_id": str(created.id),
            "vm_positive": vm_positive,
            "host_positive": host_positive,
        },
        "SUCCESS",
    )

    return AffinityGroupResult(
        success=True,
        group_id=str(created.id),
        group_name=str(created.name),
        cluster_id=str(cluster.id),
        cluster_name=str(cluster.name),
        action="create",
        message=(
            f"Affinity group '{created.name}' created successfully in cluster '{cluster.name}' "
            f"(UUID: {created.id})."
        ),
    )


def ovirt_cluster_affinity_group_update(
    cluster_name_or_id: str,
    group_name_or_id: str,
    name: str | None = None,
    description: str | None = None,
    priority: float | None = None,
    vm_positive: bool | None = None,
    vm_enforcing: bool | None = None,
    vm_enabled: bool | None = None,
    host_positive: bool | None = None,
    host_enforcing: bool | None = None,
    host_enabled: bool | None = None,
    vms: list[str] | None = None,
    hosts: list[str] | None = None,
    vm_labels: list[str] | None = None,
    host_labels: list[str] | None = None,
) -> AffinityGroupResult:
    """Update settings, rules, or members of an existing Affinity Group.

    Args:
        cluster_name_or_id: UUID or name of the cluster.
        group_name_or_id: UUID or name of the affinity group.
        name: New name for the affinity group.
        description: New description.
        priority: New priority value.
        vm_positive: New positive VM affinity setting.
        vm_enforcing: New VM enforcing setting.
        vm_enabled: New VM enabled setting.
        host_positive: New positive Host affinity setting.
        host_enforcing: New Host enforcing setting.
        host_enabled: New Host enabled setting.
        vms: New complete list of member VMs (replaces current list if provided).
        hosts: New complete list of member Hosts (replaces current list if provided).
        vm_labels: New complete list of member VM labels.
        host_labels: New complete list of member Host labels.

    Returns:
        AffinityGroupResult with update status.
    """
    require_mutation_allowed("ovirt_cluster_affinity_group_update")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    clusters_svc = sys_svc.clusters_service()

    cluster = client.find_resource_by_id_or_name(clusters_svc, cluster_name_or_id, "cluster")
    c_svc = clusters_svc.cluster_service(cluster.id)
    ag_svc = c_svc.affinity_groups_service()

    ag = _find_affinity_group_by_id_or_name(ag_svc, group_name_or_id)
    ag_detail = ag_svc.group_service(ag.id).get()

    update_kwargs: dict[str, Any] = {}

    if name is not None:
        name_clean = name.strip()
        if not name_clean:
            raise OvirtValidationError("Affinity group name cannot be empty.")
        update_kwargs["name"] = name_clean

    if description is not None:
        update_kwargs["description"] = description

    if priority is not None:
        update_kwargs["priority"] = priority

    # Handle vms_rule updates
    existing_vms_rule = getattr(ag_detail, "vms_rule", None)
    if any(x is not None for x in (vm_positive, vm_enforcing, vm_enabled)):
        cur_enabled = (
            bool(existing_vms_rule.enabled)
            if existing_vms_rule and hasattr(existing_vms_rule, "enabled")
            else True
        )
        cur_pos = (
            bool(existing_vms_rule.positive)
            if existing_vms_rule and hasattr(existing_vms_rule, "positive")
            else True
        )
        cur_enf = (
            bool(existing_vms_rule.enforcing)
            if existing_vms_rule and hasattr(existing_vms_rule, "enforcing")
            else False
        )

        update_kwargs["vms_rule"] = sdk_types.AffinityRule(
            enabled=vm_enabled if vm_enabled is not None else cur_enabled,
            positive=vm_positive if vm_positive is not None else cur_pos,
            enforcing=vm_enforcing if vm_enforcing is not None else cur_enf,
        )

    # Handle hosts_rule updates
    existing_hosts_rule = getattr(ag_detail, "hosts_rule", None)
    if any(x is not None for x in (host_positive, host_enforcing, host_enabled)):
        cur_h_enabled = (
            bool(existing_hosts_rule.enabled)
            if existing_hosts_rule and hasattr(existing_hosts_rule, "enabled")
            else True
        )
        cur_h_pos = (
            bool(existing_hosts_rule.positive)
            if existing_hosts_rule and hasattr(existing_hosts_rule, "positive")
            else True
        )
        cur_h_enf = (
            bool(existing_hosts_rule.enforcing)
            if existing_hosts_rule and hasattr(existing_hosts_rule, "enforcing")
            else False
        )

        update_kwargs["hosts_rule"] = sdk_types.AffinityRule(
            enabled=host_enabled if host_enabled is not None else cur_h_enabled,
            positive=host_positive if host_positive is not None else cur_h_pos,
            enforcing=host_enforcing if host_enforcing is not None else cur_h_enf,
        )

    # Resolve member VMs if specified
    if vms is not None:
        vms_svc = sys_svc.vms_service()
        sdk_vms: list[sdk_types.Vm] = []
        for vm_id_or_name in vms:
            target_vm = client.find_resource_by_id_or_name(vms_svc, vm_id_or_name, "vm")
            sdk_vms.append(sdk_types.Vm(id=target_vm.id))
        update_kwargs["vms"] = sdk_vms

    # Resolve member Hosts if specified
    if hosts is not None:
        hosts_svc = sys_svc.hosts_service()
        sdk_hosts: list[sdk_types.Host] = []
        for host_id_or_name in hosts:
            target_host = client.find_resource_by_id_or_name(hosts_svc, host_id_or_name, "host")
            sdk_hosts.append(sdk_types.Host(id=target_host.id))
        update_kwargs["hosts"] = sdk_hosts

    # Resolve member Labels if specified
    labels_svc = sys_svc.affinity_labels_service()
    if vm_labels is not None:
        sdk_vm_labels: list[sdk_types.AffinityLabel] = []
        for lbl_id_or_name in vm_labels:
            target_lbl = _find_label_by_id_or_name(labels_svc, lbl_id_or_name)
            sdk_vm_labels.append(sdk_types.AffinityLabel(id=target_lbl.id))
        update_kwargs["vm_labels"] = sdk_vm_labels

    if host_labels is not None:
        sdk_host_labels: list[sdk_types.AffinityLabel] = []
        for lbl_id_or_name in host_labels:
            target_lbl = _find_label_by_id_or_name(labels_svc, lbl_id_or_name)
            sdk_host_labels.append(sdk_types.AffinityLabel(id=target_lbl.id))
        update_kwargs["host_labels"] = sdk_host_labels

    ag_svc.group_service(ag.id).update(sdk_types.AffinityGroup(**update_kwargs))

    audit_log(
        "ovirt_cluster_affinity_group_update",
        str(ag.name),
        {
            "group_id": str(ag.id),
            "cluster_id": str(cluster.id),
            "updated_fields": list(update_kwargs.keys()),
        },
        "SUCCESS",
    )

    return AffinityGroupResult(
        success=True,
        group_id=str(ag.id),
        group_name=str(name or ag.name),
        cluster_id=str(cluster.id),
        cluster_name=str(cluster.name),
        action="update",
        message=f"Affinity group '{name or ag.name}' updated successfully in cluster '{cluster.name}'.",
    )


def ovirt_cluster_affinity_group_delete(
    cluster_name_or_id: str,
    group_name_or_id: str,
    confirm: bool = False,
) -> AffinityGroupResult:
    """Delete an Affinity Group from a cluster.

    Args:
        cluster_name_or_id: UUID or name of the cluster.
        group_name_or_id: UUID or name of the affinity group to delete.
        confirm: Confirmation flag required in safe-mode.

    Returns:
        AffinityGroupResult with deletion status.
    """
    require_destructive_confirmation("ovirt_cluster_affinity_group_delete", confirm)

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    clusters_svc = sys_svc.clusters_service()

    cluster = client.find_resource_by_id_or_name(clusters_svc, cluster_name_or_id, "cluster")
    c_svc = clusters_svc.cluster_service(cluster.id)
    ag_svc = c_svc.affinity_groups_service()

    ag = _find_affinity_group_by_id_or_name(ag_svc, group_name_or_id)

    ag_svc.group_service(ag.id).remove()

    audit_log(
        "ovirt_cluster_affinity_group_delete",
        str(ag.name),
        {"group_id": str(ag.id), "cluster_id": str(cluster.id)},
        "SUCCESS",
    )

    return AffinityGroupResult(
        success=True,
        group_id=str(ag.id),
        group_name=str(ag.name),
        cluster_id=str(cluster.id),
        cluster_name=str(cluster.name),
        action="delete",
        message=f"Affinity group '{ag.name}' deleted successfully from cluster '{cluster.name}'.",
    )
