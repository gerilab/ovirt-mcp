"""Unit tests for Hypervisor Host Network Bonding tools."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.host_network import HostBondResult
from ovirt_mcp.tools.host_bonding import (
    create_host_bond_tool,
    delete_host_bond_tool,
)


def test_create_host_bond_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_hosts_svc = MagicMock()
    mock_h_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.hosts_service.return_value = mock_hosts_svc
    mock_hosts_svc.host_service.return_value = mock_h_svc

    mock_host = MagicMock()
    mock_host.id = "host-1"
    mock_host.name = "olvmhost002"
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    mock_nic1 = MagicMock()
    mock_nic1.name = "eth1"
    mock_nic2 = MagicMock()
    mock_nic2.name = "eth2"
    mock_h_svc.nics_service().list.return_value = [mock_nic1, mock_nic2]

    with patch("ovirt_mcp.tools.host_bonding.get_client", return_value=mock_client):
        res = create_host_bond_tool(
            "olvmhost002",
            bond_name="bond0",
            slaves=["eth1", "eth2"],
            mode="active-backup",
        )

    assert isinstance(res, HostBondResult)
    assert res.success is True
    assert res.bond_name == "bond0"
    assert res.slaves == ["eth1", "eth2"]
    mock_h_svc.setup_networks.assert_called_once()


def test_create_host_bond_under_two_slaves_guard() -> None:
    with pytest.raises(OvirtValidationError, match="requires at least 2"):
        create_host_bond_tool("olvmhost002", "bond0", slaves=["eth1"])


def test_create_host_bond_missing_slave_guard() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_hosts_svc = MagicMock()
    mock_h_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.hosts_service.return_value = mock_hosts_svc
    mock_hosts_svc.host_service.return_value = mock_h_svc

    mock_host = MagicMock()
    mock_host.id = "host-1"
    mock_host.name = "olvmhost002"
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    mock_nic1 = MagicMock()
    mock_nic1.name = "eth0"
    mock_h_svc.nics_service().list.return_value = [mock_nic1]

    with (
        patch("ovirt_mcp.tools.host_bonding.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="not found on host"),
    ):
        create_host_bond_tool("olvmhost002", "bond0", slaves=["eth0", "eth99"])


def test_delete_host_bond_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_hosts_svc = MagicMock()
    mock_h_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.hosts_service.return_value = mock_hosts_svc
    mock_hosts_svc.host_service.return_value = mock_h_svc

    mock_host = MagicMock()
    mock_host.id = "host-1"
    mock_host.name = "olvmhost002"
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    mock_bond = MagicMock()
    mock_bond.name = "bond0"
    mock_h_svc.nics_service().list.return_value = [mock_bond]

    with patch("ovirt_mcp.tools.host_bonding.get_client", return_value=mock_client):
        res = delete_host_bond_tool("olvmhost002", "bond0", confirm=True)

    assert isinstance(res, HostBondResult)
    assert res.success is True
    assert res.action == "delete"
    mock_h_svc.setup_networks.assert_called_once()


def test_delete_host_bond_safe_mode_guard() -> None:
    mock_cfg = OvirtConfig(
        ovirt_url="https://olvm.local",
        ovirt_username="admin@internal",
        ovirt_password=SecretStr("pwd"),
        mcp_safe_mode=True,
    )
    with (
        patch("ovirt_mcp.config.get_config", return_value=mock_cfg),
        patch("ovirt_mcp.tools.guards.get_config", return_value=mock_cfg),
        pytest.raises(
            OvirtValidationError, match="Operation 'ovirt_host_bond_delete' is destructive"
        ),
    ):
        delete_host_bond_tool("olvmhost002", "bond0", confirm=False)
