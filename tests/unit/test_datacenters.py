"""Unit tests for Data Center management tools."""

from unittest.mock import MagicMock, patch

from ovirt_mcp.models.datacenter import (
    DataCenterDetail,
    DataCenterSummary,
)
from ovirt_mcp.tools.datacenters import (
    get_datacenter_tool,
    list_datacenters_tool,
)


def test_list_datacenters_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_dcs_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.data_centers_service.return_value = mock_dcs_svc

    mock_dc = MagicMock()
    mock_dc.id = "dc-uuid-1"
    mock_dc.name = "DefaultDC"
    mock_dc.description = "Primary datacenter"
    mock_dc.status.value = "up"
    mock_dc.local = False
    mock_dc.version.major = 4
    mock_dc.version.minor = 7
    mock_dc.quota_mode.value = "enabled"

    mock_dcs_svc.list.return_value = [mock_dc]

    with patch("ovirt_mcp.tools.datacenters.get_client", return_value=mock_client):
        res = list_datacenters_tool()

    assert len(res) == 1
    assert isinstance(res[0], DataCenterSummary)
    assert res[0].id == "dc-uuid-1"
    assert res[0].name == "DefaultDC"
    assert res[0].storage_type == "shared"
    assert res[0].compatibility_version == "4.7"
    assert res[0].quota_mode == "enabled"


def test_get_datacenter_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_dcs_svc = MagicMock()
    mock_dc_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.data_centers_service.return_value = mock_dcs_svc
    mock_dcs_svc.data_center_service.return_value = mock_dc_svc

    mock_dc = MagicMock()
    mock_dc.id = "dc-uuid-1"
    mock_dc.name = "DefaultDC"
    mock_dc.description = "Primary DC"
    mock_dc.status.value = "up"
    mock_dc.local = False
    mock_dc.version.major = 4
    mock_dc.version.minor = 7
    mock_dc.quota_mode = None

    mock_client.find_resource_by_id_or_name.return_value = mock_dc

    mock_cl = MagicMock()
    mock_cl.name = "DefaultCluster"
    mock_dc_svc.clusters_service().list.return_value = [mock_cl]

    mock_sd = MagicMock()
    mock_sd.name = "Data"
    mock_dc_svc.storage_domains_service().list.return_value = [mock_sd]

    mock_net = MagicMock()
    mock_net.name = "ovirtmgmt"
    mock_dc_svc.networks_service().list.return_value = [mock_net]

    with patch("ovirt_mcp.tools.datacenters.get_client", return_value=mock_client):
        res = get_datacenter_tool("DefaultDC")

    assert isinstance(res, DataCenterDetail)
    assert res.id == "dc-uuid-1"
    assert res.clusters == ["DefaultCluster"]
    assert res.storage_domains == ["Data"]
    assert res.networks == ["ovirtmgmt"]
