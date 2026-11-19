"""Model Context Protocol (MCP) Server entrypoint for oVirt / OLVM."""

import logging
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

from ovirt_mcp.client import get_client
from ovirt_mcp.config import get_config
from ovirt_mcp.models.affinity import (
    AffinityGroupInfo,
    AffinityGroupResult,
    AffinityLabelInfo,
    AffinityLabelResult,
    EntityLabelResult,
)
from ovirt_mcp.models.compute import (
    VmConsoleTicket,
    VmGraphicsConsoleInfo,
    VmUpdateResult,
)
from ovirt_mcp.models.datacenter import (
    DataCenterDetail,
    DataCenterSummary,
)
from ovirt_mcp.models.disk import (
    DiskCreateResult,
    DiskDetail,
    DiskOperationResult,
    DiskResizeResult,
    VmDiskAttachmentInfo,
    VmDiskAttachmentResult,
)
from ovirt_mcp.models.event import VmEvent
from ovirt_mcp.models.host import (
    HostDetail,
    HostDeviceInfo,
    HostEvent,
    HostLifecycleResult,
    HostNicInfo,
    HostNumaNodeInfo,
    HostStats,
    HostSummary,
    HostUpgradeCheckResult,
    HostUpgradeResult,
)
from ovirt_mcp.models.host_network import (
    HostBondResult,
    HostIscsiDiscoverResult,
    HostIscsiLoginResult,
    HostNetworkAttachmentInfo,
    HostNetworkSetupResult,
)
from ovirt_mcp.models.logical_network import (
    LogicalNetworkResult,
    LogicalNetworkSummary,
)
from ovirt_mcp.models.media import (
    IsoFileInfo,
    VmCdromInfo,
    VmCdromResult,
)
from ovirt_mcp.models.network import (
    VmNicDetail,
    VmNicResult,
    VnicProfileInfo,
)
from ovirt_mcp.models.quota import (
    QuotaDetail,
    QuotaResult,
    QuotaSummary,
)
from ovirt_mcp.models.storage import (
    StorageDomainDetail,
    StorageDomainResult,
    StorageDomainSummary,
)
from ovirt_mcp.models.tag import (
    TagAssignmentResult,
    TagResult,
    TagSummary,
)
from ovirt_mcp.models.template import (
    TemplateDetail,
    TemplateResult,
    TemplateSummary,
)
from ovirt_mcp.models.vm import (
    VmCompactDetail,
    VmCreateResult,
    VmDeleteResult,
    VmDetail,
    VmLifecycleResult,
    VmMigrateResult,
    VmPinResult,
    VmSnapshotInfo,
    VmSnapshotResult,
    VmSummary,
)
from ovirt_mcp.tools.affinity import (
    ovirt_affinity_label_create as create_affinity_label_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_affinity_label_delete as delete_affinity_label_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_affinity_label_list as list_affinity_labels_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_cluster_affinity_group_create as create_cluster_affinity_group_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_cluster_affinity_group_delete as delete_cluster_affinity_group_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_cluster_affinity_group_get as get_cluster_affinity_group_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_cluster_affinity_group_list as list_cluster_affinity_groups_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_cluster_affinity_group_update as update_cluster_affinity_group_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_host_label_assign as assign_host_label_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_host_label_list as list_host_labels_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_host_label_unassign as unassign_host_label_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_vm_label_assign as assign_vm_label_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_vm_label_list as list_vm_labels_tool,
)
from ovirt_mcp.tools.affinity import (
    ovirt_vm_label_unassign as unassign_vm_label_tool,
)
from ovirt_mcp.tools.compute import (
    get_vm_console_ticket_tool,
    list_vm_graphics_consoles_tool,
    update_vm_tool,
)
from ovirt_mcp.tools.datacenters import (
    get_datacenter_tool,
    list_datacenters_tool,
)
from ovirt_mcp.tools.disks import (
    attach_disk_tool,
    attach_vm_disk_tool,
    copy_disk_tool,
    create_disk_tool,
    create_vm_disk_tool,
    detach_disk_tool,
    detach_vm_disk_tool,
    list_disks_tool,
    list_vm_disks_tool,
    move_disk_tool,
    resize_disk_tool,
    sparsify_disk_tool,
)
from ovirt_mcp.tools.events import list_vm_events_tool
from ovirt_mcp.tools.host_bonding import (
    create_host_bond_tool,
    delete_host_bond_tool,
)
from ovirt_mcp.tools.hosts import (
    activate_host_tool,
    get_host_stats_tool,
    get_host_tool,
    list_host_devices_tool,
    list_host_events_tool,
    list_host_nics_tool,
    list_host_numa_tool,
    list_host_storage_tool,
    list_hosts_tool,
    maintenance_host_tool,
    restart_host_tool,
    upgrade_check_host_tool,
    upgrade_host_tool,
)
from ovirt_mcp.tools.hosts_network import (
    ovirt_host_iscsi_discover as discover_host_iscsi_tool,
)
from ovirt_mcp.tools.hosts_network import (
    ovirt_host_iscsi_login as login_host_iscsi_tool,
)
from ovirt_mcp.tools.hosts_network import (
    ovirt_host_network_attachment_list as list_host_network_attachments_tool,
)
from ovirt_mcp.tools.hosts_network import (
    ovirt_host_network_sync as sync_host_network_tool,
)
from ovirt_mcp.tools.logical_networks import (
    create_logical_network_tool,
    delete_logical_network_tool,
    list_logical_networks_tool,
)
from ovirt_mcp.tools.media import (
    attach_vm_iso_tool,
    eject_vm_iso_tool,
    list_storage_isos_tool,
    list_vm_cdroms_tool,
)
from ovirt_mcp.tools.networks import (
    add_vm_nic_tool,
    list_vm_nics_tool,
    list_vnic_profiles_tool,
    remove_vm_nic_tool,
)
from ovirt_mcp.tools.quotas import (
    create_quota_tool,
    delete_quota_tool,
    get_quota_tool,
    list_quotas_tool,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_activate as activate_storage_domain_tool,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_attach as attach_storage_domain_tool,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_create_nfs as create_nfs_storage_domain_tool,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_delete as delete_storage_domain_tool,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_detach as detach_storage_domain_tool,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_get as get_storage_domain_tool,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_list as list_storage_domains_tool,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_maintenance as maintenance_storage_domain_tool,
)
from ovirt_mcp.tools.tags import (
    assign_host_tag_tool,
    assign_user_tag_tool,
    assign_vm_tag_tool,
    create_tag_tool,
    delete_tag_tool,
    list_tags_tool,
    list_user_tags_tool,
    unassign_host_tag_tool,
    unassign_user_tag_tool,
    unassign_vm_tag_tool,
)
from ovirt_mcp.tools.templates import (
    create_template_from_vm_tool,
    delete_template_tool,
    get_template_tool,
    list_templates_tool,
)
from ovirt_mcp.tools.vms import (
    commit_vm_snapshot_tool,
    create_vm_snapshot_tool,
    create_vm_tool,
    delete_vm_snapshot_tool,
    delete_vm_tool,
    get_vm_tool,
    list_vm_snapshots_tool,
    list_vms_tool,
    migrate_vm_tool,
    pin_vm_tool,
    preview_vm_snapshot_tool,
    reboot_vm_tool,
    restore_vm_snapshot_tool,
    start_vm_tool,
    stop_vm_tool,
    undo_vm_snapshot_tool,
    unpin_vm_tool,
)

# Configure logging
config = get_config()
logging.basicConfig(
    level=getattr(logging, config.mcp_log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("ovirt_mcp")

# Initialize MCP Server
mcp = MCPServer(
    name="ovirt-mcp",
    instructions=(
        "Enterprise MCP server for managing oVirt and Oracle Linux Virtualization Manager (OLVM) "
        "virtualization clusters, virtual machines, storage domains, and networks."
    ),
)


@mcp.tool(
    name="ovirt_test_connection",
    description="Test connection to the oVirt / OLVM Engine and retrieve product version and status.",
)
def ovirt_test_connection() -> dict[str, Any]:
    """Test connection to the oVirt / OLVM Engine and return health/status info."""
    client = get_client()
    try:
        return client.test_connection()
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
        }


@mcp.tool(
    name="ovirt_vm_list",
    description="List virtual machines with optional filtering by cluster, status, or search query.",
)
def ovirt_vm_list(
    cluster: str | None = None,
    status: str | None = None,
    search_query: str | None = None,
    max_results: int = 100,
) -> list[VmSummary]:
    """List virtual machines in oVirt / OLVM with power status, resources, and IP addresses."""
    return list_vms_tool(
        cluster=cluster,
        status=status,
        search_query=search_query,
        max_results=max_results,
    )


@mcp.tool(
    name="ovirt_vm_get",
    description=(
        "Get details of a virtual machine by name or UUID. "
        "Set compact=True for a lightweight summary (saves ~75% tokens for smaller LLMs like Llama/Mistral). "
        "Set compact=False for complete engineering details (CPU topology, memory policy, I/O threads, affinity, disks, NICs)."
    ),
)
def ovirt_vm_get(name_or_id: str, compact: bool | None = None) -> VmDetail | VmCompactDetail:
    """Retrieve detailed configuration and status of a single virtual machine."""
    return get_vm_tool(name_or_id, compact=compact)


@mcp.tool(
    name="ovirt_vm_events",
    description="Retrieve audit history, shutdown causes, error messages, and operational events for a specific virtual machine.",
)
def ovirt_vm_events(
    name_or_id: str,
    max_events: int = 25,
    severity: str | None = None,
) -> list[VmEvent]:
    """Retrieve audit history and operational events for a virtual machine."""
    return list_vm_events_tool(
        name_or_id=name_or_id,
        max_events=max_events,
        severity=severity,
    )


@mcp.tool(
    name="ovirt_vm_start",
    description="Start / power-on a virtual machine by name or UUID. Set wait=True to block until UP state.",
)
def ovirt_vm_start(
    name_or_id: str,
    pause: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
) -> VmLifecycleResult:
    """Power on a virtual machine."""
    return start_vm_tool(
        name_or_id=name_or_id,
        pause=pause,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_stop",
    description=(
        "Stop or shut down a virtual machine. "
        "graceful=True (DEFAULT): Initiates a clean, orderly operating system shutdown inside the guest via guest tools (vtools / QEMU guest agent) and ACPI, allowing services to terminate cleanly and flush filesystem buffers. "
        "graceful=False: Immediate hard power-off (force kill, pulling the virtual plug). "
        "In Safe Mode (default), confirm=True is required. "
        "Set wait=True to block until DOWN state."
    ),
)
def ovirt_vm_stop(
    name_or_id: str,
    graceful: bool = True,
    force: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
) -> VmLifecycleResult:
    """Shut down or power off a virtual machine."""
    return stop_vm_tool(
        name_or_id=name_or_id,
        graceful=graceful,
        force=force,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_shutdown",
    description=(
        "Initiate a clean, graceful operating system shutdown of a virtual machine via guest tools (vtools / QEMU guest agent) and ACPI. "
        "This is the recommended, safest way to shut down running VMs. "
        "In Safe Mode (default), confirm=True is required. "
        "Set wait=True to block until DOWN state."
    ),
)
def ovirt_vm_shutdown(
    name_or_id: str,
    force: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
) -> VmLifecycleResult:
    """Initiate a clean, graceful shutdown of a VM via guest agent/tools."""
    return stop_vm_tool(
        name_or_id=name_or_id,
        graceful=True,
        force=force,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_reboot",
    description=(
        "Reboot a running virtual machine. In Safe Mode (default), confirm=True is required. "
        "Set wait=True to block until VM completes restart and returns to UP state."
    ),
)
def ovirt_vm_reboot(
    name_or_id: str,
    force: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
) -> VmLifecycleResult:
    """Reboot a virtual machine."""
    return reboot_vm_tool(
        name_or_id=name_or_id,
        force=force,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_create",
    description=(
        "Create a new virtual machine in oVirt / OLVM. "
        "Allows provisioning from Blank or custom template, configuring vCPUs, RAM, primary disk, and vNIC profile."
    ),
)
def ovirt_vm_create(
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
    """Create a new virtual machine."""
    return create_vm_tool(
        name=name,
        cluster=cluster,
        template=template,
        memory_mb=memory_mb,
        cpu_cores=cpu_cores,
        cpu_sockets=cpu_sockets,
        description=description,
        os_type=os_type,
        disk_size_gb=disk_size_gb,
        storage_domain=storage_domain,
        network_profile=network_profile,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_delete",
    description=(
        "Permanently delete a virtual machine in oVirt / OLVM. "
        "Safe Mode (default) requires confirm=True. "
        "Set detach_only=True to keep disks; set force=True to force stop if running."
    ),
)
def ovirt_vm_delete(
    name_or_id: str,
    detach_only: bool = False,
    force: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
) -> VmDeleteResult:
    """Delete a virtual machine."""
    return delete_vm_tool(
        name_or_id=name_or_id,
        detach_only=detach_only,
        force=force,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_migrate",
    description=(
        "Live-migrate a running virtual machine to another hypervisor host with zero downtime. "
        "target_host is optional; if omitted, the engine automatically selects the optimal cluster host."
    ),
)
def ovirt_vm_migrate(
    name_or_id: str,
    target_host: str | None = None,
    force: bool = False,
    wait: bool = False,
    timeout_seconds: int = 120,
) -> VmMigrateResult:
    """Migrate a running VM to another physical host."""
    return migrate_vm_tool(
        name_or_id=name_or_id,
        target_host=target_host,
        force=force,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_pin",
    description=(
        "Pin a virtual machine to run exclusively on a specific hypervisor host. "
        "Disables automatic migration and restricts execution to the designated host."
    ),
)
def ovirt_vm_pin(name_or_id: str, host: str) -> VmPinResult:
    """Pin a VM to a designated hypervisor host."""
    return pin_vm_tool(name_or_id=name_or_id, host=host)


@mcp.tool(
    name="ovirt_vm_unpin",
    description=(
        "Unpin a previously pinned virtual machine, restoring normal dynamic live migration "
        "and load-balancing across all hosts in the cluster."
    ),
)
def ovirt_vm_unpin(name_or_id: str) -> VmPinResult:
    """Unpin a VM, restoring cluster-wide migratability."""
    return unpin_vm_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_vm_snapshot_list",
    description=(
        "List all snapshots of a virtual machine, including snapshot ID, description, "
        "status (ok, locked, in_preview), type, creation timestamp, and memory state."
    ),
)
def ovirt_vm_snapshot_list(name_or_id: str) -> list[VmSnapshotInfo]:
    """List snapshots for a virtual machine."""
    return list_vm_snapshots_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_vm_snapshot_create",
    description=(
        "Create a point-in-time snapshot of a virtual machine. "
        "Supports live snapshots for running VMs as well as offline snapshots. "
        "Optionally persist memory state (persist_memory=True, pauses execution while dumping RAM). "
        "Set wait=True to block synchronously until the snapshot is unlocked and ready."
    ),
)
def ovirt_vm_snapshot_create(
    name_or_id: str,
    description: str,
    persist_memory: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Create a point-in-time snapshot of a VM."""
    return create_vm_snapshot_tool(
        name_or_id=name_or_id,
        description=description,
        persist_memory=persist_memory,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_snapshot_restore",
    description=(
        "Restore / revert a virtual machine to a specified snapshot state. "
        "Requires VM to be in DOWN status before reverting. "
        "Optionally restore saved guest RAM memory state (restore_memory=True, requires persist_memory=True when created). "
        "Destructive action: requires confirm=True when MCP_SAFE_MODE=true."
    ),
)
def ovirt_vm_snapshot_restore(
    name_or_id: str,
    snapshot_id: str,
    restore_memory: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Restore a VM to a specified snapshot."""
    return restore_vm_snapshot_tool(
        name_or_id=name_or_id,
        snapshot_id=snapshot_id,
        restore_memory=restore_memory,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_snapshot_preview",
    description=(
        "Preview a snapshot without permanently committing changes (non-destructive inspection). "
        "Switches the VM to run on top of the snapshot's state. "
        "Can be safely reverted using ovirt_vm_snapshot_undo, or made permanent using ovirt_vm_snapshot_commit. "
        "If restore_memory=True, restores the VM's saved RAM memory state online. "
        "Destructive action in Safe Mode: requires confirm=True."
    ),
)
def ovirt_vm_snapshot_preview(
    name_or_id: str,
    snapshot_id: str,
    restore_memory: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Preview a snapshot on a virtual machine."""
    return preview_vm_snapshot_tool(
        name_or_id=name_or_id,
        snapshot_id=snapshot_id,
        restore_memory=restore_memory,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_snapshot_commit",
    description=(
        "Permanently commit the active snapshot preview, making it the permanent operational state of the VM. "
        "Destructive action in Safe Mode: requires confirm=True."
    ),
)
def ovirt_vm_snapshot_commit(
    name_or_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Commit the active snapshot preview."""
    return commit_vm_snapshot_tool(
        name_or_id=name_or_id,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_snapshot_undo",
    description=(
        "Undo the active snapshot preview and restore the VM to its exact state before preview was initiated. "
        "Reversible counterpart to ovirt_vm_snapshot_preview! "
        "Destructive action in Safe Mode: requires confirm=True."
    ),
)
def ovirt_vm_snapshot_undo(
    name_or_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Undo the active snapshot preview."""
    return undo_vm_snapshot_tool(
        name_or_id=name_or_id,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_snapshot_delete",
    description=(
        "Delete a snapshot and consolidate delta disks back into the parent disk image. "
        "Destructive action: requires confirm=True when MCP_SAFE_MODE=true. "
        "Set wait=True to block until snapshot removal and disk consolidation completes."
    ),
)
def ovirt_vm_snapshot_delete(
    name_or_id: str,
    snapshot_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> VmSnapshotResult:
    """Delete a snapshot and consolidate disk deltas."""
    return delete_vm_snapshot_tool(
        name_or_id=name_or_id,
        snapshot_id=snapshot_id,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_cdrom_list",
    description=(
        "List virtual CD-ROM drives and mounted ISO media for a virtual machine. "
        "Returns CD-ROM device UUIDs, attached ISO file names, and empty state."
    ),
)
def ovirt_vm_cdrom_list(name_or_id: str) -> list[VmCdromInfo]:
    """List virtual CD-ROM drives and mounted media for a VM."""
    return list_vm_cdroms_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_vm_iso_attach",
    description=(
        "Attach / mount an ISO image into a virtual machine's CD-ROM drive. "
        "If the VM is running and current is not specified, media is automatically "
        "hot-plugged into the active guest and saved to persistent configuration."
    ),
)
def ovirt_vm_iso_attach(
    name_or_id: str,
    iso_file: str,
    cdrom_id: str | None = None,
    current: bool | None = None,
) -> VmCdromResult:
    """Attach an ISO file to a VM's CD-ROM drive."""
    return attach_vm_iso_tool(
        name_or_id=name_or_id,
        iso_file=iso_file,
        cdrom_id=cdrom_id,
        current=current,
    )


@mcp.tool(
    name="ovirt_vm_iso_eject",
    description=(
        "Eject / unmount any mounted ISO media from a virtual machine's CD-ROM drive. "
        "Reversible counterpart to ovirt_vm_iso_attach. Supports live hot-eject on running VMs."
    ),
)
def ovirt_vm_iso_eject(
    name_or_id: str,
    cdrom_id: str | None = None,
    current: bool | None = None,
) -> VmCdromResult:
    """Eject ISO media from a VM's CD-ROM drive."""
    return eject_vm_iso_tool(
        name_or_id=name_or_id,
        cdrom_id=cdrom_id,
        current=current,
    )


@mcp.tool(
    name="ovirt_storage_iso_list",
    description=(
        "List available ISO image files across all ISO storage domains or in a designated domain. "
        "Allows operators and agents to discover available OS installation ISOs."
    ),
)
def ovirt_storage_iso_list(
    storage_domain: str | None = None,
) -> list[IsoFileInfo]:
    """List available ISO image files in ISO storage domains."""
    return list_storage_isos_tool(storage_domain=storage_domain)


@mcp.tool(
    name="ovirt_disk_list",
    description=(
        "List virtual disks in the virtualization environment. Supports filtering by storage domain, "
        "search query, or listing disks attached to a specific virtual machine (via vm_name_or_id)."
    ),
)
def ovirt_disk_list(
    storage_domain: str | None = None,
    search: str | None = None,
    vm_name_or_id: str | None = None,
) -> list[DiskDetail]:
    """List virtual disks in the oVirt / OLVM environment."""
    return list_disks_tool(
        storage_domain=storage_domain,
        search=search,
        vm_name_or_id=vm_name_or_id,
    )


@mcp.tool(
    name="ovirt_vm_disk_list",
    description=(
        "List all virtual disks attached to a virtual machine with attachment metadata "
        "(attachment ID, interface, bootable, active, read-only status). Alias to ovirt_disk_list."
    ),
)
def ovirt_vm_disk_list(name_or_id: str) -> list[VmDiskAttachmentInfo]:
    """List disks attached to a virtual machine."""
    return list_vm_disks_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_disk_attach",
    description=(
        "Attach an existing floating virtual disk to a virtual machine. "
        "Allows attaching with interface ('virtio', 'virtio_scsi', 'sata', 'ide'), "
        "bootable flag, active status, and read-only mode."
    ),
)
def ovirt_disk_attach(
    name_or_id: str,
    disk_id: str,
    interface: str = "virtio",
    bootable: bool = False,
    active: bool = True,
    read_only: bool = False,
) -> VmDiskAttachmentResult:
    """Attach an existing disk to a virtual machine."""
    return attach_disk_tool(
        name_or_id=name_or_id,
        disk_id=disk_id,
        interface=interface,
        bootable=bootable,
        active=active,
        read_only=read_only,
    )


@mcp.tool(
    name="ovirt_vm_disk_attach",
    description="Attach an existing floating virtual disk to a virtual machine (alias to ovirt_disk_attach).",
)
def ovirt_vm_disk_attach(
    name_or_id: str,
    disk_id: str,
    interface: str = "virtio",
    bootable: bool = False,
    active: bool = True,
    read_only: bool = False,
) -> VmDiskAttachmentResult:
    """Attach an existing disk to a virtual machine."""
    return attach_vm_disk_tool(
        name_or_id=name_or_id,
        disk_id=disk_id,
        interface=interface,
        bootable=bootable,
        active=active,
        read_only=read_only,
    )


@mcp.tool(
    name="ovirt_disk_detach",
    description=(
        "Detach a virtual disk from a virtual machine without deleting the underlying disk image. "
        "Reversible counterpart to ovirt_disk_attach. "
        "Destructive action in Safe Mode: requires confirm=True when MCP_SAFE_MODE=true."
    ),
)
def ovirt_disk_detach(
    name_or_id: str,
    disk_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
) -> VmDiskAttachmentResult:
    """Detach a virtual disk from a virtual machine."""
    return detach_disk_tool(
        name_or_id=name_or_id,
        disk_id=disk_id,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_disk_detach",
    description="Detach a virtual disk from a virtual machine (alias to ovirt_disk_detach).",
)
def ovirt_vm_disk_detach(
    name_or_id: str,
    disk_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
) -> VmDiskAttachmentResult:
    """Detach a virtual disk from a virtual machine."""
    return detach_vm_disk_tool(
        name_or_id=name_or_id,
        disk_id=disk_id,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_disk_create",
    description=(
        "Create a new virtual disk. If vm_name_or_id is provided, attaches the disk to that VM; "
        "if omitted, creates a floating virtual disk on the specified storage domain. "
        "Supports size in GB, storage domain, disk format ('cow' or 'raw'), and VM interface options."
    ),
)
def ovirt_disk_create(
    size_gb: int,
    storage_domain: str,
    disk_name: str | None = None,
    disk_format: str = "cow",
    vm_name_or_id: str | None = None,
    interface: str = "virtio",
    bootable: bool = False,
    active: bool = True,
    wait: bool = False,
    timeout_seconds: int = 120,
) -> DiskCreateResult | VmDiskAttachmentResult:
    """Create a virtual disk (floating or attached to a virtual machine)."""
    return create_disk_tool(
        size_gb=size_gb,
        storage_domain=storage_domain,
        disk_name=disk_name,
        disk_format=disk_format,
        vm_name_or_id=vm_name_or_id,
        interface=interface,
        bootable=bootable,
        active=active,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_vm_disk_create",
    description="Create a new virtual disk and attach it directly to a virtual machine (alias to ovirt_disk_create).",
)
def ovirt_vm_disk_create(
    name_or_id: str,
    size_gb: int,
    storage_domain: str,
    disk_name: str | None = None,
    disk_format: str = "cow",
    interface: str = "virtio",
    bootable: bool = False,
    active: bool = True,
    wait: bool = False,
    timeout_seconds: int = 120,
) -> VmDiskAttachmentResult:
    """Create a new disk and attach it to a virtual machine."""
    return create_vm_disk_tool(
        name_or_id=name_or_id,
        size_gb=size_gb,
        storage_domain=storage_domain,
        disk_name=disk_name,
        disk_format=disk_format,
        interface=interface,
        bootable=bootable,
        active=active,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_disk_resize",
    description=(
        "Expand the provisioned capacity of a virtual disk to a larger size in gigabytes. "
        "Note: Virtual disks can only be expanded; shrinking is not supported to protect data integrity. "
        "Destructive/modifying action in Safe Mode: requires confirm=True when MCP_SAFE_MODE=true."
    ),
)
def ovirt_disk_resize(
    disk_id: str,
    size_gb: int,
    confirm: bool = False,
) -> DiskResizeResult:
    """Expand the provisioned capacity of a virtual disk."""
    return resize_disk_tool(
        disk_id=disk_id,
        size_gb=size_gb,
        confirm=confirm,
    )


@mcp.tool(
    name="ovirt_disk_move",
    description=(
        "Move a virtual disk to a different Storage Domain (Storage vMotion / offline disk migration). "
        "Safely migrates the underlying disk image between active storage domains. "
        "Set wait=True to block until migration completes."
    ),
)
def ovirt_disk_move(
    disk_name_or_id: str,
    storage_domain_name_or_id: str,
    wait: bool = True,
    timeout: int = 300,
) -> DiskOperationResult:
    """Move a virtual disk to a different Storage Domain."""
    return move_disk_tool(
        disk_name_or_id=disk_name_or_id,
        storage_domain_name_or_id=storage_domain_name_or_id,
        wait=wait,
        timeout=timeout,
    )


@mcp.tool(
    name="ovirt_disk_copy",
    description=(
        "Clone / copy a virtual disk to a target Storage Domain. "
        "Allows creating an independent copy with an optional new disk alias. "
        "Set wait=True to block until the copy operation finishes."
    ),
)
def ovirt_disk_copy(
    disk_name_or_id: str,
    storage_domain_name_or_id: str,
    new_alias: str | None = None,
    wait: bool = True,
    timeout: int = 300,
) -> DiskOperationResult:
    """Clone a virtual disk to a target Storage Domain."""
    return copy_disk_tool(
        disk_name_or_id=disk_name_or_id,
        storage_domain_name_or_id=storage_domain_name_or_id,
        new_alias=new_alias,
        wait=wait,
        timeout=timeout,
    )


@mcp.tool(
    name="ovirt_disk_sparsify",
    description=(
        "Reclaim zeroed free space from a thin-provisioned (COW) virtual disk (fstrim / sparsification). "
        "Compacts the disk image on the underlying storage domain. "
        "Set wait=True to wait for sparsification to complete."
    ),
)
def ovirt_disk_sparsify(
    disk_name_or_id: str,
    wait: bool = True,
    timeout: int = 300,
) -> DiskOperationResult:
    """Reclaim zeroed space from a thin-provisioned virtual disk."""
    return sparsify_disk_tool(
        disk_name_or_id=disk_name_or_id,
        wait=wait,
        timeout=timeout,
    )


@mcp.tool(
    name="ovirt_vm_nic_list",
    description=(
        "List all virtual network interface cards (vNICs) attached to a virtual machine, "
        "including interface name, device UUID, assigned MAC address, interface model (virtio, e1000), "
        "plugged state, linked state, and associated vNIC profile."
    ),
)
def ovirt_vm_nic_list(name_or_id: str) -> list[VmNicDetail]:
    """List virtual network interface cards (vNICs) for a virtual machine."""
    return list_vm_nics_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_vm_nic_add",
    description=(
        "Add a new virtual network interface card (vNIC) to a virtual machine. "
        "Requires specifying an interface name (e.g. 'nic1') and a valid vNIC profile (e.g. 'ovirtmgmt')."
    ),
)
def ovirt_vm_nic_add(
    name_or_id: str,
    name: str,
    profile: str,
    interface: str = "virtio",
    plugged: bool = True,
    linked: bool = True,
) -> VmNicResult:
    """Add a new vNIC to a virtual machine."""
    return add_vm_nic_tool(
        name_or_id=name_or_id,
        name=name,
        profile=profile,
        interface=interface,
        plugged=plugged,
        linked=linked,
    )


@mcp.tool(
    name="ovirt_vm_nic_remove",
    description=(
        "Remove a virtual network interface card (vNIC) from a virtual machine. "
        "Reversible counterpart to ovirt_vm_nic_add. "
        "Destructive action in Safe Mode: requires confirm=True when MCP_SAFE_MODE=true."
    ),
)
def ovirt_vm_nic_remove(
    name_or_id: str,
    nic_name_or_id: str,
    confirm: bool = False,
) -> VmNicResult:
    """Remove a vNIC from a virtual machine."""
    return remove_vm_nic_tool(
        name_or_id=name_or_id,
        nic_name_or_id=nic_name_or_id,
        confirm=confirm,
    )


@mcp.tool(
    name="ovirt_network_profile_list",
    description=(
        "List available virtual network interface profiles (vNIC profiles) across logical networks, "
        "including profile IDs, names, parent network names, and passthrough flags."
    ),
)
def ovirt_network_profile_list(
    network: str | None = None,
) -> list[VnicProfileInfo]:
    """List available vNIC profiles in the oVirt / OLVM environment."""
    return list_vnic_profiles_tool(network=network)


@mcp.tool(
    name="ovirt_vm_update",
    description=(
        "Update compute hardware resources (RAM memory in MB, CPU cores/sockets/threads), "
        "description, or High Availability (HA) failover state for a virtual machine. "
        "Modifying CPU or RAM is Safe-Mode guarded and requires confirm=True when MCP_SAFE_MODE=true."
    ),
)
def ovirt_vm_update(
    name_or_id: str,
    memory_mb: int | None = None,
    cpu_cores: int | None = None,
    cpu_sockets: int | None = None,
    cpu_threads: int | None = None,
    description: str | None = None,
    ha_enabled: bool | None = None,
    confirm: bool = False,
) -> VmUpdateResult:
    """Update virtual machine resources or configuration."""
    return update_vm_tool(
        name_or_id=name_or_id,
        memory_mb=memory_mb,
        cpu_cores=cpu_cores,
        cpu_sockets=cpu_sockets,
        cpu_threads=cpu_threads,
        description=description,
        ha_enabled=ha_enabled,
        confirm=confirm,
    )


@mcp.tool(
    name="ovirt_vm_graphics_consoles",
    description=(
        "List available graphical display consoles (VNC / SPICE) configured for a virtual machine, "
        "including console UUID, protocol ('vnc' or 'spice'), and display ports."
    ),
)
def ovirt_vm_graphics_consoles(
    name_or_id: str,
) -> list[VmGraphicsConsoleInfo]:
    """List graphical consoles for a virtual machine."""
    return list_vm_graphics_consoles_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_vm_ticket",
    description=(
        "Generate a temporary single-use authentication password/ticket to connect to a running "
        "virtual machine's graphical console (VNC / SPICE). VM must be powered on (status='up')."
    ),
)
def ovirt_vm_ticket(
    name_or_id: str,
    expiry_seconds: int = 120,
) -> VmConsoleTicket:
    """Generate a graphical console access ticket."""
    return get_vm_console_ticket_tool(
        name_or_id=name_or_id,
        expiry_seconds=expiry_seconds,
    )


# ── HYPERVISOR HOST TOOLS ─────────────────────────────────────────────────────


@mcp.tool(
    name="ovirt_host_list",
    description=(
        "List all hypervisor hosts in the virtualization environment, including status, "
        "cluster assignment, IP address, CPU topology, memory in GB, active VMs count, "
        "SPM role status, and nested virtualization detection."
    ),
)
def ovirt_host_list(
    cluster: str | None = None,
    status: str | None = None,
) -> list[HostSummary]:
    """List hypervisor hosts in the cluster/environment."""
    return list_hosts_tool(cluster=cluster, status=status)


@mcp.tool(
    name="ovirt_host_get",
    description=(
        "Retrieve comprehensive hardware, BIOS, OS, kernel, VDSM/libvirt versions, "
        "power management (fencing) configuration, and device counts for a hypervisor host."
    ),
)
def ovirt_host_get(name_or_id: str) -> HostDetail:
    """Retrieve full configuration and state of a single hypervisor host."""
    return get_host_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_host_stats",
    description=(
        "Retrieve real-time performance metrics and telemetry statistics for a hypervisor host, "
        "including CPU usage %, user/system/idle breakdown, 5-minute load average, RAM total/used/free/%, "
        "swap space, active VM count, and host boot time."
    ),
)
def ovirt_host_stats(name_or_id: str) -> HostStats:
    """Retrieve real-time telemetry statistics for a hypervisor host."""
    return get_host_stats_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_host_maintenance",
    description=(
        "Put a hypervisor host into maintenance mode (deactivate). "
        "Initiates orderly live migration of running virtual machines to other cluster nodes. "
        "Enterprise Pre-condition Guards: detects pinned non-migratable VMs and blocks unless stop_pinned_vms=True, "
        "and handles SPM role migration. "
        "Reversible counterpart: ovirt_host_activate. "
        "In Safe Mode (default), confirm=True is required. Set wait=True to block until maintenance mode is achieved."
    ),
)
def ovirt_host_maintenance(
    name_or_id: str,
    stop_pinned_vms: bool = False,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 300,
) -> HostLifecycleResult:
    """Place a hypervisor host into maintenance mode."""
    return maintenance_host_tool(
        name_or_id=name_or_id,
        stop_pinned_vms=stop_pinned_vms,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_host_activate",
    description=(
        "Activate a hypervisor host from maintenance mode back to active 'up' status. "
        "Reversible counterpart to ovirt_host_maintenance! "
        "Set wait=True to block until host status reaches 'up'."
    ),
)
def ovirt_host_activate(
    name_or_id: str,
    wait: bool = False,
    timeout_seconds: int = 180,
) -> HostLifecycleResult:
    """Activate a hypervisor host back to active 'up' status."""
    return activate_host_tool(
        name_or_id=name_or_id,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_host_restart",
    description=(
        "Restart / reboot a hypervisor host via out-of-band power management fencing. "
        "Strict Enterprise Safety Guards: "
        "1. Host MUST be in 'maintenance' status. Reboot is strictly rejected if host is 'up' or 'preparing_for_maintenance'. "
        "2. Running VMs count MUST be exactly 0 (no running workloads). "
        "3. Verifies that power management (fencing/IPMI) is enabled; in nested virtualization or labs without IPMI, "
        "reports diagnostic error. "
        "Destructive action: requires confirm=True in Safe Mode."
    ),
)
def ovirt_host_restart(
    name_or_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 300,
) -> HostLifecycleResult:
    """Restart / reboot a hypervisor host via out-of-band power management."""
    return restart_host_tool(
        name_or_id=name_or_id,
        confirm=confirm,
        wait=wait,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="ovirt_host_upgrade_check",
    description=(
        "Check if operating system or package updates are available for a hypervisor host. "
        "Triggers the engine to query host package repositories via Ansible runner and "
        "returns whether updates are available (update_available)."
    ),
)
def ovirt_host_upgrade_check(name_or_id: str) -> HostUpgradeCheckResult:
    """Check for operating system or package updates on a hypervisor host."""
    return upgrade_check_host_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_host_upgrade",
    description=(
        "Upgrade operating system packages and VDSM on a hypervisor host via Engine Ansible automation. "
        "Strict Safety Guard: The host MUST be in 'maintenance' mode before initiating an upgrade. "
        "Active VMs must be migrated away using 'ovirt_host_maintenance'. "
        "Protected action in Safe Mode: requires confirm=True when MCP_SAFE_MODE=true."
    ),
)
def ovirt_host_upgrade(
    name_or_id: str,
    reboot: bool = True,
    confirm: bool = False,
    async_: bool = True,
    timeout_minutes: int = 60,
) -> HostUpgradeResult:
    """Upgrade operating system packages and VDSM on a hypervisor host."""
    return upgrade_host_tool(
        name_or_id=name_or_id,
        reboot=reboot,
        confirm=confirm,
        async_=async_,
        timeout_minutes=timeout_minutes,
    )


@mcp.tool(
    name="ovirt_host_nic_list",
    description=(
        "List physical network interfaces (pNICs) on a hypervisor host, "
        "including interface name, MAC address, speed in Mbps, operational status, "
        "IP addresses, bridge attachments, and bonding slave memberships."
    ),
)
def ovirt_host_nic_list(name_or_id: str) -> list[HostNicInfo]:
    """List physical network interfaces on a host."""
    return list_host_nics_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_host_numa_list",
    description=(
        "List NUMA (Non-Uniform Memory Access) node topology on a hypervisor host, "
        "including node index, memory in MB, and assigned CPU core IDs."
    ),
)
def ovirt_host_numa_list(name_or_id: str) -> list[HostNumaNodeInfo]:
    """List NUMA node topology on a host."""
    return list_host_numa_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_host_device_list",
    description=(
        "List physical hardware and PCI bus devices configured on a hypervisor host "
        "(SR-IOV virtual functions, GPU passthrough devices, Fibre Channel / SAS HBAs, NICs)."
    ),
)
def ovirt_host_device_list(
    name_or_id: str,
    max_devices: int = 50,
) -> list[HostDeviceInfo]:
    """List PCI and hardware devices on a host."""
    return list_host_devices_tool(
        name_or_id=name_or_id,
        max_devices=max_devices,
    )


@mcp.tool(
    name="ovirt_host_storage_list",
    description=(
        "List storage domains and block/SAN storage server connections visible to a hypervisor host."
    ),
)
def ovirt_host_storage_list(name_or_id: str) -> list[dict[str, Any]]:
    """List storage connections accessible to a host."""
    return list_host_storage_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_host_events",
    description=(
        "Retrieve audit history, hardware alerts, SPM role transitions, and operational events "
        "for a specific hypervisor host."
    ),
)
def ovirt_host_events(
    name_or_id: str,
    max_events: int = 25,
    severity: str | None = None,
) -> list[HostEvent]:
    """Retrieve audit events for a hypervisor host."""
    return list_host_events_tool(
        name_or_id=name_or_id,
        max_events=max_events,
        severity=severity,
    )


# =========================================================================
# Affinity Labels & Cluster Affinity Groups Tools
# =========================================================================


@mcp.tool(
    name="ovirt_affinity_label_list",
    description=(
        "List all global Affinity Labels in oVirt/OLVM along with their assigned "
        "hypervisor hosts and virtual machines."
    ),
)
def ovirt_affinity_label_list() -> list[AffinityLabelInfo]:
    """List all global Affinity Labels."""
    return list_affinity_labels_tool()


@mcp.tool(
    name="ovirt_affinity_label_create",
    description="Create a new global Affinity Label in oVirt/OLVM.",
)
def ovirt_affinity_label_create(name: str) -> AffinityLabelResult:
    """Create a new global Affinity Label."""
    return create_affinity_label_tool(name=name)


@mcp.tool(
    name="ovirt_affinity_label_delete",
    description=(
        "Delete an Affinity Label. Protected by safe-mode confirm flag. "
        "Optionally set detach_first=True to automatically unassign the label from all "
        "hosts and VMs before deleting."
    ),
)
def ovirt_affinity_label_delete(
    name_or_id: str,
    confirm: bool = False,
    detach_first: bool = False,
) -> AffinityLabelResult:
    """Delete an Affinity Label."""
    return delete_affinity_label_tool(
        name_or_id=name_or_id,
        confirm=confirm,
        detach_first=detach_first,
    )


@mcp.tool(
    name="ovirt_host_label_list",
    description="List all Affinity Labels currently assigned to a hypervisor host.",
)
def ovirt_host_label_list(host_name_or_id: str) -> list[str]:
    """List Affinity Labels on a host."""
    return list_host_labels_tool(host_name_or_id=host_name_or_id)


@mcp.tool(
    name="ovirt_host_label_assign",
    description="Assign an Affinity Label to a hypervisor host.",
)
def ovirt_host_label_assign(
    host_name_or_id: str,
    label_name_or_id: str,
) -> EntityLabelResult:
    """Assign an Affinity Label to a host."""
    return assign_host_label_tool(
        host_name_or_id=host_name_or_id,
        label_name_or_id=label_name_or_id,
    )


@mcp.tool(
    name="ovirt_host_label_unassign",
    description=(
        "Unassign an Affinity Label from a hypervisor host "
        "(symmetric reversible counterpart of ovirt_host_label_assign)."
    ),
)
def ovirt_host_label_unassign(
    host_name_or_id: str,
    label_name_or_id: str,
) -> EntityLabelResult:
    """Unassign an Affinity Label from a host."""
    return unassign_host_label_tool(
        host_name_or_id=host_name_or_id,
        label_name_or_id=label_name_or_id,
    )


@mcp.tool(
    name="ovirt_vm_label_list",
    description="List all Affinity Labels currently assigned to a virtual machine.",
)
def ovirt_vm_label_list(vm_name_or_id: str) -> list[str]:
    """List Affinity Labels on a VM."""
    return list_vm_labels_tool(vm_name_or_id=vm_name_or_id)


@mcp.tool(
    name="ovirt_vm_label_assign",
    description="Assign an Affinity Label to a virtual machine.",
)
def ovirt_vm_label_assign(
    vm_name_or_id: str,
    label_name_or_id: str,
) -> EntityLabelResult:
    """Assign an Affinity Label to a VM."""
    return assign_vm_label_tool(
        vm_name_or_id=vm_name_or_id,
        label_name_or_id=label_name_or_id,
    )


@mcp.tool(
    name="ovirt_vm_label_unassign",
    description=(
        "Unassign an Affinity Label from a virtual machine "
        "(symmetric reversible counterpart of ovirt_vm_label_assign)."
    ),
)
def ovirt_vm_label_unassign(
    vm_name_or_id: str,
    label_name_or_id: str,
) -> EntityLabelResult:
    """Unassign an Affinity Label from a VM."""
    return unassign_vm_label_tool(
        vm_name_or_id=vm_name_or_id,
        label_name_or_id=label_name_or_id,
    )


@mcp.tool(
    name="ovirt_cluster_affinity_group_list",
    description=(
        "List all Affinity Groups defined within a cluster, including their rules, "
        "member VMs, member Hosts, and label associations."
    ),
)
def ovirt_cluster_affinity_group_list(
    cluster_name_or_id: str,
) -> list[AffinityGroupInfo]:
    """List all Affinity Groups in a cluster."""
    return list_cluster_affinity_groups_tool(cluster_name_or_id=cluster_name_or_id)


@mcp.tool(
    name="ovirt_cluster_affinity_group_get",
    description=(
        "Get detailed configuration and members of a specific Affinity Group in a cluster."
    ),
)
def ovirt_cluster_affinity_group_get(
    cluster_name_or_id: str,
    group_name_or_id: str,
) -> AffinityGroupInfo:
    """Get Affinity Group details."""
    return get_cluster_affinity_group_tool(
        cluster_name_or_id=cluster_name_or_id,
        group_name_or_id=group_name_or_id,
    )


@mcp.tool(
    name="ovirt_cluster_affinity_group_create",
    description=(
        "Create a new Affinity Group in a cluster. Supports VM-to-VM and VM-to-Host "
        "affinity rules (positive or anti-affinity, mandatory enforcing or soft preference) "
        "and direct membership of VMs, Hosts, or Labels."
    ),
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
    """Create a new Affinity Group in a cluster."""
    return create_cluster_affinity_group_tool(
        cluster_name_or_id=cluster_name_or_id,
        name=name,
        description=description,
        priority=priority,
        vm_positive=vm_positive,
        vm_enforcing=vm_enforcing,
        vm_enabled=vm_enabled,
        host_positive=host_positive,
        host_enforcing=host_enforcing,
        host_enabled=host_enabled,
        vms=vms,
        hosts=hosts,
        vm_labels=vm_labels,
        host_labels=host_labels,
    )


@mcp.tool(
    name="ovirt_cluster_affinity_group_update",
    description=("Update settings, rules, or members of an existing Affinity Group in a cluster."),
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
    """Update an Affinity Group in a cluster."""
    return update_cluster_affinity_group_tool(
        cluster_name_or_id=cluster_name_or_id,
        group_name_or_id=group_name_or_id,
        name=name,
        description=description,
        priority=priority,
        vm_positive=vm_positive,
        vm_enforcing=vm_enforcing,
        vm_enabled=vm_enabled,
        host_positive=host_positive,
        host_enforcing=host_enforcing,
        host_enabled=host_enabled,
        vms=vms,
        hosts=hosts,
        vm_labels=vm_labels,
        host_labels=host_labels,
    )


@mcp.tool(
    name="ovirt_cluster_affinity_group_delete",
    description=("Delete an Affinity Group from a cluster. Protected by safe-mode confirm flag."),
)
def ovirt_cluster_affinity_group_delete(
    cluster_name_or_id: str,
    group_name_or_id: str,
    confirm: bool = False,
) -> AffinityGroupResult:
    """Delete an Affinity Group from a cluster."""
    return delete_cluster_affinity_group_tool(
        cluster_name_or_id=cluster_name_or_id,
        group_name_or_id=group_name_or_id,
        confirm=confirm,
    )


# =========================================================================
# Host Network Attachments & iSCSI Discovery Tools
# =========================================================================


@mcp.tool(
    name="ovirt_host_network_attachment_list",
    description=(
        "List all logical network attachments on a hypervisor host, "
        "including network name, physical NIC/bond, in-sync status, and IPv4 configuration."
    ),
)
def ovirt_host_network_attachment_list(
    host_name_or_id: str,
) -> list[HostNetworkAttachmentInfo]:
    """List logical network attachments on a host."""
    return list_host_network_attachments_tool(host_name_or_id=host_name_or_id)


@mcp.tool(
    name="ovirt_host_iscsi_discover",
    description=("Discover available iSCSI targets on a storage portal from a hypervisor host."),
)
def ovirt_host_iscsi_discover(
    host_name_or_id: str,
    address: str,
    port: int = 3260,
    username: str | None = None,
    password: str | None = None,
) -> HostIscsiDiscoverResult:
    """Discover iSCSI targets from a host."""
    return discover_host_iscsi_tool(
        host_name_or_id=host_name_or_id,
        address=address,
        port=port,
        username=username,
        password=password,
    )


@mcp.tool(
    name="ovirt_host_iscsi_login",
    description=(
        "Log in to an iSCSI target portal from a hypervisor host, discovering LUN block devices."
    ),
)
def ovirt_host_iscsi_login(
    host_name_or_id: str,
    address: str,
    target: str,
    port: int = 3260,
    username: str | None = None,
    password: str | None = None,
) -> HostIscsiLoginResult:
    """Log in to an iSCSI target from a host."""
    return login_host_iscsi_tool(
        host_name_or_id=host_name_or_id,
        address=address,
        target=target,
        port=port,
        username=username,
        password=password,
    )


@mcp.tool(
    name="ovirt_host_network_sync",
    description=(
        "Synchronize out-of-sync network attachments on a hypervisor host "
        "with connectivity rollback protection."
    ),
)
def ovirt_host_network_sync(
    host_name_or_id: str,
    network_attachment_id: str | None = None,
) -> HostNetworkSetupResult:
    """Synchronize out-of-sync network attachments on a host."""
    return sync_host_network_tool(
        host_name_or_id=host_name_or_id,
        network_attachment_id=network_attachment_id,
    )


# =========================================================================
# Storage Domains Lifecycle Tools
# =========================================================================


@mcp.tool(
    name="ovirt_storage_domain_list",
    description=(
        "List all Storage Domains in oVirt / OLVM with capacity (available, used, committed GB), "
        "storage protocol (NFS, iSCSI, FCP), and attached Data Centers."
    ),
)
def ovirt_storage_domain_list() -> list[StorageDomainSummary]:
    """List all storage domains."""
    return list_storage_domains_tool()


@mcp.tool(
    name="ovirt_storage_domain_get",
    description=(
        "Get detailed configuration, space thresholds, and counts of stored disks, "
        "templates, and VMs for a Storage Domain."
    ),
)
def ovirt_storage_domain_get(name_or_id: str) -> StorageDomainDetail:
    """Get storage domain details."""
    return get_storage_domain_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_storage_domain_create_nfs",
    description=(
        "Create a new NFS Storage Domain in oVirt / OLVM initialized via a designated hypervisor host."
    ),
)
def ovirt_storage_domain_create_nfs(
    name: str,
    host_name_or_id: str,
    address: str,
    path: str,
    domain_type: str = "data",
    nfs_version: str = "auto",
    description: str | None = None,
) -> StorageDomainResult:
    """Create a new NFS Storage Domain."""
    return create_nfs_storage_domain_tool(
        name=name,
        host_name_or_id=host_name_or_id,
        address=address,
        path=path,
        domain_type=domain_type,
        nfs_version=nfs_version,
        description=description,
    )


@mcp.tool(
    name="ovirt_storage_domain_attach",
    description="Attach a Storage Domain to a Data Center.",
)
def ovirt_storage_domain_attach(
    storage_domain_name_or_id: str,
    data_center_name_or_id: str,
) -> StorageDomainResult:
    """Attach a storage domain to a Data Center."""
    return attach_storage_domain_tool(
        storage_domain_name_or_id=storage_domain_name_or_id,
        data_center_name_or_id=data_center_name_or_id,
    )


@mcp.tool(
    name="ovirt_storage_domain_activate",
    description="Activate an attached Storage Domain in a Data Center.",
)
def ovirt_storage_domain_activate(
    storage_domain_name_or_id: str,
    data_center_name_or_id: str,
) -> StorageDomainResult:
    """Activate a storage domain in a Data Center."""
    return activate_storage_domain_tool(
        storage_domain_name_or_id=storage_domain_name_or_id,
        data_center_name_or_id=data_center_name_or_id,
    )


@mcp.tool(
    name="ovirt_storage_domain_maintenance",
    description="Move an attached Storage Domain to maintenance mode in a Data Center (deactivate).",
)
def ovirt_storage_domain_maintenance(
    storage_domain_name_or_id: str,
    data_center_name_or_id: str,
) -> StorageDomainResult:
    """Move a storage domain to maintenance mode."""
    return maintenance_storage_domain_tool(
        storage_domain_name_or_id=storage_domain_name_or_id,
        data_center_name_or_id=data_center_name_or_id,
    )


@mcp.tool(
    name="ovirt_storage_domain_detach",
    description=(
        "Detach a Storage Domain from a Data Center "
        "(symmetric reversible counterpart of ovirt_storage_domain_attach)."
    ),
)
def ovirt_storage_domain_detach(
    storage_domain_name_or_id: str,
    data_center_name_or_id: str,
) -> StorageDomainResult:
    """Detach a storage domain from a Data Center."""
    return detach_storage_domain_tool(
        storage_domain_name_or_id=storage_domain_name_or_id,
        data_center_name_or_id=data_center_name_or_id,
    )


@mcp.tool(
    name="ovirt_storage_domain_delete",
    description=(
        "Delete or unregister a Storage Domain from oVirt / OLVM. "
        "Protected by safe-mode confirm flag and pre-flight detachment guards."
    ),
)
def ovirt_storage_domain_delete(
    name_or_id: str,
    host_name_or_id: str | None = None,
    format: bool = False,
    confirm: bool = False,
) -> StorageDomainResult:
    """Delete a storage domain."""
    return delete_storage_domain_tool(
        name_or_id=name_or_id,
        host_name_or_id=host_name_or_id,
        format=format,
        confirm=confirm,
    )


# =========================================================================
# Templates & Golden Images Tools
# =========================================================================


@mcp.tool(
    name="ovirt_template_list",
    description=(
        "List all virtual machine templates and golden images in the virtualization environment, "
        "including system Blank template, custom images, hardware specs (vCPU, RAM), and versioning."
    ),
)
def ovirt_template_list(search: str | None = None) -> list[TemplateSummary]:
    """List virtual machine templates and golden images."""
    return list_templates_tool(search=search)


@mcp.tool(
    name="ovirt_template_get",
    description=(
        "Retrieve deep technical configuration and hardware profile of an oVirt / OLVM template, "
        "including attached disk references, NIC count, CPU topology, memory, and OS type."
    ),
)
def ovirt_template_get(name_or_id: str) -> TemplateDetail:
    """Get detailed specification of a template."""
    return get_template_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_template_create_from_vm",
    description=(
        "Create a new reusable template / golden image from an existing virtual machine. "
        "The source virtual machine must be powered off (down) to capture disk snapshots. "
        "Set wait=True to block until template disk creation finishes."
    ),
)
def ovirt_template_create_from_vm(
    vm_name_or_id: str,
    template_name: str,
    description: str | None = None,
    wait: bool = True,
    timeout: int = 300,
) -> TemplateResult:
    """Create a new template from an existing VM."""
    return create_template_from_vm_tool(
        vm_name_or_id=vm_name_or_id,
        template_name=template_name,
        description=description,
        wait=wait,
        timeout=timeout,
    )


@mcp.tool(
    name="ovirt_template_delete",
    description=(
        "Delete an oVirt / OLVM template from the environment. "
        "Protected by safe-mode confirmation (confirm=True). "
        "The system Blank template is permanently protected from deletion."
    ),
)
def ovirt_template_delete(
    name_or_id: str,
    confirm: bool = False,
    wait: bool = True,
    timeout: int = 180,
) -> TemplateResult:
    """Delete a template from the environment."""
    return delete_template_tool(
        name_or_id=name_or_id,
        confirm=confirm,
        wait=wait,
        timeout=timeout,
    )


# =========================================================================
# Data Center, Quota & Logical Network Tools
# =========================================================================


@mcp.tool(
    name="ovirt_datacenter_list",
    description=(
        "List all Data Centers in oVirt / OLVM with status (up/uninitialized), storage type "
        "(shared/local), compatibility version, and quota mode."
    ),
)
def ovirt_datacenter_list(search: str | None = None) -> list[DataCenterSummary]:
    """List Data Centers in the virtualization environment."""
    return list_datacenters_tool(search=search)


@mcp.tool(
    name="ovirt_datacenter_get",
    description=(
        "Retrieve complete specification of a Data Center including attached clusters, "
        "attached Storage Domains, and defined logical networks."
    ),
)
def ovirt_datacenter_get(name_or_id: str) -> DataCenterDetail:
    """Get detailed specification of a Data Center."""
    return get_datacenter_tool(name_or_id=name_or_id)


@mcp.tool(
    name="ovirt_quota_list",
    description=(
        "List resource quotas defined across Data Centers or within a specific Data Center."
    ),
)
def ovirt_quota_list(data_center: str | None = None) -> list[QuotaSummary]:
    """List resource quotas."""
    return list_quotas_tool(data_center=data_center)


@mcp.tool(
    name="ovirt_quota_get",
    description=(
        "Retrieve technical limits of a quota, including cluster compute ceilings "
        "(vCPU, memory) and Storage Domain capacity limits."
    ),
)
def ovirt_quota_get(
    name_or_id: str,
    data_center: str | None = None,
) -> QuotaDetail:
    """Get detailed quota limits."""
    return get_quota_tool(name_or_id=name_or_id, data_center=data_center)


@mcp.tool(
    name="ovirt_quota_create",
    description=(
        "Create a new resource quota in a Data Center to enforce cluster compute and storage limits."
    ),
)
def ovirt_quota_create(
    name: str,
    data_center: str,
    description: str | None = None,
) -> QuotaResult:
    """Create a new quota in a Data Center."""
    return create_quota_tool(
        name=name,
        data_center=data_center,
        description=description,
    )


@mcp.tool(
    name="ovirt_quota_delete",
    description=(
        "Delete a resource quota from a Data Center. Protected by safe-mode confirmation. "
        "The system Default quota is protected from removal."
    ),
)
def ovirt_quota_delete(
    name_or_id: str,
    data_center: str,
    confirm: bool = False,
) -> QuotaResult:
    """Delete a quota from a Data Center."""
    return delete_quota_tool(
        name_or_id=name_or_id,
        data_center=data_center,
        confirm=confirm,
    )


@mcp.tool(
    name="ovirt_network_list",
    description=(
        "List logical networks across Data Centers or filtered by Data Center, "
        "including 802.1Q VLAN encapsulation tag, MTU, and status."
    ),
)
def ovirt_network_list(data_center: str | None = None) -> list[LogicalNetworkSummary]:
    """List logical networks."""
    return list_logical_networks_tool(data_center=data_center)


@mcp.tool(
    name="ovirt_network_create",
    description=(
        "Create a new logical network in a Data Center with optional VLAN tagging and custom MTU."
    ),
)
def ovirt_network_create(
    name: str,
    data_center: str,
    vlan_id: int | None = None,
    mtu: int | None = None,
    description: str | None = None,
) -> LogicalNetworkResult:
    """Create a new logical network."""
    return create_logical_network_tool(
        name=name,
        data_center=data_center,
        vlan_id=vlan_id,
        mtu=mtu,
        description=description,
    )


@mcp.tool(
    name="ovirt_network_delete",
    description=(
        "Delete a logical network from a Data Center. Protected by safe-mode confirmation. "
        "The management network 'ovirtmgmt' is protected from deletion."
    ),
)
def ovirt_network_delete(
    name_or_id: str,
    data_center: str | None = None,
    confirm: bool = False,
) -> LogicalNetworkResult:
    """Delete a logical network."""
    return delete_logical_network_tool(
        name_or_id=name_or_id,
        data_center=data_center,
        confirm=confirm,
    )


# =========================================================================
# Inventory Tags Tools
# =========================================================================


@mcp.tool(
    name="ovirt_tag_list",
    description="List hierarchical inventory tags in the oVirt / OLVM virtualization environment.",
)
def ovirt_tag_list(search: str | None = None) -> list[TagSummary]:
    """List inventory tags."""
    return list_tags_tool(search=search)


@mcp.tool(
    name="ovirt_tag_create",
    description="Create a new inventory tag in oVirt / OLVM with optional parent hierarchical nesting.",
)
def ovirt_tag_create(
    name: str,
    description: str | None = None,
    parent: str | None = None,
) -> TagResult:
    """Create a new inventory tag."""
    return create_tag_tool(
        name=name,
        description=description,
        parent=parent,
    )


@mcp.tool(
    name="ovirt_tag_delete",
    description="Delete an inventory tag from oVirt / OLVM. Protected by safe-mode confirmation. System root tag is protected.",
)
def ovirt_tag_delete(
    name_or_id: str,
    confirm: bool = False,
) -> TagResult:
    """Delete an inventory tag."""
    return delete_tag_tool(
        name_or_id=name_or_id,
        confirm=confirm,
    )


@mcp.tool(
    name="ovirt_vm_tag_assign",
    description="Assign an inventory tag to a virtual machine.",
)
def ovirt_vm_tag_assign(
    vm_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Assign an inventory tag to a VM."""
    return assign_vm_tag_tool(
        vm_name_or_id=vm_name_or_id,
        tag_name_or_id=tag_name_or_id,
    )


@mcp.tool(
    name="ovirt_vm_tag_unassign",
    description="Unassign an inventory tag from a virtual machine.",
)
def ovirt_vm_tag_unassign(
    vm_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Unassign an inventory tag from a VM."""
    return unassign_vm_tag_tool(
        vm_name_or_id=vm_name_or_id,
        tag_name_or_id=tag_name_or_id,
    )


@mcp.tool(
    name="ovirt_host_tag_assign",
    description="Assign an inventory tag to a hypervisor host.",
)
def ovirt_host_tag_assign(
    host_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Assign an inventory tag to a host."""
    return assign_host_tag_tool(
        host_name_or_id=host_name_or_id,
        tag_name_or_id=tag_name_or_id,
    )


@mcp.tool(
    name="ovirt_host_tag_unassign",
    description="Unassign an inventory tag from a hypervisor host.",
)
def ovirt_host_tag_unassign(
    host_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Unassign an inventory tag from a host."""
    return unassign_host_tag_tool(
        host_name_or_id=host_name_or_id,
        tag_name_or_id=tag_name_or_id,
    )


@mcp.tool(
    name="ovirt_user_tag_list",
    description="List inventory tags assigned to an oVirt / OLVM user.",
)
def ovirt_user_tag_list(user_name_or_id: str) -> list[TagSummary]:
    """List inventory tags assigned to a user."""
    return list_user_tags_tool(user_name_or_id=user_name_or_id)


@mcp.tool(
    name="ovirt_user_tag_assign",
    description="Assign an inventory tag to an oVirt / OLVM user.",
)
def ovirt_user_tag_assign(
    user_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Assign an inventory tag to a user."""
    return assign_user_tag_tool(
        user_name_or_id=user_name_or_id,
        tag_name_or_id=tag_name_or_id,
    )


@mcp.tool(
    name="ovirt_user_tag_unassign",
    description="Unassign an inventory tag from an oVirt / OLVM user.",
)
def ovirt_user_tag_unassign(
    user_name_or_id: str,
    tag_name_or_id: str,
) -> TagAssignmentResult:
    """Unassign an inventory tag from a user."""
    return unassign_user_tag_tool(
        user_name_or_id=user_name_or_id,
        tag_name_or_id=tag_name_or_id,
    )


# =========================================================================
# Host Network Bonding Tools
# =========================================================================


@mcp.tool(
    name="ovirt_host_bond_create",
    description=(
        "Create a bonded network interface on a hypervisor host combining 2 or more physical interfaces. "
        "Supports active-backup, 802.3ad (LACP), balance-rr, and custom bond modes."
    ),
)
def ovirt_host_bond_create(
    host_name_or_id: str,
    bond_name: str,
    slaves: list[str],
    mode: str = "active-backup",
) -> HostBondResult:
    """Create a network bond interface on a host."""
    return create_host_bond_tool(
        host_name_or_id=host_name_or_id,
        bond_name=bond_name,
        slaves=slaves,
        mode=mode,
    )


@mcp.tool(
    name="ovirt_host_bond_delete",
    description=(
        "Delete a network bond interface from a hypervisor host, releasing slave interfaces back to standalone mode. "
        "Protected by safe-mode confirmation (confirm=True)."
    ),
)
def ovirt_host_bond_delete(
    host_name_or_id: str,
    bond_name: str,
    confirm: bool = False,
) -> HostBondResult:
    """Delete a network bond interface from a host."""
    return delete_host_bond_tool(
        host_name_or_id=host_name_or_id,
        bond_name=bond_name,
        confirm=confirm,
    )


def main() -> None:
    """Run the MCP server over standard I/O (stdio) or network HTTP/SSE transport."""
    config = get_config()
    transport = config.mcp_transport.strip().lower()

    if transport in ("sse", "streamable-http"):
        logger.info(
            "Starting oVirt/OLVM MCP server in network daemon mode (transport='%s', bind='%s:%d')...",
            transport,
            config.mcp_host,
            config.mcp_port,
        )
        if transport == "streamable-http":
            mcp.run(transport="streamable-http", host=config.mcp_host, port=config.mcp_port)
        else:
            mcp.run(transport="sse", host=config.mcp_host, port=config.mcp_port)
    else:
        logger.info("Starting oVirt/OLVM MCP server in interactive stdio mode...")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
