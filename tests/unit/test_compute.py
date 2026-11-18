"""Unit tests for VM compute resource updating and console ticket tools."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtPermissionError, OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.compute import (
    VmConsoleTicket,
    VmGraphicsConsoleInfo,
    VmUpdateResult,
)
from ovirt_mcp.tools.compute import (
    get_vm_console_ticket_tool,
    list_vm_graphics_consoles_tool,
    update_vm_tool,
)


def _setup_mock_vm(
    vm_id: str = "vm-uuid-1",
    vm_name: str = "test-vm",
    status_str: str = "down",
) -> tuple[MagicMock, MagicMock, MagicMock]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = vm_id
    mock_vm.name = vm_name
    mock_status = MagicMock()
    mock_status.value = status_str
    mock_vm.status = mock_status

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    return mock_client, mock_vm_service, mock_vm


# ── UPDATE VM TESTS ───────────────────────────────────────────────────────────


def test_update_vm_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        update_vm_tool("test-vm", memory_mb=2048)
    assert "read-only mode" in str(exc_info.value)


def test_update_vm_safe_mode_unconfirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        update_vm_tool("test-vm", memory_mb=4096, confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_update_vm_no_params(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, _ = _setup_mock_vm()

    with patch("ovirt_mcp.tools.compute.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            update_vm_tool("test-vm")
        assert "No resource parameters" in str(exc_info.value)


def test_update_vm_invalid_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, _ = _setup_mock_vm()

    with patch("ovirt_mcp.tools.compute.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            update_vm_tool("test-vm", memory_mb=-10, confirm=True)
        assert "Memory must be greater than 0 MB" in str(exc_info.value)


def test_update_vm_invalid_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, _ = _setup_mock_vm()

    with patch("ovirt_mcp.tools.compute.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            update_vm_tool("test-vm", cpu_cores=0, confirm=True)
        assert "positive integers" in str(exc_info.value)


def test_update_vm_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm()

    mock_updated = MagicMock()
    mock_updated.memory = 4096 * (1024**2)
    mock_updated.cpu.topology.cores = 4
    mock_updated.cpu.topology.sockets = 1
    mock_updated.high_availability.enabled = True
    mock_vm_service.update.return_value = mock_updated

    with patch("ovirt_mcp.tools.compute.get_client", return_value=mock_client):
        res = update_vm_tool(
            "test-vm",
            memory_mb=4096,
            cpu_cores=4,
            ha_enabled=True,
            confirm=True,
        )

    assert isinstance(res, VmUpdateResult)
    assert res.success is True
    assert res.memory_mb == 4096
    assert res.cpu_cores == 4
    assert res.ha_enabled is True
    mock_vm_service.update.assert_called_once()


# ── GRAPHICS CONSOLES TESTS ───────────────────────────────────────────────────


def test_list_vm_graphics_consoles_success() -> None:
    mock_client, mock_vm_service, _ = _setup_mock_vm()

    mock_c1 = MagicMock()
    mock_c1.id = "vnc-1"
    mock_c1.protocol.value = "vnc"
    mock_c1.port = 5900
    mock_c1.tls_port = 5901

    mock_vm_service.graphics_consoles_service().list.return_value = [mock_c1]

    with patch("ovirt_mcp.tools.compute.get_client", return_value=mock_client):
        res = list_vm_graphics_consoles_tool("test-vm")

    assert len(res) == 1
    assert isinstance(res[0], VmGraphicsConsoleInfo)
    assert res[0].id == "vnc-1"
    assert res[0].protocol == "vnc"
    assert res[0].port == 5900
    assert res[0].tls_port == 5901


# ── CONSOLE TICKET TESTS ──────────────────────────────────────────────────────


def test_get_vm_console_ticket_read_only_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        get_vm_console_ticket_tool("test-vm")
    assert "read-only mode" in str(exc_info.value)


def test_get_vm_console_ticket_vm_down() -> None:
    mock_client, _, _ = _setup_mock_vm(status_str="down")

    with patch("ovirt_mcp.tools.compute.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            get_vm_console_ticket_tool("test-vm")
        assert "must be powered on" in str(exc_info.value)


def test_get_vm_console_ticket_success() -> None:
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="up")

    mock_ticket = MagicMock()
    mock_ticket.value = "s3cr3tT1ck3t!"
    mock_vm_service.ticket.return_value = mock_ticket

    with patch("ovirt_mcp.tools.compute.get_client", return_value=mock_client):
        res = get_vm_console_ticket_tool("test-vm", expiry_seconds=300)

    assert isinstance(res, VmConsoleTicket)
    assert res.ticket_value == "s3cr3tT1ck3t!"
    assert res.expiry_seconds == 300
    mock_vm_service.ticket.assert_called_once()
