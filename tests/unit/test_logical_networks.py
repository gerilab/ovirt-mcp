"""Unit tests for Logical Network management tools."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.logical_network import (
    LogicalNetworkDetail,
    LogicalNetworkResult,
    LogicalNetworkSummary,
)
from ovirt_mcp.tools.logical_networks import (
    create_logical_network_tool,
    delete_logical_network_tool,
    get_logical_network_tool,
    list_logical_networks_tool,
)


def test_list_logical_networks_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_nets_svc = MagicMock()
    mock_dcs_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.networks_service.return_value = mock_nets_svc
    mock_sys.data_centers_service.return_value = mock_dcs_svc

    mock_dc = MagicMock()
    mock_dc.id = "dc-1"
    mock_dc.name = "DefaultDC"
    mock_dcs_svc.list.return_value = [mock_dc]

    mock_net = MagicMock()
    mock_net.id = "net-1"
    mock_net.name = "ovirtmgmt"
    mock_net.description = "Management network"
    mock_net.data_center.id = "dc-1"
    mock_net.vlan = None
    mock_net.mtu = 1500
    mock_net.status.value = "operational"

    mock_nets_svc.list.return_value = [mock_net]

    with patch("ovirt_mcp.tools.logical_networks.get_client", return_value=mock_client):
        res = list_logical_networks_tool()

    assert len(res) == 1
    assert isinstance(res[0], LogicalNetworkSummary)
    assert res[0].id == "net-1"
    assert res[0].name == "ovirtmgmt"
    assert res[0].vlan_id is None
    assert res[0].mtu == 1500
    assert res[0].data_center_name == "DefaultDC"


def test_create_logical_network_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_dcs_svc = MagicMock()
    mock_nets_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.data_centers_service.return_value = mock_dcs_svc
    mock_sys.networks_service.return_value = mock_nets_svc

    mock_dc = MagicMock()
    mock_dc.id = "dc-1"
    mock_dc.name = "DefaultDC"
    mock_client.find_resource_by_id_or_name.return_value = mock_dc

    mock_nets_svc.list.return_value = []  # No collision

    mock_created = MagicMock()
    mock_created.id = "new-net-id"
    mock_nets_svc.add.return_value = mock_created

    with patch("ovirt_mcp.tools.logical_networks.get_client", return_value=mock_client):
        res = create_logical_network_tool(
            "VLAN_Storage",
            "DefaultDC",
            vlan_id=200,
            mtu=9000,
            description="iSCSI storage network",
        )

    assert isinstance(res, LogicalNetworkResult)
    assert res.success is True
    assert res.network_id == "new-net-id"
    assert res.network_name == "VLAN_Storage"
    mock_nets_svc.add.assert_called_once()


def test_create_logical_network_invalid_vlan_guard() -> None:
    with pytest.raises(OvirtValidationError, match="Invalid VLAN ID"):
        create_logical_network_tool("BadVLAN", "DefaultDC", vlan_id=5000)


def test_delete_logical_network_ovirtmgmt_guard() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_nets_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.networks_service.return_value = mock_nets_svc

    mock_mgmt = MagicMock()
    mock_mgmt.id = "mgmt-id"
    mock_mgmt.name = "ovirtmgmt"

    mock_client.find_resource_by_id_or_name.return_value = mock_mgmt

    with (
        patch("ovirt_mcp.tools.logical_networks.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="Cannot delete the default management network"),
    ):
        delete_logical_network_tool("ovirtmgmt", confirm=True)


def test_delete_logical_network_safe_mode_guard() -> None:
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
            OvirtValidationError, match="Operation 'ovirt_network_delete' is destructive"
        ),
    ):
        delete_logical_network_tool("VLAN_Storage", confirm=False)


def test_get_logical_network_success() -> None:
    """Test get_logical_network_tool retrieves complete network details."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_nets_svc = MagicMock()
    mock_net_svc = MagicMock()
    mock_dcs_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.networks_service.return_value = mock_nets_svc
    mock_sys.data_centers_service.return_value = mock_dcs_svc
    mock_nets_svc.network_service.return_value = mock_net_svc

    mock_net = MagicMock()
    mock_net.id = "net-100"
    mock_net.name = "vlan-prod"
    mock_net.description = "Production VLAN"
    mock_net.data_center.id = "dc-1"
    mock_net.data_center.name = "ProdDC"
    mock_net.vlan.id = 100
    mock_net.mtu = 9000
    mock_net.status.value = "operational"
    mock_net.stp = True
    mock_net.port_isolation = False
    mock_net.usages = [MagicMock(value="vm")]

    mock_client.find_resource_by_id_or_name.return_value = mock_net

    mock_profile = MagicMock()
    mock_profile.name = "vlan-prod-profile"
    mock_net_svc.vnic_profiles_service().list.return_value = [mock_profile]
    mock_net_svc.network_labels_service().list.return_value = []
    mock_net_svc.permissions_service().list.return_value = [MagicMock()]

    with patch("ovirt_mcp.tools.logical_networks.get_client", return_value=mock_client):
        detail = get_logical_network_tool("vlan-prod")

    assert isinstance(detail, LogicalNetworkDetail)
    assert detail.id == "net-100"
    assert detail.name == "vlan-prod"
    assert detail.vlan_id == 100
    assert detail.mtu == 9000
    assert detail.stp is True
    assert detail.usages == ["vm"]
    assert detail.vnic_profiles == ["vlan-prod-profile"]
    assert detail.permissions_count == 1
