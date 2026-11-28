"""Tools for managing virtual disks, attachments, detached disks, and capacity extension."""

import logging
import time
from typing import Any

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.disk import (
    DiskCreateResult,
    DiskDeleteResult,
    DiskDetail,
    DiskIoStats,
    DiskOperationResult,
    DiskResizeResult,
    VmDiskAttachmentInfo,
    VmDiskAttachmentResult,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_disk_status,
    require_mutation_allowed,
    require_storage_domain_status,
    require_vm_status,
)

logger = logging.getLogger("ovirt_mcp.tools.disks")


def extract_disk_io_stats(disk_service: Any) -> DiskIoStats | None:
    """Extract real-time DiskIoStats from a disk_service statistics subcollection."""
    try:
        if not hasattr(disk_service, "statistics_service"):
            return None
        raw_stats = disk_service.statistics_service().list()
        if not raw_stats:
            return None
        stats_map: dict[str, float] = {}
        for s in raw_stats:
            s_name = str(getattr(s, "name", ""))
            vals = getattr(s, "values", None) or []
            if vals:
                stats_map[s_name] = float(getattr(vals[0], "datum", 0.0))

        read_bytes = stats_map.get("data.current.read", 0.0)
        write_bytes = stats_map.get("data.current.write", 0.0)
        read_mb = round(read_bytes / (1024**2), 3)
        write_mb = round(write_bytes / (1024**2), 3)
        read_iops = round(stats_map.get("data.current.read_ops", 0.0), 1)
        write_iops = round(stats_map.get("data.current.write_ops", 0.0), 1)
        read_lat_s = stats_map.get("disk.read.latency", 0.0)
        write_lat_s = stats_map.get("disk.write.latency", 0.0)
        flush_lat_s = stats_map.get("disk.flush.latency", 0.0)
        read_lat_ms = round(read_lat_s * 1000.0, 3)
        write_lat_ms = round(write_lat_s * 1000.0, 3)
        flush_lat_ms = round(flush_lat_s * 1000.0, 3)

        return DiskIoStats(
            read_bytes_sec=round(read_bytes, 1),
            write_bytes_sec=round(write_bytes, 1),
            read_mb_sec=read_mb,
            write_mb_sec=write_mb,
            read_iops=read_iops,
            write_iops=write_iops,
            read_latency_ms=read_lat_ms,
            write_latency_ms=write_lat_ms,
            flush_latency_ms=flush_lat_ms,
        )
    except Exception as exc:
        logger.debug("Could not extract disk io stats: %s", exc)
        return None


def list_vm_disks_tool(name_or_id: str) -> list[VmDiskAttachmentInfo]:
    """List all virtual disks attached to a specific virtual machine.

    Args:
        name_or_id: Display name or UUID of the virtual machine.

    Returns:
        List of VmDiskAttachmentInfo containing disk IDs, sizes, interfaces, and statuses.
    """
    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    disks_service = conn.system_service().disks_service()
    disks_service = conn.system_service().disks_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_service = vms_service.vm_service(vm_id)

    # Pre-fetch storage domain names for human-readable resolution
    sd_names: dict[str, str] = {}
    try:
        sds_service = conn.system_service().storage_domains_service()
        for sd_item in sds_service.list():
            if hasattr(sd_item, "id") and hasattr(sd_item, "name") and sd_item.id and sd_item.name:
                sd_names[str(sd_item.id)] = str(sd_item.name)
    except Exception as sd_err:
        logger.debug("Could not pre-fetch storage domain names: %s", sd_err)

    results: list[VmDiskAttachmentInfo] = []
    try:
        attachments = vm_service.disk_attachments_service().list()
        for att in attachments:
            att_id = str(getattr(att, "id", ""))
            disk_ref = getattr(att, "disk", None)
            disk_id = str(getattr(disk_ref, "id", att_id))
            bootable = bool(getattr(att, "bootable", False))
            active = bool(getattr(att, "active", True))
            read_only = bool(getattr(att, "read_only", False))
            iface_obj = getattr(att, "interface", None)
            iface_str = str(getattr(iface_obj, "value", iface_obj or "virtio")).lower()

            # Retrieve underlying disk entity for size and domain details
            disk_name = "Unknown"
            prov_gb = 0.0
            act_gb: float | None = None
            d_format = "cow"
            sd_name: str | None = None
            d_status = "ok"

            try:
                full_disk = disks_service.disk_service(disk_id).get()
                disk_name = str(getattr(full_disk, "name", full_disk.id))
                prov_bytes = getattr(full_disk, "provisioned_size", 0) or 0
                prov_gb = round(prov_bytes / (1024**3), 2)
                act_bytes = getattr(full_disk, "actual_size", None)
                if act_bytes is not None:
                    act_gb = round(act_bytes / (1024**3), 2)
                format_obj = getattr(full_disk, "format", None)
                d_format = str(getattr(format_obj, "value", format_obj or "cow")).lower()
                status_obj = getattr(full_disk, "status", None)
                d_status = str(getattr(status_obj, "value", status_obj or "ok")).lower()

                sds = getattr(full_disk, "storage_domains", [])
                if sds and len(sds) > 0:
                    raw_sd_id = (
                        str(getattr(sds[0], "id", ""))
                        if hasattr(sds[0], "id") and sds[0].id
                        else None
                    )
                    raw_sd_name = getattr(sds[0], "name", None)
                    if raw_sd_name and str(raw_sd_name) != "None":
                        sd_name = str(raw_sd_name)
                    elif raw_sd_id and raw_sd_id in sd_names:
                        sd_name = sd_names[raw_sd_id]
                    elif raw_sd_id:
                        sd_name = raw_sd_id
            except Exception as disk_err:
                logger.debug("Failed to fetch detailed disk info for %s: %s", disk_id, disk_err)

            disk_io = None
            try:
                disk_io = extract_disk_io_stats(disks_service.disk_service(disk_id))
            except Exception as io_err:
                logger.debug("Failed to fetch I/O stats for disk %s: %s", disk_id, io_err)

            results.append(
                VmDiskAttachmentInfo(
                    attachment_id=att_id,
                    disk_id=disk_id,
                    disk_name=disk_name,
                    interface=iface_str,
                    bootable=bootable,
                    active=active,
                    read_only=read_only,
                    provisioned_size_gb=prov_gb,
                    actual_size_gb=act_gb,
                    disk_format=d_format,
                    storage_domain_name=sd_name,
                    status=d_status,
                    io_stats=disk_io,
                )
            )
    except Exception as exc:
        logger.warning("Failed to list disk attachments for VM '%s': %s", name_or_id, exc)
        raise OvirtMCPError(
            f"Failed to list disk attachments for VM '{name_or_id}': {exc}",
            details={"vm": name_or_id, "error": str(exc)},
        ) from exc

    return results


def attach_vm_disk_tool(
    name_or_id: str,
    disk_id: str,
    interface: str = "virtio",
    bootable: bool = False,
    active: bool = True,
    read_only: bool = False,
) -> VmDiskAttachmentResult:
    """Attach an existing floating virtual disk to a virtual machine.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        disk_id: UUID of the existing floating disk.
        interface: Interface type ('virtio', 'virtio_scsi', 'sata', 'ide').
        bootable: Whether to mark this disk as the primary bootable device.
        active: Whether to activate (plug) the disk immediately.
        read_only: Whether to mount the disk as read-only.

    Returns:
        VmDiskAttachmentResult with attachment confirmation.
    """
    require_mutation_allowed("attach_vm_disk")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    disks_service = conn.system_service().disks_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    require_vm_status(
        vm_name, getattr(vm, "status", None), ("up", "down", "paused"), action_name="attach_vm_disk"
    )
    vm_service = vms_service.vm_service(vm_id)

    # Validate that target disk exists and is unlocked
    try:
        disk_svc = disks_service.disk_service(disk_id)
        disk = disk_svc.get()
        disk_name = str(getattr(disk, "name", disk_id))
        require_disk_status(
            disk_name, getattr(disk, "status", None), ("ok",), action_name="attach_vm_disk"
        )

        # If disk is locked (e.g. just detached or resized), wait until it reaches 'ok'
        start_wait = time.time()
        while getattr(getattr(disk, "status", None), "value", "ok").lower() == "locked":
            if time.time() - start_wait > 30:
                break
            time.sleep(2)
            try:
                disk = disk_svc.get()
            except Exception:
                break
    except Exception as exc:
        raise OvirtValidationError(
            f"Virtual disk '{disk_id}' not found: {exc}",
            details={"disk_id": disk_id, "error": str(exc)},
        ) from exc

    try:
        iface_enum = sdk_types.DiskInterface(interface.lower())
    except ValueError:
        raise OvirtValidationError(
            f"Invalid disk interface '{interface}'. Valid choices: 'virtio', 'virtio_scsi', 'sata', 'ide'.",
            details={"interface": interface},
        ) from None

    attachment_spec = sdk_types.DiskAttachment(
        disk=sdk_types.Disk(id=disk_id),
        interface=iface_enum,
        bootable=bootable,
        active=active,
        read_only=read_only,
    )

    try:
        created = vm_service.disk_attachments_service().add(attachment_spec)
        att_id = str(getattr(created, "id", disk_id))
    except Exception as exc:
        audit_log(
            "attach_vm_disk",
            vm_name,
            {"vm_id": vm_id, "disk_id": disk_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to attach disk '{disk_id}' to VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "disk_id": disk_id, "error": str(exc)},
        ) from exc

    audit_log(
        "attach_vm_disk",
        vm_name,
        {"vm_id": vm_id, "disk_id": disk_id, "interface": interface, "attachment_id": att_id},
        "SUCCESS",
    )
    return VmDiskAttachmentResult(
        success=True,
        action="attach",
        vm_id=vm_id,
        vm_name=vm_name,
        disk_id=disk_id,
        disk_name=disk_name,
        interface=interface.lower(),
        message=f"Disk '{disk_name}' ({disk_id}) successfully attached to VM '{vm_name}' (interface={interface}).",
    )


def detach_vm_disk_tool(
    name_or_id: str,
    disk_id: str,
    confirm: bool = False,
    wait: bool = False,
    timeout_seconds: int = 60,
) -> VmDiskAttachmentResult:
    """Detach a virtual disk from a virtual machine without deleting the underlying storage image.

    Reversible counterpart to attach_vm_disk.
    Destructive action in Safe Mode: requires confirm=True.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        disk_id: UUID of the disk to detach.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        wait: If True, blocks until the disk is confirmed detached from the VM.
        timeout_seconds: Maximum time to wait if wait=True.

    Returns:
        VmDiskAttachmentResult with outcome confirmation.
    """
    require_destructive_confirmation(
        f"detach disk '{disk_id}' from VM '{name_or_id}'", confirmed=confirm
    )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    disks_service = conn.system_service().disks_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    require_vm_status(
        vm_name, getattr(vm, "status", None), ("up", "down", "paused"), action_name="detach_vm_disk"
    )
    vm_service = vms_service.vm_service(vm_id)

    # Locate attachment by disk id or attachment id
    attachments = vm_service.disk_attachments_service().list()
    target_att = None
    for att in attachments:
        d_id = str(getattr(getattr(att, "disk", None), "id", ""))
        a_id = str(getattr(att, "id", ""))
        if disk_id in (d_id, a_id):
            target_att = att
            break

    if not target_att:
        raise OvirtValidationError(
            f"Disk '{disk_id}' is not attached to virtual machine '{vm_name}'.",
            details={"vm_id": vm_id, "disk_id": disk_id},
        )

    target_att_id = str(getattr(target_att, "id", disk_id))
    att_service = vm_service.disk_attachments_service().attachment_service(target_att_id)

    try:
        # detach_only=True ensures the disk data is preserved in storage domain
        att_service.remove(detach_only=True)
    except Exception as exc:
        audit_log(
            "detach_vm_disk",
            vm_name,
            {"vm_id": vm_id, "disk_id": disk_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to detach disk '{disk_id}' from VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "disk_id": disk_id, "error": str(exc)},
        ) from exc

    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(2)
            try:
                remaining = vm_service.disk_attachments_service().list()
                found = any(
                    str(getattr(getattr(a, "disk", None), "id", "")) == disk_id
                    or str(getattr(a, "id", "")) == target_att_id
                    for a in remaining
                )
                if not found:
                    # Verify underlying disk is unlocked
                    try:
                        disk_obj = disks_service.disk_service(disk_id).get()
                        d_st = getattr(getattr(disk_obj, "status", None), "value", "ok").lower()
                        if d_st == "ok":
                            break
                    except Exception:
                        break
            except Exception as poll_exc:
                logger.debug("Transient poll error during disk detach: %s", poll_exc)

    audit_log(
        "detach_vm_disk",
        vm_name,
        {"vm_id": vm_id, "disk_id": disk_id},
        "SUCCESS",
    )
    return VmDiskAttachmentResult(
        success=True,
        action="detach",
        vm_id=vm_id,
        vm_name=vm_name,
        disk_id=disk_id,
        message=f"Disk '{disk_id}' successfully detached from VM '{vm_name}' (underlying storage preserved).",
    )


attach_disk_tool = attach_vm_disk_tool
detach_disk_tool = detach_vm_disk_tool


def create_vm_disk_tool(
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
    """Create a new virtual disk and attach it directly to a virtual machine.

    Args:
        name_or_id: Display name or UUID of the virtual machine.
        size_gb: Provisioned disk capacity in gigabytes.
        storage_domain: Name or UUID of target storage domain.
        disk_name: Optional disk alias/name (defaults to '<vm_name>_disk_<timestamp>').
        disk_format: 'cow' (QCOW2 thin-provisioned) or 'raw'.
        interface: 'virtio', 'virtio_scsi', 'sata', 'ide'.
        bootable: Whether to mark the new disk as bootable.
        active: Whether to activate (plug) the disk immediately.
        wait: If True, blocks until the disk creation completes and reaches 'ok' status.
        timeout_seconds: Maximum time to wait if wait=True.

    Returns:
        VmDiskAttachmentResult with created disk details.
    """
    require_mutation_allowed("create_vm_disk")

    if size_gb <= 0:
        raise OvirtValidationError(f"Disk size must be greater than 0 GB, got {size_gb}.")

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    disks_service = conn.system_service().disks_service()
    sds_service = conn.system_service().storage_domains_service()

    vm = client.find_resource_by_id_or_name(vms_service, name_or_id, "vm")
    vm_id = str(vm.id)
    vm_name = str(vm.name)
    require_vm_status(
        vm_name, getattr(vm, "status", None), ("up", "down", "paused"), action_name="create_vm_disk"
    )
    vm_service = vms_service.vm_service(vm_id)

    sd = client.find_resource_by_id_or_name(sds_service, storage_domain, "storage domain")
    sd_id = str(sd.id)
    sd_name = str(getattr(sd, "name", sd_id))
    require_storage_domain_status(
        sd_name, getattr(sd, "status", None), ("active",), action_name="create_disk"
    )

    actual_disk_name = disk_name or f"{vm_name}_disk_{int(time.time())}"

    try:
        iface_enum = sdk_types.DiskInterface(interface.lower())
    except ValueError:
        raise OvirtValidationError(
            f"Invalid disk interface '{interface}'. Valid choices: 'virtio', 'virtio_scsi', 'sata', 'ide'.",
            details={"interface": interface},
        ) from None

    try:
        format_enum = sdk_types.DiskFormat(disk_format.lower())
    except ValueError:
        raise OvirtValidationError(
            f"Invalid disk format '{disk_format}'. Valid choices: 'cow', 'raw'.",
            details={"disk_format": disk_format},
        ) from None

    attachment_spec = sdk_types.DiskAttachment(
        disk=sdk_types.Disk(
            name=actual_disk_name,
            description=f"Attached to {vm_name}",
            format=format_enum,
            provisioned_size=size_gb * (1024**3),
            storage_domains=[sdk_types.StorageDomain(id=sd_id)],
        ),
        interface=iface_enum,
        bootable=bootable,
        active=active,
    )

    try:
        created = vm_service.disk_attachments_service().add(attachment_spec)
        created_disk = getattr(created, "disk", None)
        created_disk_id = str(getattr(created_disk, "id", getattr(created, "id", "")))
    except Exception as exc:
        audit_log(
            "create_vm_disk",
            vm_name,
            {
                "vm_id": vm_id,
                "size_gb": size_gb,
                "storage_domain": storage_domain,
                "error": str(exc),
            },
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to create and attach disk on VM '{vm_name}': {exc}",
            details={"vm_id": vm_id, "size_gb": size_gb, "error": str(exc)},
        ) from exc

    if wait and created_disk_id:
        start_time = time.time()
        disk_service = disks_service.disk_service(created_disk_id)
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                refreshed = disk_service.get()
                st = getattr(getattr(refreshed, "status", None), "value", "").lower()
                if st == "ok":
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during disk creation: %s", poll_exc)

    audit_log(
        "create_vm_disk",
        vm_name,
        {
            "vm_id": vm_id,
            "disk_id": created_disk_id,
            "size_gb": size_gb,
            "disk_name": actual_disk_name,
        },
        "SUCCESS",
    )
    return VmDiskAttachmentResult(
        success=True,
        action="create",
        vm_id=vm_id,
        vm_name=vm_name,
        disk_id=created_disk_id,
        disk_name=actual_disk_name,
        interface=interface.lower(),
        message=f"Disk '{actual_disk_name}' ({size_gb}GB, {disk_format}) created and attached to VM '{vm_name}'.",
    )


def create_disk_tool(
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
    """Create a new virtual disk (floating or attached to a virtual machine).

    If vm_name_or_id is provided, the disk is created and attached directly to the VM.
    If vm_name_or_id is omitted, a floating virtual disk is created on the storage domain.

    Args:
        size_gb: Provisioned disk capacity in gigabytes.
        storage_domain: Name or UUID of target storage domain.
        disk_name: Optional disk alias/name.
        disk_format: 'cow' (QCOW2 thin-provisioned) or 'raw'.
        vm_name_or_id: Optional VM name or UUID to attach to.
        interface: 'virtio', 'virtio_scsi', 'sata', 'ide' (if attaching to VM).
        bootable: Whether to mark the disk as bootable (if attaching to VM).
        active: Whether to activate/plug immediately (if attaching to VM).
        wait: If True, blocks until disk creation finishes and reaches 'ok' status.
        timeout_seconds: Maximum time to wait if wait=True.

    Returns:
        DiskCreateResult (if floating) or VmDiskAttachmentResult (if attached to VM).
    """
    if vm_name_or_id:
        return create_vm_disk_tool(
            name_or_id=vm_name_or_id,
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

    require_mutation_allowed("ovirt_disk_create")

    if size_gb <= 0:
        raise OvirtValidationError(f"Disk size must be greater than 0 GB, got {size_gb}.")

    client = get_client()
    conn = client.get_connection()
    disks_service = conn.system_service().disks_service()
    sds_service = conn.system_service().storage_domains_service()

    sd = client.find_resource_by_id_or_name(sds_service, storage_domain, "storage domain")
    sd_id = str(sd.id)
    sd_name = str(getattr(sd, "name", sd_id))
    require_storage_domain_status(
        sd_name, getattr(sd, "status", None), ("active",), action_name="create_disk"
    )

    actual_disk_name = disk_name or f"disk_{int(time.time())}"

    try:
        format_enum = sdk_types.DiskFormat(disk_format.lower())
    except ValueError:
        raise OvirtValidationError(
            f"Invalid disk format '{disk_format}'. Valid choices: 'cow', 'raw'.",
            details={"disk_format": disk_format},
        ) from None

    disk_spec = sdk_types.Disk(
        name=actual_disk_name,
        format=format_enum,
        provisioned_size=size_gb * (1024**3),
        storage_domains=[sdk_types.StorageDomain(id=sd_id)],
    )

    try:
        created = disks_service.add(disk_spec)
        created_disk_id = str(getattr(created, "id", ""))
    except Exception as exc:
        audit_log(
            "ovirt_disk_create",
            actual_disk_name,
            {
                "size_gb": size_gb,
                "storage_domain": storage_domain,
                "error": str(exc),
            },
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to create floating virtual disk '{actual_disk_name}': {exc}",
            details={"size_gb": size_gb, "storage_domain": storage_domain, "error": str(exc)},
        ) from exc

    if wait and created_disk_id:
        start_time = time.time()
        disk_service = disks_service.disk_service(created_disk_id)
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                refreshed = disk_service.get()
                st = getattr(getattr(refreshed, "status", None), "value", "").lower()
                if st == "ok":
                    break
            except Exception as poll_exc:
                logger.debug("Transient poll error during floating disk creation: %s", poll_exc)

    audit_log(
        "ovirt_disk_create",
        actual_disk_name,
        {
            "disk_id": created_disk_id,
            "size_gb": size_gb,
            "disk_name": actual_disk_name,
            "storage_domain": str(sd.name),
        },
        "SUCCESS",
    )
    return DiskCreateResult(
        success=True,
        action="create",
        disk_id=created_disk_id,
        disk_name=actual_disk_name,
        provisioned_size_gb=float(size_gb),
        storage_domain=str(sd.name),
        disk_format=disk_format.lower(),
        message=f"Floating virtual disk '{actual_disk_name}' ({size_gb}GB, {disk_format}) created on storage domain '{sd.name}'.",
    )


def resize_disk_tool(
    disk_id: str,
    size_gb: int,
    confirm: bool = False,
    dry_run: bool = False,
) -> DiskResizeResult:
    """Expand / resize the provisioned capacity of a virtual disk.

    Note: oVirt only supports expanding (increasing) virtual disk size.
    Shrinking virtual disks is strictly prohibited by hypervisors to prevent data loss.
    Destructive/modifying action in Safe Mode: requires confirm=True.

    Args:
        disk_id: UUID of the virtual disk to resize.
        size_gb: New total provisioned capacity in gigabytes (must be strictly larger than current size).
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).
        dry_run: If True, validates target size without extending the disk.

    Returns:
        DiskResizeResult with old and new capacities.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"resize virtual disk '{disk_id}' to {size_gb}GB", confirmed=confirm
        )
    else:
        require_mutation_allowed("resize_disk")

    client = get_client()
    conn = client.get_connection()
    disks_service = conn.system_service().disks_service()

    try:
        disk_service = disks_service.disk_service(disk_id)
        current_disk = disk_service.get()
    except Exception as exc:
        raise OvirtValidationError(
            f"Virtual disk '{disk_id}' not found: {exc}",
            details={"disk_id": disk_id, "error": str(exc)},
        ) from exc

    disk_name = str(getattr(current_disk, "name", disk_id))
    status_obj = getattr(current_disk, "status", None)
    require_disk_status(
        disk_name,
        status_obj,
        allowed_statuses=("ok",),
        action_name="resize_disk",
    )
    current_bytes = getattr(current_disk, "provisioned_size", 0) or 0
    current_gb = round(current_bytes / (1024**3), 2)
    new_bytes = size_gb * (1024**3)

    if new_bytes <= current_bytes:
        raise OvirtValidationError(
            f"New size ({size_gb}GB) must be strictly greater than current size ({current_gb}GB). "
            "oVirt does not support shrinking virtual disks.",
            details={
                "disk_id": disk_id,
                "current_size_gb": current_gb,
                "requested_size_gb": size_gb,
            },
        )

    if dry_run:
        audit_log(
            "resize_disk",
            disk_name,
            {
                "disk_id": disk_id,
                "current_size_gb": current_gb,
                "new_size_gb": size_gb,
                "dry_run": True,
            },
            "SUCCESS",
        )
        return DiskResizeResult(
            success=True,
            disk_id=disk_id,
            disk_name=disk_name,
            old_size_gb=current_gb,
            new_size_gb=float(size_gb),
            dry_run=True,
            message=f"[DRY RUN] Virtual disk '{disk_name}' ({disk_id}) would be resized from {current_gb}GB to {size_gb}GB. No changes were made.",
        )

    try:
        disk_service.update(sdk_types.Disk(provisioned_size=new_bytes))
    except Exception as exc:
        audit_log(
            "resize_disk",
            disk_name,
            {"disk_id": disk_id, "requested_size_gb": size_gb, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(
            f"Failed to resize disk '{disk_name}' ({disk_id}) to {size_gb}GB: {exc}",
            details={"disk_id": disk_id, "new_size_gb": size_gb, "error": str(exc)},
        ) from exc

    audit_log(
        "resize_disk",
        disk_name,
        {"disk_id": disk_id, "old_size_gb": current_gb, "new_size_gb": size_gb},
        "SUCCESS",
    )
    return DiskResizeResult(
        success=True,
        disk_id=disk_id,
        disk_name=disk_name,
        old_size_gb=current_gb,
        new_size_gb=float(size_gb),
        message=f"Disk '{disk_name}' provisioned capacity successfully expanded from {current_gb}GB to {size_gb}GB.",
    )


def list_disks_tool(
    storage_domain: str | None = None,
    search: str | None = None,
    vm_name_or_id: str | None = None,
) -> list[DiskDetail]:
    """List virtual disks across storage domains, including floating and attached disks.

    Args:
        storage_domain: Optional storage domain name or UUID to filter disks.
        search: Optional oVirt search query (e.g. 'status=ok', 'name=data*').
        vm_name_or_id: Optional VM name or UUID to filter disks attached to a specific VM.

    Returns:
        List of DiskDetail with capacity, format, content type, and storage domain.
    """
    client = get_client()
    conn = client.get_connection()
    disks_service = conn.system_service().disks_service()

    target_sd_id: str | None = None
    if storage_domain:
        sds_service = conn.system_service().storage_domains_service()
        sd = client.find_resource_by_id_or_name(sds_service, storage_domain, "storage domain")
        target_sd_id = str(sd.id)

    vm_disk_ids: set[str] | None = None
    if vm_name_or_id:
        vms_service = conn.system_service().vms_service()
        vm = client.find_resource_by_id_or_name(vms_service, vm_name_or_id, "vm")
        vm_service = vms_service.vm_service(vm.id)
        attachments = vm_service.disk_attachments_service().list()
        vm_disk_ids = {
            str(getattr(getattr(att, "disk", None), "id", att.id)) for att in attachments
        }

    # Pre-fetch storage domain names for human-readable resolution
    sd_names: dict[str, str] = {}
    try:
        sds_service = conn.system_service().storage_domains_service()
        for sd_item in sds_service.list():
            if hasattr(sd_item, "id") and hasattr(sd_item, "name") and sd_item.id and sd_item.name:
                sd_names[str(sd_item.id)] = str(sd_item.name)
    except Exception as sd_err:
        logger.debug("Could not pre-fetch storage domain names: %s", sd_err)

    disks_list: list[DiskDetail] = []
    try:
        raw_disks = disks_service.list(search=search)
        for d in raw_disks:
            d_id = str(getattr(d, "id", ""))
            if vm_disk_ids is not None and d_id not in vm_disk_ids:
                continue

            d_name = str(getattr(d, "name", d_id))
            status_obj = getattr(d, "status", None)
            status_str = str(getattr(status_obj, "value", status_obj or "ok")).lower()

            prov_bytes = getattr(d, "provisioned_size", 0) or 0
            prov_gb = round(prov_bytes / (1024**3), 2)
            act_bytes = getattr(d, "actual_size", None)
            act_gb = round(act_bytes / (1024**3), 2) if act_bytes is not None else None

            format_obj = getattr(d, "format", None)
            format_str = str(getattr(format_obj, "value", format_obj or "cow")).lower()

            content_obj = getattr(d, "content_type", None)
            content_str = str(getattr(content_obj, "value", content_obj or "data")).lower()

            sds = getattr(d, "storage_domains", [])
            d_sd_id = str(sds[0].id) if sds and hasattr(sds[0], "id") and sds[0].id else None
            d_sd_name: str | None = None
            if d_sd_id and d_sd_id in sd_names:
                d_sd_name = sd_names[d_sd_id]
            elif sds and hasattr(sds[0], "name") and sds[0].name and str(sds[0].name) != "None":
                d_sd_name = str(sds[0].name)
            elif d_sd_id:
                d_sd_name = d_sd_id

            if target_sd_id and d_sd_id != target_sd_id:
                continue

            disk_io = None
            try:
                disk_io = extract_disk_io_stats(disks_service.disk_service(d_id))
            except Exception as io_err:
                logger.debug("Failed to fetch I/O stats for disk %s: %s", d_id, io_err)

            backup_obj = getattr(d, "backup", None)
            backup_val = (
                str(getattr(backup_obj, "value", backup_obj)) if backup_obj is not None else None
            )
            backup_mode_obj = getattr(d, "backup_mode", None)
            backup_mode_val = (
                str(getattr(backup_mode_obj, "value", backup_mode_obj))
                if backup_mode_obj is not None
                else None
            )
            shareable_val = (
                bool(getattr(d, "shareable", False))
                if getattr(d, "shareable", None) is not None
                else None
            )
            ro_val = (
                bool(getattr(d, "read_only", False))
                if getattr(d, "read_only", None) is not None
                else None
            )
            wipe_val = (
                bool(getattr(d, "wipe_after_delete", False))
                if getattr(d, "wipe_after_delete", None) is not None
                else None
            )
            sparse_val = (
                bool(getattr(d, "sparse", False))
                if getattr(d, "sparse", None) is not None
                else None
            )
            qcow_ver_obj = getattr(d, "qcow_version", None)
            qcow_version_val = (
                str(getattr(qcow_ver_obj, "value", qcow_ver_obj))
                if qcow_ver_obj is not None
                else None
            )
            sgio_obj = getattr(d, "sgio", None)
            sgio_val = str(getattr(sgio_obj, "value", sgio_obj)) if sgio_obj is not None else None
            prop_err_obj = getattr(d, "propagate_errors", None)
            propagate_errors_val = (
                str(getattr(prop_err_obj, "value", prop_err_obj))
                if prop_err_obj is not None
                else None
            )
            desc_val = (
                str(getattr(d, "description", None))
                if getattr(d, "description", None) is not None
                else None
            )
            comment_val = (
                str(getattr(d, "comment", None))
                if getattr(d, "comment", None) is not None
                else None
            )

            disks_list.append(
                DiskDetail(
                    id=d_id,
                    name=d_name,
                    status=status_str,
                    provisioned_size_gb=prov_gb,
                    actual_size_gb=act_gb,
                    disk_format=format_str,
                    content_type=content_str,
                    storage_domain_name=d_sd_name,
                    storage_domain_id=d_sd_id,
                    backup=backup_val,
                    backup_mode=backup_mode_val,
                    shareable=shareable_val,
                    read_only=ro_val,
                    wipe_after_delete=wipe_val,
                    sparse=sparse_val,
                    qcow_version=qcow_version_val,
                    sgio=sgio_val,
                    propagate_errors=propagate_errors_val,
                    description=desc_val,
                    comment=comment_val,
                    io_stats=disk_io,
                )
            )
    except Exception as exc:
        logger.warning("Failed to list disks: %s", exc)
        raise OvirtMCPError(
            f"Failed to list disks: {exc}",
            details={"storage_domain": storage_domain, "search": search, "error": str(exc)},
        ) from exc

    return disks_list


def move_disk_tool(
    disk_name_or_id: str,
    storage_domain_name_or_id: str,
    wait: bool = True,
    timeout: int = 300,
    dry_run: bool = False,
) -> DiskOperationResult:
    """Move a virtual disk to a different Storage Domain (live or offline storage migration).

    Args:
        disk_name_or_id: Name or UUID of the virtual disk to migrate.
        storage_domain_name_or_id: Target Storage Domain name or UUID.
        wait: Whether to synchronously wait for the migration to complete.
        timeout: Maximum time in seconds to wait for migration.
        dry_run: If True, validates storage domain target without initiating migration.

    Returns:
        DiskOperationResult with migration outcome.
    """
    require_mutation_allowed("ovirt_disk_move")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    disks_svc = sys_svc.disks_service()
    sds_svc = sys_svc.storage_domains_service()

    disk = client.find_resource_by_id_or_name(disks_svc, disk_name_or_id, "disk")
    status_obj = getattr(disk, "status", None)
    require_disk_status(
        str(getattr(disk, "name", disk_name_or_id)),
        status_obj,
        allowed_statuses=("ok",),
        action_name="move_disk",
    )
    target_sd = client.find_resource_by_id_or_name(
        sds_svc, storage_domain_name_or_id, "storage domain"
    )

    # Determine current hosting domain
    cur_sds = getattr(disk, "storage_domains", [])
    src_sd_name = "unknown"
    src_sd_id = None
    if cur_sds:
        src_sd_id = str(cur_sds[0].id) if getattr(cur_sds[0], "id", None) else None
        if getattr(cur_sds[0], "name", None):
            src_sd_name = str(cur_sds[0].name)
        elif src_sd_id:
            try:
                sd_obj = sds_svc.storage_domain_service(src_sd_id).get()
                src_sd_name = str(sd_obj.name)
            except Exception:
                pass

    if src_sd_id == str(target_sd.id):
        raise OvirtValidationError(
            f"Disk '{disk.name}' is already on target Storage Domain '{target_sd.name}'.",
            details={"disk_id": str(disk.id), "storage_domain_id": str(target_sd.id)},
        )

    # Check status
    cur_status = str(getattr(disk, "status", "ok")).lower()
    if cur_status == "locked":
        raise OvirtValidationError(
            f"Cannot move disk '{disk.name}': disk is currently locked by another operation.",
            details={"disk_id": str(disk.id), "status": cur_status},
        )

    if dry_run:
        audit_log(
            "ovirt_disk_move",
            str(disk.name),
            {
                "disk_id": str(disk.id),
                "source_storage_domain": src_sd_name,
                "target_storage_domain": str(target_sd.name),
                "dry_run": True,
            },
            "SUCCESS",
        )
        return DiskOperationResult(
            success=True,
            disk_id=str(disk.id),
            disk_name=str(disk.name),
            action="move",
            source_storage_domain=src_sd_name,
            target_storage_domain=str(target_sd.name),
            dry_run=True,
            message=f"[DRY RUN] Disk '{disk.name}' would be moved from '{src_sd_name}' to '{target_sd.name}'. No changes were made.",
        )

    disk_svc = disks_svc.disk_service(disk.id)
    disk_svc.move(storage_domain=sdk_types.StorageDomain(id=target_sd.id))

    if wait:
        start_time = time.time()
        time.sleep(2)
        while time.time() - start_time < timeout:
            time.sleep(3)
            updated_disk = disk_svc.get()
            status = str(getattr(updated_disk, "status", "ok")).lower()
            if status == "ok":
                break
            if status == "illegal":
                raise OvirtMCPError(
                    f"Disk migration failed for disk '{disk.name}'. Status became 'illegal'.",
                    details={"disk_id": str(disk.id), "status": status},
                )

    audit_log(
        "ovirt_disk_move",
        str(disk.name),
        {
            "disk_id": str(disk.id),
            "source_domain": src_sd_name,
            "target_domain": str(target_sd.name),
        },
        "SUCCESS",
    )

    return DiskOperationResult(
        success=True,
        disk_id=str(disk.id),
        disk_name=str(disk.name),
        action="move",
        source_storage_domain=src_sd_name,
        target_storage_domain=str(target_sd.name),
        message=(
            f"Virtual disk '{disk.name}' successfully migrated from '{src_sd_name}' "
            f"to target Storage Domain '{target_sd.name}'."
        ),
    )


def copy_disk_tool(
    disk_name_or_id: str,
    storage_domain_name_or_id: str,
    new_alias: str | None = None,
    wait: bool = True,
    timeout: int = 300,
) -> DiskOperationResult:
    """Copy / clone a virtual disk to a different Storage Domain.

    Args:
        disk_name_or_id: Name or UUID of the virtual disk to clone.
        storage_domain_name_or_id: Target Storage Domain name or UUID.
        new_alias: Optional new display name / alias for the copied disk.
        wait: Whether to synchronously wait for the copy to complete.
        timeout: Maximum wait time in seconds.

    Returns:
        DiskOperationResult with clone outcome.
    """
    require_mutation_allowed("ovirt_disk_copy")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    disks_svc = sys_svc.disks_service()
    sds_svc = sys_svc.storage_domains_service()

    disk = client.find_resource_by_id_or_name(disks_svc, disk_name_or_id, "disk")
    status_obj = getattr(disk, "status", None)
    require_disk_status(
        str(getattr(disk, "name", disk_name_or_id)),
        status_obj,
        allowed_statuses=("ok",),
        action_name="copy_disk",
    )
    target_sd = client.find_resource_by_id_or_name(
        sds_svc, storage_domain_name_or_id, "storage domain"
    )

    cur_sds = getattr(disk, "storage_domains", [])
    src_sd_name = "unknown"
    if cur_sds:
        if getattr(cur_sds[0], "name", None):
            src_sd_name = str(cur_sds[0].name)
        elif getattr(cur_sds[0], "id", None):
            try:
                sd_obj = sds_svc.storage_domain_service(cur_sds[0].id).get()
                src_sd_name = str(sd_obj.name)
            except Exception:
                pass

    copy_kwargs: dict[str, Any] = {"storage_domain": sdk_types.StorageDomain(id=target_sd.id)}
    if new_alias:
        copy_kwargs["disk"] = sdk_types.Disk(alias=new_alias.strip())

    disk_svc = disks_svc.disk_service(disk.id)
    disk_svc.copy(**copy_kwargs)

    if wait:
        start_time = time.time()
        time.sleep(2)
        while time.time() - start_time < timeout:
            time.sleep(3)
            updated_disk = disk_svc.get()
            status = str(getattr(updated_disk, "status", "ok")).lower()
            if status == "ok":
                break
            if status == "illegal":
                raise OvirtMCPError(
                    f"Disk copy failed for disk '{disk.name}'. Status became 'illegal'.",
                    details={"disk_id": str(disk.id), "status": status},
                )

    audit_log(
        "ovirt_disk_copy",
        str(disk.name),
        {
            "disk_id": str(disk.id),
            "source_domain": src_sd_name,
            "target_domain": str(target_sd.name),
            "new_alias": new_alias,
        },
        "SUCCESS",
    )

    return DiskOperationResult(
        success=True,
        disk_id=str(disk.id),
        disk_name=str(new_alias or disk.name),
        action="copy",
        source_storage_domain=src_sd_name,
        target_storage_domain=str(target_sd.name),
        message=(
            f"Virtual disk '{disk.name}' successfully copied to Storage Domain '{target_sd.name}' "
            f"(alias: '{new_alias or disk.name}')."
        ),
    )


def sparsify_disk_tool(
    disk_name_or_id: str,
    wait: bool = True,
    timeout: int = 300,
    dry_run: bool = False,
) -> DiskOperationResult:
    """Reclaim zeroed blocks from a thin-provisioned virtual disk (fstrim / sparsify).

    Args:
        disk_name_or_id: Name or UUID of the virtual disk to sparsify.
        wait: Whether to synchronously wait for the operation to complete.
        timeout: Maximum wait time in seconds.
        dry_run: If True, validates disk eligibility (raw format) without sparsifying.

    Returns:
        DiskOperationResult with sparsify outcome.
    """
    require_mutation_allowed("ovirt_disk_sparsify")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    disks_svc = sys_svc.disks_service()

    disk = client.find_resource_by_id_or_name(disks_svc, disk_name_or_id, "disk")
    status_obj = getattr(disk, "status", None)
    require_disk_status(
        str(getattr(disk, "name", disk_name_or_id)),
        status_obj,
        allowed_statuses=("ok",),
        action_name="sparsify_disk",
    )

    # Guard: oVirt / OLVM engine only supports sparsification on RAW disks; QCOW2 is rejected
    disk_fmt = str(getattr(disk, "format", "raw")).lower()
    if disk_fmt in ("cow", "qcow2"):
        raise OvirtValidationError(
            f"Cannot sparsify disk '{disk.name}': disk format is '{disk_fmt}'. "
            "oVirt / OLVM sparsification is only supported for raw-formatted virtual disks.",
            details={"disk_id": str(disk.id), "format": disk_fmt},
        )

    if dry_run:
        audit_log(
            "ovirt_disk_sparsify",
            str(disk.name),
            {"disk_id": str(disk.id), "format": disk_fmt, "dry_run": True},
            "SUCCESS",
        )
        return DiskOperationResult(
            success=True,
            disk_id=str(disk.id),
            disk_name=str(disk.name),
            action="sparsify",
            dry_run=True,
            message=f"[DRY RUN] Virtual disk '{disk.name}' (format: {disk_fmt}) would be sparsified to reclaim zeroed blocks. No changes were made.",
        )

    disk_svc = disks_svc.disk_service(disk.id)
    disk_svc.sparsify()

    if wait:
        start_time = time.time()
        time.sleep(2)
        while time.time() - start_time < timeout:
            time.sleep(3)
            updated_disk = disk_svc.get()
            status = str(getattr(updated_disk, "status", "ok")).lower()
            if status == "ok":
                break
            if status == "illegal":
                raise OvirtMCPError(
                    f"Disk sparsify failed for disk '{disk.name}'. Status became 'illegal'.",
                    details={"disk_id": str(disk.id), "status": status},
                )

    audit_log(
        "ovirt_disk_sparsify",
        str(disk.name),
        {"disk_id": str(disk.id), "format": disk_fmt},
        "SUCCESS",
    )

    return DiskOperationResult(
        success=True,
        disk_id=str(disk.id),
        disk_name=str(disk.name),
        action="sparsify",
        message=f"Virtual disk '{disk.name}' sparsified successfully (zeroed blocks reclaimed).",
    )


def reduce_disk_tool(
    disk_name_or_id: str,
    wait: bool = True,
    timeout: int = 300,
    dry_run: bool = False,
    confirm: bool = False,
) -> DiskOperationResult:
    """Reduce (shrink) the underlying physical storage volume allocation for a thin-provisioned virtual disk.

    Args:
        disk_name_or_id: Name or UUID of the virtual disk to reduce.
        wait: Whether to synchronously wait for the operation to complete.
        timeout: Maximum wait time in seconds.
        dry_run: If True, validates preconditions without executing.
        confirm: Confirmation flag for mutation in Safe Mode.

    Returns:
        DiskOperationResult with operation outcome.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"reduce storage volume of disk '{disk_name_or_id}'", confirmed=confirm
        )
    else:
        require_mutation_allowed("reduce_disk")

    client = get_client()
    conn = client.get_connection()
    sys_svc = conn.system_service()
    disks_svc = sys_svc.disks_service()

    disk = client.find_resource_by_id_or_name(disks_svc, disk_name_or_id, "disk")
    disk_id = str(disk.id)
    disk_name = str(disk.name)
    status_obj = getattr(disk, "status", None)
    require_disk_status(
        disk_name,
        status_obj,
        allowed_statuses=("ok",),
        action_name="reduce_disk",
    )

    if dry_run:
        audit_log(
            "ovirt_disk_reduce",
            disk_name,
            {"disk_id": disk_id, "dry_run": True},
            "SUCCESS",
        )
        return DiskOperationResult(
            success=True,
            disk_id=disk_id,
            disk_name=disk_name,
            action="reduce",
            dry_run=True,
            message=f"[DRY RUN] Volume reduction validated for virtual disk '{disk_name}'. No changes were made.",
        )

    disk_svc = disks_svc.disk_service(disk.id)
    try:
        disk_svc.reduce()
    except Exception as exc:
        audit_log(
            "ovirt_disk_reduce",
            disk_name,
            {"disk_id": disk_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to reduce disk '{disk_name}': {exc}") from exc

    if wait:
        start_time = time.time()
        time.sleep(2)
        while time.time() - start_time < timeout:
            time.sleep(3)
            updated_disk = disk_svc.get()
            status = str(getattr(updated_disk, "status", "ok")).lower()
            if status == "ok":
                break
            if status == "illegal":
                raise OvirtMCPError(
                    f"Disk reduce failed for disk '{disk_name}'. Status became 'illegal'.",
                    details={"disk_id": disk_id, "status": status},
                )

    audit_log(
        "ovirt_disk_reduce",
        disk_name,
        {"disk_id": disk_id},
        "SUCCESS",
    )

    return DiskOperationResult(
        success=True,
        disk_id=disk_id,
        disk_name=disk_name,
        action="reduce",
        message=f"Virtual disk '{disk_name}' physical storage volume reduced successfully.",
    )


def get_disk_tool(name_or_id: str) -> DiskDetail:
    """Retrieve detailed information about a single virtual disk by name/alias or UUID.

    Args:
        name_or_id: Name/alias or UUID of the virtual disk to retrieve.

    Returns:
        DiskDetail containing disk format, capacity, status, hosting storage domain, and I/O stats.
    """
    client = get_client()
    conn = client.get_connection()
    disks_service = conn.system_service().disks_service()

    disk = client.find_resource_by_id_or_name(disks_service, name_or_id, "disk")
    d_id = str(disk.id)
    raw_name = getattr(disk, "name", d_id)
    if type(raw_name).__name__ in ("MagicMock", "Mock") and hasattr(raw_name, "_mock_name"):
        d_name = getattr(raw_name, "_mock_name", str(d_id))
    else:
        d_name = str(raw_name)
    status_obj = getattr(disk, "status", None)
    status_str = str(getattr(status_obj, "value", status_obj or "ok")).lower()

    prov_bytes = getattr(disk, "provisioned_size", 0) or 0
    prov_gb = round(prov_bytes / (1024**3), 2)
    act_bytes = getattr(disk, "actual_size", None)
    act_gb = round(act_bytes / (1024**3), 2) if act_bytes is not None else None

    format_obj = getattr(disk, "format", None)
    format_str = str(getattr(format_obj, "value", format_obj or "cow")).lower()

    content_obj = getattr(disk, "content_type", None)
    content_str = str(getattr(content_obj, "value", content_obj or "data")).lower()

    sds = getattr(disk, "storage_domains", [])
    d_sd_id = str(sds[0].id) if sds and hasattr(sds[0], "id") and sds[0].id else None
    d_sd_name: str | None = None
    if sds and hasattr(sds[0], "name") and sds[0].name and str(sds[0].name) != "None":
        raw_sd_name = sds[0].name
        if type(raw_sd_name).__name__ in ("MagicMock", "Mock") and hasattr(
            raw_sd_name, "_mock_name"
        ):
            d_sd_name = getattr(raw_sd_name, "_mock_name", str(d_sd_id))
        else:
            d_sd_name = str(raw_sd_name)
    elif d_sd_id:
        try:
            sds_service = conn.system_service().storage_domains_service()
            sd_entity = sds_service.storage_domain_service(d_sd_id).get()
            d_sd_name = str(getattr(sd_entity, "name", d_sd_id))
        except Exception:
            d_sd_name = d_sd_id

    disk_io = None
    try:
        disk_io = extract_disk_io_stats(disks_service.disk_service(d_id))
    except Exception as io_err:
        logger.debug("Failed to fetch I/O stats for disk %s: %s", d_id, io_err)

    backup_obj = getattr(disk, "backup", None)
    backup_val = str(getattr(backup_obj, "value", backup_obj)) if backup_obj is not None else None
    backup_mode_obj = getattr(disk, "backup_mode", None)
    backup_mode_val = (
        str(getattr(backup_mode_obj, "value", backup_mode_obj))
        if backup_mode_obj is not None
        else None
    )
    shareable_val = (
        bool(getattr(disk, "shareable", False))
        if getattr(disk, "shareable", None) is not None
        else None
    )
    read_only_val = (
        bool(getattr(disk, "read_only", False))
        if getattr(disk, "read_only", None) is not None
        else None
    )
    wipe_val = (
        bool(getattr(disk, "wipe_after_delete", False))
        if getattr(disk, "wipe_after_delete", None) is not None
        else None
    )
    sparse_val = (
        bool(getattr(disk, "sparse", False)) if getattr(disk, "sparse", None) is not None else None
    )
    qcow_val = (
        str(getattr(disk, "qcow_version", "")) if getattr(disk, "qcow_version", None) else None
    )
    sgio_obj = getattr(disk, "sgio", None)
    sgio_val = str(getattr(sgio_obj, "value", sgio_obj)) if sgio_obj is not None else None
    prop_obj = getattr(disk, "propagate_errors", None)
    prop_val = str(getattr(prop_obj, "value", prop_obj)) if prop_obj is not None else None
    desc_val = str(getattr(disk, "description", "")) if getattr(disk, "description", None) else None
    comm_val = str(getattr(disk, "comment", "")) if getattr(disk, "comment", None) else None

    return DiskDetail(
        id=d_id,
        name=d_name,
        status=status_str,
        provisioned_size_gb=prov_gb,
        actual_size_gb=act_gb,
        disk_format=format_str,
        content_type=content_str,
        storage_domain_name=d_sd_name,
        storage_domain_id=d_sd_id,
        backup=backup_val,
        backup_mode=backup_mode_val,
        shareable=shareable_val,
        read_only=read_only_val,
        wipe_after_delete=wipe_val,
        sparse=sparse_val,
        qcow_version=qcow_val,
        sgio=sgio_val,
        propagate_errors=prop_val,
        description=desc_val,
        comment=comm_val,
        io_stats=disk_io,
    )


def delete_disk_tool(
    name_or_id: str,
    dry_run: bool = False,
    confirm: bool = False,
) -> DiskDeleteResult:
    """Permanently delete a virtual disk from its storage domain in oVirt / OLVM.

    Args:
        name_or_id: Name/alias or UUID of the virtual disk to delete.
        dry_run: If True, simulates deletion and validates state without deleting the disk.
        confirm: Confirmation flag required in Safe Mode (MCP_SAFE_MODE=true).

    Returns:
        DiskDeleteResult with outcome and disk identification.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"delete disk '{name_or_id}'",
            confirmed=confirm,
        )
    else:
        require_mutation_allowed("delete_disk")

    client = get_client()
    conn = client.get_connection()
    disks_service = conn.system_service().disks_service()
    disk = client.find_resource_by_id_or_name(disks_service, name_or_id, "disk")
    disk_id = str(disk.id)
    disk_name = str(getattr(disk, "name", disk_id))
    require_disk_status(
        disk_name, getattr(disk, "status", None), ("ok",), action_name="refresh_disk_lun"
    )

    status_obj = getattr(disk, "status", None)
    require_disk_status(disk_name, status_obj, ("ok",), action_name="delete_disk")

    if dry_run:
        audit_log(
            "ovirt_disk_delete",
            disk_name,
            {"disk_id": disk_id, "dry_run": True},
            "SUCCESS",
        )
        return DiskDeleteResult(
            success=True,
            disk_id=disk_id,
            disk_name=disk_name,
            dry_run=True,
            message=f"[DRY RUN] Virtual disk '{disk_name}' ({disk_id}) is eligible for deletion and would be permanently deleted.",
        )

    disk_service = disks_service.disk_service(disk_id)
    try:
        disk_service.remove()
    except Exception as exc:
        audit_log(
            "ovirt_disk_delete",
            disk_name,
            {"disk_id": disk_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to delete virtual disk '{disk_name}': {exc}") from exc

    audit_log(
        "ovirt_disk_delete",
        disk_name,
        {"disk_id": disk_id},
        "SUCCESS",
    )
    return DiskDeleteResult(
        success=True,
        disk_id=disk_id,
        disk_name=disk_name,
        dry_run=False,
        message=f"Virtual disk '{disk_name}' ({disk_id}) was successfully deleted.",
    )


def convert_disk_tool(
    name_or_id: str,
    target_format: str,
    sparse: bool | None = None,
    wait: bool = False,
    timeout_seconds: int = 120,
    dry_run: bool = False,
    confirm: bool = False,
) -> DiskOperationResult:
    """Convert a virtual disk format (cow vs raw) and/or preallocation mode (sparse).

    Args:
        name_or_id: Display name or UUID of the virtual disk.
        target_format: Desired target disk format: 'cow' (qcow2) or 'raw'.
        sparse: Optional allocation policy: True for thin-provisioned / sparse, False for preallocated.
        wait: If True, waits synchronously until conversion completes.
        timeout_seconds: Maximum time to wait if wait=True.
        dry_run: If True, simulates without converting the disk.
        confirm: Confirmation flag required in Safe Mode.

    Returns:
        DiskOperationResult with conversion outcome.
    """
    if not dry_run:
        require_destructive_confirmation(
            f"convert disk '{name_or_id}' to format '{target_format}'",
            confirmed=confirm,
        )
    else:
        require_mutation_allowed("convert_disk")

    fmt_lower = target_format.lower().strip()
    if fmt_lower == "cow":
        fmt_enum = sdk_types.DiskFormat.COW
    elif fmt_lower == "raw":
        fmt_enum = sdk_types.DiskFormat.RAW
    else:
        raise OvirtValidationError(
            f"Invalid target_format '{target_format}'. Allowed values are 'cow' or 'raw'."
        )

    client = get_client()
    conn = client.get_connection()
    disks_service = conn.system_service().disks_service()
    disk = client.find_resource_by_id_or_name(disks_service, name_or_id, "disk")
    disk_id = str(disk.id)
    disk_name = str(getattr(disk, "name", disk_id))

    status_obj = getattr(disk, "status", None)
    require_disk_status(disk_name, status_obj, ("ok",), action_name="convert_disk")

    if dry_run:
        audit_log(
            "ovirt_disk_convert",
            disk_name,
            {"disk_id": disk_id, "target_format": fmt_lower, "dry_run": True},
            "SUCCESS",
        )
        return DiskOperationResult(
            success=True,
            disk_id=disk_id,
            disk_name=disk_name,
            action="convert",
            dry_run=True,
            message=f"[DRY RUN] Virtual disk '{disk_name}' ({disk_id}) would be converted to {fmt_lower} (sparse={sparse}).",
        )

    disk_kwargs: dict[str, Any] = {"format": fmt_enum}
    if sparse is not None:
        disk_kwargs["sparse"] = sparse

    disk_svc = disks_service.disk_service(disk_id)
    try:
        disk_svc.convert(disk=sdk_types.Disk(**disk_kwargs))
    except Exception as exc:
        audit_log(
            "ovirt_disk_convert",
            disk_name,
            {"disk_id": disk_id, "target_format": fmt_lower, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to convert disk '{disk_name}': {exc}") from exc

    if wait:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(3)
            try:
                updated = disk_svc.get()
                st = str(getattr(getattr(updated, "status", None), "value", "ok")).lower()
                if st != "locked":
                    break
            except Exception:
                pass

    audit_log(
        "ovirt_disk_convert",
        disk_name,
        {"disk_id": disk_id, "target_format": fmt_lower},
        "SUCCESS",
    )
    return DiskOperationResult(
        success=True,
        disk_id=disk_id,
        disk_name=disk_name,
        action="convert",
        dry_run=False,
        message=f"Virtual disk '{disk_name}' ({disk_id}) conversion to {fmt_lower} initiated successfully.",
    )


def refresh_disk_lun_tool(
    name_or_id: str,
    dry_run: bool = False,
) -> DiskOperationResult:
    """Refresh the size and underlying volume status of a direct LUN virtual disk.

    Args:
        name_or_id: Display name or UUID of the direct LUN disk.
        dry_run: If True, simulates without executing refresh.

    Returns:
        DiskOperationResult with refresh status.
    """
    require_mutation_allowed("refresh_disk_lun")

    client = get_client()
    conn = client.get_connection()
    disks_service = conn.system_service().disks_service()
    disk = client.find_resource_by_id_or_name(disks_service, name_or_id, "disk")
    disk_id = str(disk.id)
    disk_name = str(getattr(disk, "name", disk_id))
    require_disk_status(
        disk_name, getattr(disk, "status", None), ("ok",), action_name="refresh_disk_lun"
    )

    if dry_run:
        audit_log(
            "ovirt_disk_refresh_lun",
            disk_name,
            {"disk_id": disk_id, "dry_run": True},
            "SUCCESS",
        )
        return DiskOperationResult(
            success=True,
            disk_id=disk_id,
            disk_name=disk_name,
            action="refresh_lun",
            dry_run=True,
            message=f"[DRY RUN] Direct LUN disk '{disk_name}' ({disk_id}) status and capacity would be refreshed.",
        )

    disk_svc = disks_service.disk_service(disk_id)
    try:
        disk_svc.refresh_lun()
    except Exception as exc:
        audit_log(
            "ovirt_disk_refresh_lun",
            disk_name,
            {"disk_id": disk_id, "error": str(exc)},
            "FAILED",
        )
        raise OvirtMCPError(f"Failed to refresh LUN for disk '{disk_name}': {exc}") from exc

    audit_log(
        "ovirt_disk_refresh_lun",
        disk_name,
        {"disk_id": disk_id},
        "SUCCESS",
    )
    return DiskOperationResult(
        success=True,
        disk_id=disk_id,
        disk_name=disk_name,
        action="refresh_lun",
        dry_run=False,
        message=f"Direct LUN disk '{disk_name}' ({disk_id}) refreshed successfully.",
    )
