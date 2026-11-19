"""Models for oVirt / OLVM Virtual Machine Backups and CBT Checkpoints."""

from pydantic import BaseModel, Field


class VmCheckpointInfo(BaseModel):
    """Information about a VM Changed Block Tracking (CBT) checkpoint."""

    id: str = Field(description="Unique ID of the checkpoint.")
    vm_id: str = Field(description="ID of the virtual machine.")
    vm_name: str | None = Field(default=None, description="Name of the virtual machine.")
    parent_id: str | None = Field(
        default=None, description="ID of the parent checkpoint if part of a chain."
    )
    creation_date: str | None = Field(
        default=None, description="ISO timestamp of when the checkpoint was created."
    )
    disk_ids: list[str] = Field(
        default_factory=list,
        description="IDs of disks included in this checkpoint tracking bitmap.",
    )
    description: str | None = Field(
        default=None, description="Optional description or comment on the checkpoint."
    )


class VmBackupInfo(BaseModel):
    """Information about a VM backup operation (full or incremental CBT)."""

    id: str = Field(description="Unique ID of the backup session.")
    vm_id: str = Field(description="ID of the virtual machine being backed up.")
    vm_name: str | None = Field(default=None, description="Name of the virtual machine.")
    phase: str = Field(
        description="Current phase of the backup (e.g., initializing, ready, finalizing, succeeded, failed)."
    )
    creation_date: str | None = Field(
        default=None, description="ISO timestamp of when the backup was initiated."
    )
    modification_date: str | None = Field(
        default=None, description="ISO timestamp of last status modification."
    )
    from_checkpoint_id: str | None = Field(
        default=None,
        description="Parent checkpoint ID for incremental backup, or None for full backup.",
    )
    to_checkpoint_id: str | None = Field(
        default=None,
        description="Target checkpoint ID created by this backup operation.",
    )
    disk_ids: list[str] = Field(
        default_factory=list, description="IDs of disks included in this backup."
    )
    snapshot_id: str | None = Field(
        default=None, description="Underlying snapshot ID created for backup consistency."
    )
    description: str | None = Field(
        default=None, description="Optional description or comment on the backup."
    )


class BackupOperationResult(BaseModel):
    """Result of a backup or checkpoint operation."""

    status: str = Field(
        description="Status of the operation: 'initiated', 'finalized', 'deleted', or 'failed'."
    )
    vm_id: str = Field(description="ID of the affected virtual machine.")
    vm_name: str = Field(description="Name of the affected virtual machine.")
    backup_id: str | None = Field(
        default=None, description="ID of the backup session if applicable."
    )
    checkpoint_id: str | None = Field(
        default=None, description="ID of the checkpoint if applicable."
    )
    phase: str | None = Field(
        default=None, description="Current phase of the backup if applicable."
    )
    message: str = Field(description="Human-readable summary of the operation.")
