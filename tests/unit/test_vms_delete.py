"""Unit tests for virtual machine deletion (ovirt_vm_delete)."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import (
    OvirtPermissionError,
    OvirtValidationError,
)
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.vm import VmDeleteResult
from ovirt_mcp.tools.vms import delete_vm_tool


def test_delete_vm_safe_mode_unconfirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deleting a VM without confirm=True in safe mode must raise OvirtValidationError."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        delete_vm_tool("test-vm", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_delete_vm_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deleting a VM in read-only mode must raise OvirtPermissionError."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        delete_vm_tool("test-vm", confirm=True)
    assert "read-only mode" in str(exc_info.value)


def test_delete_vm_running_without_force(monkeypatch: pytest.MonkeyPatch) -> None:
    """Attempting to delete a running VM without force=True must raise OvirtValidationError."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "vm-1"
    mock_vm.name = "prod-vm"
    mock_vm.status.value = "up"

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            delete_vm_tool("prod-vm", force=False, confirm=True)
        assert "Stop the virtual machine first" in str(exc_info.value)


def test_delete_vm_down_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deleting a stopped VM calls vm_service.remove."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "vm-123"
    mock_vm.name = "dev-vm"
    mock_vm.status.value = "down"

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = delete_vm_tool("dev-vm", detach_only=False, force=False, confirm=True, wait=False)
        assert isinstance(res, VmDeleteResult)
        assert res.success is True
        assert res.vm_id == "vm-123"
        assert res.vm_name == "dev-vm"
        assert res.disks_detached_only is False
        mock_vm_service.remove.assert_called_once_with(detach_only=False, force=False)


def test_delete_vm_detach_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deleting a VM with detach_only=True preserves disks."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "vm-456"
    mock_vm.name = "storage-vm"
    mock_vm.status.value = "down"

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = delete_vm_tool("storage-vm", detach_only=True, force=False, confirm=True, wait=False)
        assert res.success is True
        assert res.disks_detached_only is True
        mock_vm_service.remove.assert_called_once_with(detach_only=True, force=False)
