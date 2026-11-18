"""Unit tests for VM migration, pinning, and unpinning."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtPermissionError, OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.vm import VmMigrateResult, VmPinResult
from ovirt_mcp.tools.vms import migrate_vm_tool, pin_vm_tool, unpin_vm_tool


def test_migrate_vm_down_rejected() -> None:
    """Migrating a DOWN VM must be rejected."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "vm-1"
    mock_vm.name = "web-srv"
    mock_vm.status.value = "down"

    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            migrate_vm_tool("web-srv")
        assert "actively running" in str(exc_info.value)


def test_migrate_vm_success() -> None:
    """Migrating an UP VM invokes vm_service.migrate."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()
    mock_hosts_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "vm-1"
    mock_vm.name = "web-srv"
    mock_vm.status.value = "up"
    mock_vm.host.id = "host-1"
    mock_vm.host.name = "node01"

    mock_target_host = MagicMock()
    mock_target_host.id = "host-2"
    mock_target_host.name = "node02"

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_system.hosts_service.return_value = mock_hosts_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    def mock_find(service: MagicMock, identifier: str, res_type: str) -> MagicMock:
        if res_type == "vm":
            return mock_vm
        if res_type == "host":
            return mock_target_host
        return MagicMock()

    mock_client.find_resource_by_id_or_name.side_effect = mock_find

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = migrate_vm_tool("web-srv", target_host="node02", wait=False)
        assert isinstance(res, VmMigrateResult)
        assert res.success is True
        assert res.vm_name == "web-srv"
        assert res.source_host == "node01"
        assert res.target_host == "node02"
        mock_vm_service.migrate.assert_called_once()


def test_migrate_vm_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Migration blocked when MCP_READ_ONLY=true."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        migrate_vm_tool("web-srv")
    assert "read-only mode" in str(exc_info.value)


def test_pin_vm_success() -> None:
    """Pinning a VM updates its placement policy to PINNED."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()
    mock_hosts_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "vm-1"
    mock_vm.name = "db-srv"

    mock_host = MagicMock()
    mock_host.id = "host-fast"
    mock_host.name = "fast-node-01"

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_system.hosts_service.return_value = mock_hosts_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    def mock_find(service: MagicMock, identifier: str, res_type: str) -> MagicMock:
        if res_type == "vm":
            return mock_vm
        if res_type == "host":
            return mock_host
        return MagicMock()

    mock_client.find_resource_by_id_or_name.side_effect = mock_find

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = pin_vm_tool("db-srv", host="fast-node-01")
        assert isinstance(res, VmPinResult)
        assert res.success is True
        assert res.affinity == "pinned"
        assert res.pinned_hosts == ["fast-node-01"]
        mock_vm_service.update.assert_called_once()


def test_unpin_vm_success() -> None:
    """Unpinning a VM restores placement policy to MIGRATABLE."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "vm-1"
    mock_vm.name = "db-srv"

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = unpin_vm_tool("db-srv")
        assert isinstance(res, VmPinResult)
        assert res.success is True
        assert res.affinity == "migratable"
        assert res.pinned_hosts == []
        mock_vm_service.update.assert_called_once()
