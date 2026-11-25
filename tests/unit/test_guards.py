"""Unit tests for security guards and safe mode."""

import json
from pathlib import Path

import pytest

from ovirt_mcp.client.exceptions import OvirtPermissionError, OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.tools.guards import (
    audit_log,
    require_destructive_confirmation,
    require_mutation_allowed,
)


def test_require_mutation_allowed_success(mock_config: OvirtConfig) -> None:
    """Test mutation allowed when read-only is False."""
    mock_config.mcp_read_only = False
    # Should not raise
    require_mutation_allowed("vm_start")


def test_require_mutation_allowed_blocked(
    mock_config: OvirtConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test mutation raises OvirtPermissionError when read-only is True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config", lambda: OvirtConfig(mcp_read_only=True)
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        require_mutation_allowed("vm_delete")
    assert "read-only mode" in str(exc_info.value)


def test_require_destructive_confirmation_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test destructive operation blocked without confirm=True in safe mode."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        require_destructive_confirmation("vm_delete", confirmed=False)
    assert "destructive" in str(exc_info.value)

    # Should pass when confirmed=True
    require_destructive_confirmation("vm_delete", confirmed=True)


def test_require_destructive_confirmation_blocked_in_read_only_mode_even_if_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that MCP_READ_ONLY strictly blocks mutations even if confirmed=True is passed."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        require_destructive_confirmation("vm_delete", confirmed=True)
    assert "read-only mode" in str(exc_info.value)


def test_audit_log_file_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that audit_log writes structured JSON Lines to ovirt_audit_log_file when configured."""
    log_file = tmp_path / "ovirt_audit.jsonl"
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(ovirt_audit_log_file=log_file),
    )

    audit_log("start_vm", "vm-alpha", {"vm_id": "123", "dry_run": True}, "SUCCESS")
    audit_log("delete_vm", "vm-beta", {"vm_id": "456", "force": True}, "FAILED")

    assert log_file.exists()
    lines = [json.loads(line) for line in log_file.read_text(encoding="utf-8").strip().split("\n")]
    assert len(lines) == 2
    assert lines[0]["action"] == "start_vm"
    assert lines[0]["target"] == "vm-alpha"
    assert lines[0]["details"]["dry_run"] is True
    assert lines[0]["status"] == "SUCCESS"
    assert "timestamp" in lines[0]

    assert lines[1]["action"] == "delete_vm"
    assert lines[1]["target"] == "vm-beta"
    assert lines[1]["status"] == "FAILED"
