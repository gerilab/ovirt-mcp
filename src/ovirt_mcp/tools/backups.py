"""Tools for managing oVirt / OLVM Virtual Machine Backups and CBT Checkpoints."""

import logging
from typing import Any

import ovirtsdk4.types as sdk_types

from ovirt_mcp.client import get_client
from ovirt_mcp.client.exceptions import OvirtMCPError, OvirtValidationError
from ovirt_mcp.models.backup import (
    BackupOperationResult,
    VmBackupInfo,
    VmCheckpointInfo,
)
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
)

logger = logging.getLogger(__name__)


def _clean_opt_str(val: Any) -> str | None:
    """Return string or None if unset or a mock object."""
    if val is None or not isinstance(val, str):
        return None
    return val


def _extract_checkpoint_info(cp: Any, vm_id: str, vm_name: str | None = None) -> VmCheckpointInfo:
    """Extract a typed VmCheckpointInfo from an oVirt SDK Checkpoint object."""
    cp_id = str(cp.id)
    parent_id = _clean_opt_str(getattr(cp, "parent_id", None))

    c_date = getattr(cp, "creation_date", None)
    creation_date = str(c_date) if c_date and not hasattr(c_date, "_mock_return_value") else None
    if isinstance(c_date, str):
        creation_date = c_date

    disks = getattr(cp, "disks", None)
    disk_ids: list[str] = []
    if disks:
        try:
            for d in disks:
                if hasattr(d, "id") and d.id:
                    disk_ids.append(str(d.id))
        except (TypeError, AttributeError):
            pass

    description = _clean_opt_str(getattr(cp, "description", None))

    return VmCheckpointInfo(
        id=cp_id,
        vm_id=vm_id,
        vm_name=vm_name,
        parent_id=parent_id,
        creation_date=creation_date,
        disk_ids=disk_ids,
        description=description,
    )


def _extract_backup_info(b: Any, vm_id: str, vm_name: str | None = None) -> VmBackupInfo:
    """Extract a typed VmBackupInfo from an oVirt SDK Backup object."""
    b_id = str(b.id)

    phase_obj = getattr(b, "phase", None)
    phase_str = str(getattr(phase_obj, "value", phase_obj or "unknown")).lower()

    c_date = getattr(b, "creation_date", None)
    creation_date = str(c_date) if c_date and not hasattr(c_date, "_mock_return_value") else None
    if isinstance(c_date, str):
        creation_date = c_date

    m_date = getattr(b, "modification_date", None)
    modification_date = (
        str(m_date) if m_date and not hasattr(m_date, "_mock_return_value") else None
    )
    if isinstance(m_date, str):
        modification_date = m_date

    from_cp = _clean_opt_str(getattr(b, "from_checkpoint_id", None))
    to_cp = _clean_opt_str(getattr(b, "to_checkpoint_id", None))

    disks = getattr(b, "disks", None)
    disk_ids: list[str] = []
    if disks:
        try:
            for d in disks:
                if hasattr(d, "id") and d.id:
                    disk_ids.append(str(d.id))
        except (TypeError, AttributeError):
            pass

    snap_obj = getattr(b, "snapshot", None)
    snap_id: str | None = None
    if snap_obj is not None:
        raw_snap_id = getattr(snap_obj, "id", None)
        if isinstance(raw_snap_id, str):
            snap_id = raw_snap_id

    description = _clean_opt_str(getattr(b, "description", None))

    return VmBackupInfo(
        id=b_id,
        vm_id=vm_id,
        vm_name=vm_name,
        phase=phase_str,
        creation_date=creation_date,
        modification_date=modification_date,
        from_checkpoint_id=from_cp,
        to_checkpoint_id=to_cp,
        disk_ids=disk_ids,
        snapshot_id=snap_id,
        description=description,
    )


def list_vm_checkpoints_tool(vm_name_or_id: str) -> list[VmCheckpointInfo]:
    """List all CBT (Changed Block Tracking) checkpoints for a virtual machine.

    Args:
        vm_name_or_id: Virtual machine name or UUID.

    Returns:
        List of VmCheckpointInfo detailing checkpoint IDs, parent IDs, and tracked disks.
    """
    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, vm_name_or_id, "vm")
    vm_name = _clean_opt_str(getattr(vm, "name", None))

    checkpoints_service = vms_service.vm_service(vm.id).checkpoints_service()
    cps = checkpoints_service.list() or []

    return [_extract_checkpoint_info(cp, str(vm.id), vm_name) for cp in cps]


def get_vm_checkpoint_tool(vm_name_or_id: str, checkpoint_id: str) -> VmCheckpointInfo:
    """Get details of a specific CBT checkpoint on a virtual machine.

    Args:
        vm_name_or_id: Virtual machine name or UUID.
        checkpoint_id: UUID of the checkpoint to inspect.

    Returns:
        VmCheckpointInfo detailing the checkpoint.
    """
    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, vm_name_or_id, "vm")
    vm_name = _clean_opt_str(getattr(vm, "name", None))

    cp_service = (
        vms_service.vm_service(vm.id).checkpoints_service().checkpoint_service(checkpoint_id)
    )
    cp = cp_service.get()
    if not cp:
        raise OvirtValidationError(
            f"Checkpoint '{checkpoint_id}' not found on VM '{vm_name_or_id}'."
        )

    return _extract_checkpoint_info(cp, str(vm.id), vm_name)


def delete_vm_checkpoint_tool(
    vm_name_or_id: str,
    checkpoint_id: str,
    confirm: bool = False,
) -> BackupOperationResult:
    """Delete a CBT checkpoint from a virtual machine (removes block tracking metadata).

    Args:
        vm_name_or_id: Virtual machine name or UUID.
        checkpoint_id: UUID of the checkpoint to delete.
        confirm: Confirmation flag required when MCP Safe Mode is enabled.

    Returns:
        BackupOperationResult confirming deletion.
    """
    require_destructive_confirmation(
        f"Delete CBT checkpoint '{checkpoint_id}' on VM '{vm_name_or_id}'",
        confirm,
    )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, vm_name_or_id, "vm")
    vm_name = str(getattr(vm, "name", vm.id))

    cp_service = (
        vms_service.vm_service(vm.id).checkpoints_service().checkpoint_service(checkpoint_id)
    )
    try:
        cp_service.remove()
        audit_log(
            "delete_vm_checkpoint",
            f"{vm_name}:{checkpoint_id}",
            {"vm_id": str(vm.id), "checkpoint_id": checkpoint_id},
            "SUCCESS",
        )
        return BackupOperationResult(
            status="deleted",
            vm_id=str(vm.id),
            vm_name=vm_name,
            checkpoint_id=checkpoint_id,
            message=f"CBT checkpoint '{checkpoint_id}' deleted successfully from VM '{vm_name}'.",
        )
    except Exception as e:
        audit_log(
            "delete_vm_checkpoint",
            f"{vm_name}:{checkpoint_id}",
            {"vm_id": str(vm.id), "checkpoint_id": checkpoint_id, "error": str(e)},
            "FAILED",
        )
        logger.error(f"Failed to delete checkpoint '{checkpoint_id}' on VM '{vm_name}': {e}")
        raise OvirtMCPError(f"Failed to delete checkpoint '{checkpoint_id}': {e}") from e


def list_vm_backups_tool(vm_name_or_id: str) -> list[VmBackupInfo]:
    """List all backup sessions (active or completed) for a virtual machine.

    Args:
        vm_name_or_id: Virtual machine name or UUID.

    Returns:
        List of VmBackupInfo detailing backup phases, checkpoints, and disks.
    """
    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, vm_name_or_id, "vm")
    vm_name = _clean_opt_str(getattr(vm, "name", None))

    backups_service = vms_service.vm_service(vm.id).backups_service()
    backups = backups_service.list() or []

    return [_extract_backup_info(b, str(vm.id), vm_name) for b in backups]


def get_vm_backup_tool(vm_name_or_id: str, backup_id: str) -> VmBackupInfo:
    """Get details and current phase of a specific VM backup session.

    Args:
        vm_name_or_id: Virtual machine name or UUID.
        backup_id: UUID of the backup session.

    Returns:
        VmBackupInfo detailing the backup session.
    """
    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, vm_name_or_id, "vm")
    vm_name = _clean_opt_str(getattr(vm, "name", None))

    backup_service = vms_service.vm_service(vm.id).backups_service().backup_service(backup_id)
    b = backup_service.get()
    if not b:
        raise OvirtValidationError(f"Backup '{backup_id}' not found on VM '{vm_name_or_id}'.")

    return _extract_backup_info(b, str(vm.id), vm_name)


def start_vm_backup_tool(
    vm_name_or_id: str,
    from_checkpoint_id: str | None = None,
    disk_ids: list[str] | None = None,
    description: str | None = None,
    confirm: bool = False,
) -> BackupOperationResult:
    """Initiate a live VM backup session (full backup or incremental CBT backup).

    Args:
        vm_name_or_id: Virtual machine name or UUID.
        from_checkpoint_id: UUID of previous checkpoint for incremental backup (None for full backup).
        disk_ids: Optional list of disk UUIDs to include. If omitted, all VM disks are backed up.
        description: Optional comment or description for this backup.
        confirm: Confirmation flag required when MCP Safe Mode is enabled.

    Returns:
        BackupOperationResult with the newly created backup ID and phase.
    """
    require_destructive_confirmation(
        f"Initiate live VM backup on '{vm_name_or_id}'",
        confirm,
    )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, vm_name_or_id, "vm")
    vm_name = str(getattr(vm, "name", vm.id))

    backup_kwargs: dict[str, Any] = {}
    if from_checkpoint_id:
        backup_kwargs["from_checkpoint_id"] = from_checkpoint_id
    if description:
        backup_kwargs["description"] = description
    if disk_ids:
        backup_kwargs["disks"] = [sdk_types.Disk(id=d) for d in disk_ids]

    backup_spec = sdk_types.Backup(**backup_kwargs)
    backups_service = vms_service.vm_service(vm.id).backups_service()

    try:
        new_backup = backups_service.add(backup_spec)
        b_id = str(new_backup.id)
        phase = str(getattr(getattr(new_backup, "phase", None), "value", "initializing")).lower()
        to_cp = _clean_opt_str(getattr(new_backup, "to_checkpoint_id", None))

        audit_log(
            "start_vm_backup",
            vm_name,
            {"vm_id": str(vm.id), "backup_id": b_id, "phase": phase},
            "SUCCESS",
        )
        return BackupOperationResult(
            status="initiated",
            vm_id=str(vm.id),
            vm_name=vm_name,
            backup_id=b_id,
            checkpoint_id=to_cp,
            phase=phase,
            message=f"Live backup session '{b_id}' initiated for VM '{vm_name}' (phase: {phase}).",
        )
    except Exception as e:
        audit_log(
            "start_vm_backup",
            vm_name,
            {"vm_id": str(vm.id), "error": str(e)},
            "FAILED",
        )
        logger.error(f"Failed to initiate backup on VM '{vm_name}': {e}")
        raise OvirtMCPError(f"Failed to initiate backup on VM '{vm_name}': {e}") from e


def finalize_vm_backup_tool(
    vm_name_or_id: str,
    backup_id: str,
    confirm: bool = False,
) -> BackupOperationResult:
    """Finalize a VM backup session after data transfer completes (releases scratch disks/merges).

    Args:
        vm_name_or_id: Virtual machine name or UUID.
        backup_id: UUID of the backup session to finalize.
        confirm: Confirmation flag required when MCP Safe Mode is enabled.

    Returns:
        BackupOperationResult confirming finalization.
    """
    require_destructive_confirmation(
        f"Finalize VM backup '{backup_id}' on VM '{vm_name_or_id}'",
        confirm,
    )

    client = get_client()
    conn = client.get_connection()
    vms_service = conn.system_service().vms_service()
    vm = client.find_resource_by_id_or_name(vms_service, vm_name_or_id, "vm")
    vm_name = str(getattr(vm, "name", vm.id))

    backup_service = vms_service.vm_service(vm.id).backups_service().backup_service(backup_id)
    try:
        backup_service.finalize()
        audit_log(
            "finalize_vm_backup",
            f"{vm_name}:{backup_id}",
            {"vm_id": str(vm.id), "backup_id": backup_id},
            "SUCCESS",
        )
        return BackupOperationResult(
            status="finalized",
            vm_id=str(vm.id),
            vm_name=vm_name,
            backup_id=backup_id,
            phase="finalizing",
            message=f"Live backup session '{backup_id}' on VM '{vm_name}' successfully triggered finalization.",
        )
    except Exception as e:
        audit_log(
            "finalize_vm_backup",
            f"{vm_name}:{backup_id}",
            {"vm_id": str(vm.id), "backup_id": backup_id, "error": str(e)},
            "FAILED",
        )
        logger.error(f"Failed to finalize backup '{backup_id}' on VM '{vm_name}': {e}")
        raise OvirtMCPError(f"Failed to finalize backup '{backup_id}': {e}") from e
