"""Security guards and operation safety validators for enterprise MCP."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ovirt_mcp.client.exceptions import OvirtPermissionError, OvirtValidationError
from ovirt_mcp.config import get_config

logger = logging.getLogger("ovirt_mcp.security")


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
