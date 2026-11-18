"""Unit tests for virtual machine lifecycle management (start, stop, reboot)."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import (
    OvirtPermissionError,
    OvirtTimeoutError,
    OvirtValidationError,
)
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.vm import VmLifecycleResult
from ovirt_mcp.tools.vms import reboot_vm_tool, start_vm_tool, stop_vm_tool


@pytest.fixture
def mock_vm_service() -> MagicMock:
    """Mock for oVirt SDK VmService."""
    service = MagicMock()
    return service


def test_start_vm_already_up() -> None:
    """Starting an already running VM should succeed immediately without calling SDK start."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_client.get_connection.return_value = mock_conn
    mock_vm = MagicMock()
    mock_vm.id = "uuid-vm-1"
    mock_vm.name = "web-node-1"
    mock_vm.status.value = "up"
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    mock_client.config.mcp_read_only = False

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = start_vm_tool("web-node-1")
        assert isinstance(res, VmLifecycleResult)
        assert res.success is True
        assert res.action == "start"
        assert res.previous_status == "up"
        assert "already up" in res.message


def test_start_vm_success() -> None:
    """Starting a down VM initiates start via SDK."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "uuid-vm-1"
    mock_vm.name = "web-node-1"
    mock_vm.status.value = "down"
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.config.mcp_read_only = False

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = start_vm_tool("web-node-1", pause=False, wait=False)
        assert res.success is True
        assert res.action == "start"
        assert res.previous_status == "down"
        assert res.current_status == "powering_up"
        mock_vm_service.start.assert_called_once_with(pause=False)


def test_start_vm_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Starting a VM in read-only mode must raise OvirtPermissionError."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        start_vm_tool("web-node-1")
    assert "read-only mode" in str(exc_info.value)


def test_start_vm_wait_timeout() -> None:
    """When wait=True and VM doesn't reach target status within timeout, OvirtTimeoutError is raised."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "uuid-vm-1"
    mock_vm.name = "web-node-1"
    mock_vm.status.value = "down"
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    # Refreshed state keeps returning powering_up
    refreshed_vm = MagicMock()
    refreshed_vm.status.value = "powering_up"
    mock_vm_service.get.return_value = refreshed_vm

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.config.mcp_read_only = False

    with (
        patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client),
        patch("time.sleep", return_value=None),
        patch("time.time", side_effect=[100.0, 100.0, 101.0, 102.0, 105.0, 110.0]),
    ):
        with pytest.raises(OvirtTimeoutError) as exc_info:
            start_vm_tool("web-node-1", wait=True, timeout_seconds=3)
        assert "did not reach" in str(exc_info.value)


def test_stop_vm_safe_mode_unconfirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stopping a VM without confirm=True in safe mode must raise OvirtValidationError."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        stop_vm_tool("web-node-1", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_stop_vm_already_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stopping an already down VM returns success early."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_client.get_connection.return_value = mock_conn
    mock_vm = MagicMock()
    mock_vm.id = "uuid-vm-1"
    mock_vm.name = "web-node-1"
    mock_vm.status.value = "down"
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = stop_vm_tool("web-node-1", confirm=True)
        assert res.success is True
        assert res.previous_status == "down"
        assert "already down" in res.message


def test_stop_vm_graceful_blocked_during_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Graceful stop must be rejected if the VM is still powering_up or waiting for launch."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_vm = MagicMock()
    mock_vm.id = "uuid-vm-1"
    mock_vm.name = "web-node-1"
    mock_vm.status.value = "powering_up"
    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_client.get_connection.return_value = mock_conn

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            stop_vm_tool("web-node-1", graceful=True, confirm=True)
        assert "powering_up" in str(exc_info.value)
        assert (
            "vtools" in str(exc_info.value).lower() or "guest agent" in str(exc_info.value).lower()
        )


def test_stop_vm_graceful_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Graceful stop invokes vm_service.shutdown."""
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
    mock_vm.id = "uuid-vm-1"
    mock_vm.name = "web-node-1"
    mock_vm.status.value = "up"
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = stop_vm_tool("web-node-1", graceful=True, force=False, confirm=True, wait=False)
        assert res.success is True
        assert res.action == "shutdown"
        assert res.graceful is True
        assert "graceful" in res.message
        mock_vm_service.shutdown.assert_called_once_with(force=False)


def test_stop_vm_forced_poweroff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-graceful stop invokes vm_service.stop(force=True)."""
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
    mock_vm.id = "uuid-vm-1"
    mock_vm.name = "web-node-1"
    mock_vm.status.value = "up"
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = stop_vm_tool("web-node-1", graceful=False, force=True, confirm=True, wait=False)
        assert res.success is True
        assert res.action == "stop"
        assert res.graceful is False
        assert "hard power-off" in res.message
        mock_vm_service.stop.assert_called_once_with(force=True)


def test_reboot_vm_down_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rebooting a DOWN VM must raise OvirtValidationError."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_client.get_connection.return_value = mock_conn
    mock_vm = MagicMock()
    mock_vm.id = "uuid-vm-1"
    mock_vm.name = "web-node-1"
    mock_vm.status.value = "down"
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            reboot_vm_tool("web-node-1", confirm=True)
        assert "currently down" in str(exc_info.value)


def test_reboot_vm_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rebooting an UP VM calls vm_service.reboot."""
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
    mock_vm.id = "uuid-vm-1"
    mock_vm.name = "web-node-1"
    mock_vm.status.value = "up"
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = reboot_vm_tool("web-node-1", force=False, confirm=True, wait=False)
        assert res.success is True
        assert res.action == "reboot"
        assert res.current_status == "rebooting"
        mock_vm_service.reboot.assert_called_once_with(force=False)
