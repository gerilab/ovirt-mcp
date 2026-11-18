"""Unit tests for security guards and safe mode."""

import pytest

from ovirt_mcp.client.exceptions import OvirtPermissionError, OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.tools.guards import require_destructive_confirmation, require_mutation_allowed


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
