"""Unit tests for Hypervisor Host Network Attachments and iSCSI tools."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtPermissionError, OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.host_network import (
    HostIscsiDiscoverResult,
    HostIscsiLoginResult,
    HostNetworkAttachmentInfo,
    HostNetworkSetupResult,
)
from ovirt_mcp.tools.hosts_network import (
    ovirt_host_iscsi_discover,
    ovirt_host_iscsi_login,
    ovirt_host_network_attachment_list,
    ovirt_host_network_sync,
)


@pytest.fixture
def mock_client() -> tuple[MagicMock, MagicMock]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys

    mock_hosts_svc = MagicMock()
    mock_nets_svc = MagicMock()
    mock_sys.hosts_service.return_value = mock_hosts_svc
    mock_sys.networks_service.return_value = mock_nets_svc

    mock_hosts_svc.list.return_value = []
    mock_nets_svc.list.return_value = []

    return mock_client, mock_sys


def test_host_network_attachment_list(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    hosts_svc = sys_svc.hosts_service.return_value

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost002"
    client.find_resource_by_id_or_name.return_value = mock_host

    h_svc = MagicMock()
    hosts_svc.host_service.return_value = h_svc

    mock_net = MagicMock()
    mock_net.id = "net-1"
    mock_net.name = "ovirtmgmt"
    sys_svc.networks_service.return_value.list.return_value = [mock_net]

    mock_nic = MagicMock()
    mock_nic.id = "nic-1"
    mock_nic.name = "eth0"
    h_svc.nics_service.return_value.list.return_value = [mock_nic]

    mock_att = MagicMock()
    mock_att.id = "att-1"
    mock_att.in_sync = True
    mock_att.network.id = "net-1"
    mock_att.host_nic.id = "nic-1"

    mock_ip_assign = MagicMock()
    mock_ip_assign.assignment_method = "static"
    mock_ip_assign.ip.address = "192.0.2.12"
    mock_ip_assign.ip.netmask = "255.255.255.0"
    mock_ip_assign.ip.gateway = "192.0.2.1"
    mock_att.ip_address_assignments = [mock_ip_assign]

    h_svc.network_attachments_service.return_value.list.return_value = [mock_att]

    with patch("ovirt_mcp.tools.hosts_network.get_client", return_value=client):
        result = ovirt_host_network_attachment_list("olvmhost002")

    assert len(result) == 1
    assert isinstance(result[0], HostNetworkAttachmentInfo)
    assert result[0].network_name == "ovirtmgmt"
    assert result[0].host_nic_name == "eth0"
    assert result[0].ip_address == "192.0.2.12"
    assert result[0].boot_protocol == "static"
    assert result[0].in_sync is True


def test_host_iscsi_discover_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    hosts_svc = sys_svc.hosts_service.return_value

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost002"
    client.find_resource_by_id_or_name.return_value = mock_host

    h_svc = MagicMock()
    hosts_svc.host_service.return_value = h_svc
    h_svc.iscsi_discover.return_value = [
        "iqn.2024-01.org.example:storage.target01",
        "iqn.2024-01.org.example:storage.target02",
    ]

    with patch("ovirt_mcp.tools.hosts_network.get_client", return_value=client):
        res = ovirt_host_iscsi_discover("olvmhost002", address="192.0.2.10", port=3260)

    assert isinstance(res, HostIscsiDiscoverResult)
    assert res.count == 2
    assert "iqn.2024-01.org.example:storage.target01" in res.targets


def test_host_iscsi_discover_empty_address_raises(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, _ = mock_client
    with (
        patch("ovirt_mcp.tools.hosts_network.get_client", return_value=client),
        pytest.raises(OvirtValidationError, match="must not be empty"),
    ):
        ovirt_host_iscsi_discover("olvmhost002", address="   ")


def test_host_iscsi_login_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    hosts_svc = sys_svc.hosts_service.return_value

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost002"
    client.find_resource_by_id_or_name.return_value = mock_host

    h_svc = MagicMock()
    hosts_svc.host_service.return_value = h_svc
    h_svc.iscsi_login.return_value = None

    with (
        patch("ovirt_mcp.tools.hosts_network.get_client", return_value=client),
        patch("ovirt_mcp.tools.guards.get_config", return_value=OvirtConfig(mcp_read_only=False)),
    ):
        res = ovirt_host_iscsi_login(
            "olvmhost002",
            address="192.0.2.10",
            target="iqn.2024-01.org.example:storage.target01",
        )

    assert isinstance(res, HostIscsiLoginResult)
    assert res.success is True
    assert res.target == "iqn.2024-01.org.example:storage.target01"
    h_svc.iscsi_login.assert_called_once()


def test_host_network_sync_already_in_sync(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    hosts_svc = sys_svc.hosts_service.return_value

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost002"
    client.find_resource_by_id_or_name.return_value = mock_host

    h_svc = MagicMock()
    hosts_svc.host_service.return_value = h_svc
    mock_att = MagicMock()
    mock_att.id = "att-1"
    mock_att.in_sync = True
    h_svc.network_attachments_service.return_value.list.return_value = [mock_att]

    with (
        patch("ovirt_mcp.tools.hosts_network.get_client", return_value=client),
        patch("ovirt_mcp.tools.guards.get_config", return_value=OvirtConfig(mcp_read_only=False)),
    ):
        res = ovirt_host_network_sync("olvmhost002")

    assert isinstance(res, HostNetworkSetupResult)
    assert res.success is True
    assert "already in-sync" in res.message
    h_svc.setup_networks.assert_not_called()


def test_host_network_sync_executes(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    hosts_svc = sys_svc.hosts_service.return_value

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost002"
    client.find_resource_by_id_or_name.return_value = mock_host

    h_svc = MagicMock()
    hosts_svc.host_service.return_value = h_svc
    mock_att = MagicMock()
    mock_att.id = "att-1"
    mock_att.in_sync = False
    h_svc.network_attachments_service.return_value.list.return_value = [mock_att]

    with (
        patch("ovirt_mcp.tools.hosts_network.get_client", return_value=client),
        patch("ovirt_mcp.tools.guards.get_config", return_value=OvirtConfig(mcp_read_only=False)),
    ):
        res = ovirt_host_network_sync("olvmhost002")

    assert res.success is True
    assert "synchronized 1 network attachment(s)" in res.message
    h_svc.setup_networks.assert_called_once()


def test_read_only_blocks_mutations(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, _ = mock_client
    with (
        patch("ovirt_mcp.tools.hosts_network.get_client", return_value=client),
        patch("ovirt_mcp.tools.guards.get_config", return_value=OvirtConfig(mcp_read_only=True)),
        pytest.raises(OvirtPermissionError, match="read-only mode"),
    ):
        ovirt_host_iscsi_login("olvmhost002", address="1.2.3.4", target="iqn.test")
