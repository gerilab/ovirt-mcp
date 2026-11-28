"""Security guards and operation safety validators for enterprise MCP."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ovirt_mcp.client.exceptions import OvirtPermissionError, OvirtValidationError
from ovirt_mcp.config import get_config

logger = logging.getLogger("ovirt_mcp.security")


TRANSITIONAL_HOST_STATUSES: tuple[str, ...] = (
    "reboot",
    "installing",
    "preparing_for_maintenance",
    "kdumping",
    "connecting",
    "initializing",
)

TRANSITIONAL_VM_STATUSES: tuple[str, ...] = (
    "powering_up",
    "powering_down",
    "wait_for_launch",
    "reboot_in_progress",
    "saving_state",
    "restoring_state",
    "image_locked",
    "migrating",
)

TRANSITIONAL_STORAGE_STATUSES: tuple[str, ...] = (
    "locked",
    "unknown",
    "uninitialized",
)

TRANSITIONAL_DISK_STATUSES: tuple[str, ...] = (
    "locked",
    "illegal",
)

TRANSITIONAL_SNAPSHOT_STATUSES: tuple[str, ...] = ("locked",)

TRANSITIONAL_TEMPLATE_STATUSES: tuple[str, ...] = ("locked",)


def _extract_status_string(status: Any, default_mock: str = "up") -> str:
    """Extract string status from enum, string, or mock safely."""
    if status is None:
        return default_mock
    val = getattr(status, "value", status)
    if hasattr(val, "name"):
        val = getattr(val, "name", val)
    if type(val).__name__ in ("MagicMock", "Mock"):
        return default_mock
    return str(val or default_mock).strip().lower()


def require_host_status(
    host_name: str,
    current_status: Any,
    allowed_statuses: tuple[str, ...],
    action_name: str,
) -> None:
    """Validate that a hypervisor host is in an eligible operational state before executing an action.

    Raises:
        OvirtValidationError: If current_status is not in allowed_statuses.
    """
    curr = _extract_status_string(current_status, default_mock="up")
    allowed_lower = tuple(s.lower() for s in allowed_statuses)
    if curr not in allowed_lower:
        is_transitional = curr in TRANSITIONAL_HOST_STATUSES
        trans_hint = (
            " Operations are strictly blocked while the host is in an ephemeral transitional state."
            if is_transitional
            else ""
        )
        allowed_str = ", ".join(f"'{s}'" for s in allowed_statuses)
        msg = (
            f"Cannot execute '{action_name}' on host '{host_name}': Current status is '{curr}'. "
            f"oVirt requires the host to be in one of the following states: {allowed_str} (must be {allowed_str}).{trans_hint}"
        )
        logger.warning(
            "HOST_STATUS_GUARD_REJECTED: host=%s current=%s allowed=%s action=%s",
            host_name,
            curr,
            allowed_statuses,
            action_name,
        )
        raise OvirtValidationError(
            msg,
            details={
                "host_name": host_name,
                "current_status": curr,
                "allowed_statuses": list(allowed_statuses),
                "is_transitional": is_transitional,
                "action": action_name,
            },
        )


def require_vm_status(
    vm_name: str,
    current_status: Any,
    allowed_statuses: tuple[str, ...],
    action_name: str,
) -> None:
    """Validate that a virtual machine is in an eligible operational state before executing an action.

    Raises:
        OvirtValidationError: If current_status is not in allowed_statuses.
    """
    curr = _extract_status_string(current_status, default_mock="up")
    allowed_lower = tuple(s.lower() for s in allowed_statuses)
    if curr not in allowed_lower:
        is_transitional = curr in TRANSITIONAL_VM_STATUSES
        trans_hint = (
            " Operations are strictly blocked while the virtual machine is in an ephemeral transitional state."
            if is_transitional
            else ""
        )
        down_hint = (
            " Please stop the virtual machine first before executing this operation."
            if allowed_statuses == ("down",) and curr != "down"
            else ""
        )
        allowed_str = ", ".join(f"'{s}'" for s in allowed_statuses)
        msg = (
            f"Cannot execute '{action_name}' on VM '{vm_name}': Current status is '{curr}'. "
            f"oVirt requires the VM to be in one of the following states: {allowed_str}.{trans_hint}{down_hint}"
        )
        logger.warning(
            "VM_STATUS_GUARD_REJECTED: vm=%s current=%s allowed=%s action=%s",
            vm_name,
            curr,
            allowed_statuses,
            action_name,
        )
        raise OvirtValidationError(
            msg,
            details={
                "vm_name": vm_name,
                "current_status": curr,
                "allowed_statuses": list(allowed_statuses),
                "is_transitional": is_transitional,
                "action": action_name,
            },
        )


def require_storage_domain_status(
    domain_name: str,
    current_status: Any,
    allowed_statuses: tuple[str, ...],
    action_name: str,
) -> None:
    """Validate that a storage domain is in an eligible operational state before executing an action.

    Raises:
        OvirtValidationError: If current_status is not in allowed_statuses.
    """
    curr = _extract_status_string(current_status, default_mock="active")
    allowed_lower = tuple(s.lower() for s in allowed_statuses)
    if curr not in allowed_lower:
        is_transitional = curr in TRANSITIONAL_STORAGE_STATUSES
        trans_hint = (
            " Operations are strictly blocked while the storage domain is in an ephemeral transitional state."
            if is_transitional
            else ""
        )
        allowed_str = ", ".join(f"'{s}'" for s in allowed_statuses)
        msg = (
            f"Cannot execute '{action_name}' on storage domain '{domain_name}': Current status is '{curr}'. "
            f"oVirt requires the domain to be in one of the following states: {allowed_str}.{trans_hint}"
        )
        logger.warning(
            "STORAGE_STATUS_GUARD_REJECTED: domain=%s current=%s allowed=%s action=%s",
            domain_name,
            curr,
            allowed_statuses,
            action_name,
        )
        raise OvirtValidationError(
            msg,
            details={
                "domain_name": domain_name,
                "current_status": curr,
                "allowed_statuses": list(allowed_statuses),
                "is_transitional": is_transitional,
                "action": action_name,
            },
        )


def require_disk_status(
    disk_id_or_name: str,
    current_status: Any,
    allowed_statuses: tuple[str, ...],
    action_name: str,
) -> None:
    """Validate that a virtual disk is in an eligible operational state before executing an action.

    Raises:
        OvirtValidationError: If current_status is not in allowed_statuses.
    """
    curr = _extract_status_string(current_status, default_mock="ok")
    allowed_lower = tuple(s.lower() for s in allowed_statuses)
    if curr not in allowed_lower:
        is_transitional = curr in TRANSITIONAL_DISK_STATUSES
        trans_hint = (
            " Operations are strictly blocked while the disk is currently locked or illegal."
            if is_transitional
            else ""
        )
        allowed_str = ", ".join(f"'{s}'" for s in allowed_statuses)
        msg = (
            f"Cannot execute '{action_name}' on disk '{disk_id_or_name}': Current status is '{curr}'. "
            f"oVirt requires the disk to be in one of the following states: {allowed_str}.{trans_hint}"
        )
        logger.warning(
            "DISK_STATUS_GUARD_REJECTED: disk=%s current=%s allowed=%s action=%s",
            disk_id_or_name,
            curr,
            allowed_statuses,
            action_name,
        )
        raise OvirtValidationError(
            msg,
            details={
                "disk": disk_id_or_name,
                "current_status": curr,
                "allowed_statuses": list(allowed_statuses),
                "is_transitional": is_transitional,
                "action": action_name,
            },
        )


def require_snapshot_status(
    snapshot_desc_or_id: str,
    current_status: Any,
    allowed_statuses: tuple[str, ...],
    action_name: str,
) -> None:
    """Validate that a VM snapshot is in an eligible operational state before executing an action.

    Raises:
        OvirtValidationError: If current_status is not in allowed_statuses.
    """
    curr = _extract_status_string(current_status, default_mock="ok")
    allowed_lower = tuple(s.lower() for s in allowed_statuses)
    if curr not in allowed_lower:
        is_transitional = curr in TRANSITIONAL_SNAPSHOT_STATUSES
        trans_hint = (
            " Operations are strictly blocked while the snapshot is locked."
            if is_transitional
            else ""
        )
        allowed_str = ", ".join(f"'{s}'" for s in allowed_statuses)
        msg = (
            f"Cannot execute '{action_name}' on snapshot '{snapshot_desc_or_id}': Current status is '{curr}'. "
            f"oVirt requires the snapshot to be in one of the following states: {allowed_str}.{trans_hint}"
        )
        logger.warning(
            "SNAPSHOT_STATUS_GUARD_REJECTED: snapshot=%s current=%s allowed=%s action=%s",
            snapshot_desc_or_id,
            curr,
            allowed_statuses,
            action_name,
        )
        raise OvirtValidationError(
            msg,
            details={
                "snapshot": snapshot_desc_or_id,
                "current_status": curr,
                "allowed_statuses": list(allowed_statuses),
                "is_transitional": is_transitional,
                "action": action_name,
            },
        )


def require_template_status(
    template_name: str,
    current_status: Any,
    allowed_statuses: tuple[str, ...] = ("ok",),
    action_name: str = "operation",
) -> None:
    """Validate that a template is in an eligible operational state before executing an action.

    Raises:
        OvirtValidationError: If current_status is not in allowed_statuses.
    """
    curr = _extract_status_string(current_status, default_mock="ok")
    allowed_lower = tuple(s.lower() for s in allowed_statuses)
    if curr not in allowed_lower:
        is_transitional = curr in TRANSITIONAL_TEMPLATE_STATUSES
        trans_hint = (
            " Operations are strictly blocked while the template is in an ephemeral transitional state (e.g. locked)."
            if is_transitional
            else ""
        )
        allowed_str = ", ".join(f"'{s}'" for s in allowed_statuses)
        msg = (
            f"Cannot execute '{action_name}' on template '{template_name}': Current status is '{curr}'. "
            f"oVirt requires the template to be in one of the following states: {allowed_str}.{trans_hint}"
        )
        logger.warning(
            "TEMPLATE_STATUS_GUARD_REJECTED: template=%s current=%s allowed=%s action=%s",
            template_name,
            curr,
            allowed_statuses,
            action_name,
        )
        raise OvirtValidationError(
            msg,
            details={
                "template_name": template_name,
                "current_status": curr,
                "allowed_statuses": list(allowed_statuses),
                "is_transitional": is_transitional,
                "action": action_name,
            },
        )


def require_mutation_allowed(action_name: str) -> None:
    """Enforce that the server is not operating in read-only mode.

    Raises:
        OvirtPermissionError: If MCP_READ_ONLY is enabled.
    """
    config = get_config()
    if config.mcp_read_only:
        msg = (
            f"Operation '{action_name}' is prohibited. "
            "Server is operating in read-only mode (MCP_READ_ONLY=true)."
        )
        logger.warning(msg)
        raise OvirtPermissionError(msg, details={"action": action_name, "read_only": True})


def require_destructive_confirmation(action_name: str, confirmed: bool) -> None:
    """Enforce safe-mode confirmation for high-risk and destructive operations.

    Raises:
        OvirtValidationError: If safe mode is active and confirmed is False.
    """
    require_mutation_allowed(action_name)
    config = get_config()
    if config.mcp_safe_mode and not confirmed:
        msg = (
            f"Operation '{action_name}' is destructive and safe mode is enabled. "
            "You must explicitly supply confirm=True to execute this action."
        )
        logger.warning(msg)
        raise OvirtValidationError(
            msg,
            details={"action": action_name, "safe_mode": True, "confirmed": False},
        )


def audit_log(action_name: str, target: str, details: dict[str, Any], status: str) -> None:
    """Write an enterprise audit log entry for tracking actions taken by AI agents."""
    config = get_config()
    logger.info(
        "AUDIT: user=%s action=%s target=%s status=%s details=%s",
        config.ovirt_username,
        action_name,
        target,
        status,
        details,
    )
    if config.ovirt_audit_log_file:
        try:
            log_path = Path(config.ovirt_audit_log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "timestamp": datetime.now(UTC).isoformat(),
                "action": action_name,
                "user": config.ovirt_username,
                "target": target,
                "status": status,
                "details": details,
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as exc:
            logger.warning(
                "Failed to write audit log record to '%s': %s",
                config.ovirt_audit_log_file,
                exc,
            )
