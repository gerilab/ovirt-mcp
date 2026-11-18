"""Unit tests for virtual network interfaces (vNICs) and network profiles."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtPermissionError, OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.network import VmNicDetail, VmNicResult, VnicProfileInfo
from ovirt_mcp.tools.networks import (
    add_vm_nic_tool,
    list_vm_nics_tool,
    list_vnic_profiles_tool,
    remove_vm_nic_tool,
)


def _setup_mock_vm_and_networks(
    vm_id: str = "vm-uuid-1",
    vm_name: str = "test-vm",
) -> tuple[MagicMock, MagicMock, MagicMock]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()
    mock_profiles_service = MagicMock()
    mock_networks_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = vm_id
    mock_vm.name = vm_name

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_system.vnic_profiles_service.return_value = mock_profiles_service
    mock_system.networks_service.return_value = mock_networks_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    return mock_client, mock_vm_service, mock_profiles_service


# ── LIST VM NICS TESTS ────────────────────────────────────────────────────────


def test_list_vm_nics_success() -> None:
    mock_client, mock_vm_service, mock_profiles_service = _setup_mock_vm_and_networks()

    mock_prof = MagicMock()
    mock_prof.id = "prof-1"
    mock_prof.name = "ovirtmgmt"
    mock_prof.network.name = "ovirtmgmt"
    mock_profiles_service.list.return_value = [mock_prof]

    mock_nic = MagicMock()
    mock_nic.id = "nic-1"
    mock_nic.name = "nic1"
    mock_nic.mac.address = "52:54:00:11:22:33"
    mock_nic.interface.value = "virtio"
    mock_nic.vnic_profile.id = "prof-1"
    mock_nic.plugged = True
    mock_nic.linked = True

    mock_vm_service.nics_service().list.return_value = [mock_nic]

    with patch("ovirt_mcp.tools.networks.get_client", return_value=mock_client):
        res = list_vm_nics_tool("test-vm")

    assert len(res) == 1
    assert isinstance(res[0], VmNicDetail)
    assert res[0].id == "nic-1"
    assert res[0].name == "nic1"
    assert res[0].mac_address == "52:54:00:11:22:33"
    assert res[0].vnic_profile_name == "ovirtmgmt"
    assert res[0].plugged is True
    assert res[0].linked is True


# ── ADD VM NIC TESTS ──────────────────────────────────────────────────────────


def test_add_vm_nic_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        add_vm_nic_tool("test-vm", name="nic2", profile="ovirtmgmt")
    assert "read-only mode" in str(exc_info.value)


def test_add_vm_nic_empty_name() -> None:
    with pytest.raises(OvirtValidationError) as exc_info:
        add_vm_nic_tool("test-vm", name="   ", profile="ovirtmgmt")
    assert "vNIC name cannot be empty" in str(exc_info.value)


def test_add_vm_nic_invalid_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, _ = _setup_mock_vm_and_networks()
    mock_prof = MagicMock()
    mock_prof.id = "prof-1"
    mock_client.find_resource_by_id_or_name.side_effect = [
        MagicMock(id="vm-1", name="test-vm"),
        mock_prof,
    ]

    with patch("ovirt_mcp.tools.networks.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            add_vm_nic_tool("test-vm", name="nic2", profile="ovirtmgmt", interface="invalid_nic")
        assert "Invalid NIC interface" in str(exc_info.value)


def test_add_vm_nic_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm_and_networks()
    mock_prof = MagicMock()
    mock_prof.id = "prof-1"
    mock_client.find_resource_by_id_or_name.side_effect = [
        MagicMock(id="vm-1", name="test-vm"),
        mock_prof,
    ]

    mock_created = MagicMock()
    mock_created.id = "new-nic-id"
    mock_created.mac.address = "52:54:00:99:88:77"
    mock_vm_service.nics_service().add.return_value = mock_created

    with patch("ovirt_mcp.tools.networks.get_client", return_value=mock_client):
        res = add_vm_nic_tool(
            "test-vm",
            name="nic2",
            profile="ovirtmgmt",
            interface="virtio",
            plugged=True,
            linked=True,
        )

    assert isinstance(res, VmNicResult)
    assert res.success is True
    assert res.action == "add"
    assert res.nic_id == "new-nic-id"
    assert res.nic_name == "nic2"
    assert res.mac_address == "52:54:00:99:88:77"


# ── REMOVE VM NIC TESTS ───────────────────────────────────────────────────────


def test_remove_vm_nic_safe_mode_unconfirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        remove_vm_nic_tool("test-vm", nic_name_or_id="nic2", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_remove_vm_nic_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm_and_networks()
    mock_vm_service.nics_service().list.return_value = []

    with patch("ovirt_mcp.tools.networks.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            remove_vm_nic_tool("test-vm", nic_name_or_id="nic2", confirm=True)
        assert "not found on virtual machine" in str(exc_info.value)


def test_remove_vm_nic_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm_and_networks()

    mock_nic = MagicMock()
    mock_nic.id = "nic-1"
    mock_nic.name = "nic1"
    mock_vm_service.nics_service().list.return_value = [mock_nic]

    mock_nic_svc = MagicMock()
    mock_vm_service.nics_service().nic_service.return_value = mock_nic_svc

    with patch("ovirt_mcp.tools.networks.get_client", return_value=mock_client):
        res = remove_vm_nic_tool("test-vm", nic_name_or_id="nic1", confirm=True)

    assert isinstance(res, VmNicResult)
    assert res.success is True
    assert res.action == "remove"
    mock_nic_svc.remove.assert_called_once()


# ── LIST VNIC PROFILES TESTS ──────────────────────────────────────────────────


def test_list_vnic_profiles_success() -> None:
    mock_client, _, mock_profiles_service = _setup_mock_vm_and_networks()

    mock_prof = MagicMock()
    mock_prof.id = "p-1"
    mock_prof.name = "ovirtmgmt"
    mock_prof.network.id = "net-1"
    mock_prof.network.name = "ovirtmgmt"
    mock_prof.pass_through = False
    mock_prof.port_mirroring = False
    mock_profiles_service.list.return_value = [mock_prof]

    with patch("ovirt_mcp.tools.networks.get_client", return_value=mock_client):
        res = list_vnic_profiles_tool()

    assert len(res) == 1
    assert isinstance(res[0], VnicProfileInfo)
    assert res[0].id == "p-1"
    assert res[0].name == "ovirtmgmt"
    assert res[0].network_id == "net-1"
