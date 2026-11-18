"""Unit tests for Quota management tools."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.quota import (
    QuotaDetail,
    QuotaResult,
    QuotaSummary,
)
from ovirt_mcp.tools.quotas import (
    create_quota_tool,
    delete_quota_tool,
    get_quota_tool,
    list_quotas_tool,
)


def test_list_quotas_success() -> None:
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
    mock_dc.id = "dc-1"
    mock_dc.name = "DefaultDC"
    mock_dcs_svc.list.return_value = [mock_dc]

    mock_q = MagicMock()
    mock_q.id = "q-1"
    mock_q.name = "Default"
    mock_q.description = "Unlimited quota"
    mock_dc_svc.quotas_service().list.return_value = [mock_q]

    with patch("ovirt_mcp.tools.quotas.get_client", return_value=mock_client):
        res = list_quotas_tool()

    assert len(res) == 1
    assert isinstance(res[0], QuotaSummary)
    assert res[0].id == "q-1"
    assert res[0].name == "Default"
    assert res[0].data_center_name == "DefaultDC"


def test_get_quota_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_dcs_svc = MagicMock()
    mock_dc_svc = MagicMock()
    mock_quotas_svc = MagicMock()
    mock_q_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.data_centers_service.return_value = mock_dcs_svc
    mock_dcs_svc.data_center_service.return_value = mock_dc_svc
    mock_dc_svc.quotas_service.return_value = mock_quotas_svc
    mock_quotas_svc.quota_service.return_value = mock_q_svc

    mock_dc = MagicMock()
    mock_dc.id = "dc-1"
    mock_dc.name = "DefaultDC"
    mock_dcs_svc.list.return_value = [mock_dc]

    mock_q = MagicMock()
    mock_q.id = "q-1"
    mock_q.name = "Default"
    mock_q.description = "Unlimited"
    mock_quotas_svc.quota_service("q-1").get.return_value = mock_q
    mock_q_svc.get.return_value = mock_q

    mock_cl = MagicMock()
    mock_cl.id = "cl-lim-1"
    mock_cl.cluster.id = "cluster-1"
    mock_cl.cluster.name = "DefaultCluster"
    mock_cl.vcpu_limit = 16
    mock_cl.memory_limit = 64.0
    mock_q_svc.quota_cluster_limits_service().list.return_value = [mock_cl]

    mock_sl = MagicMock()
    mock_sl.id = "st-lim-1"
    mock_sl.storage_domain.id = "sd-1"
    mock_sl.storage_domain.name = "Data"
    mock_sl.limit = 500.0
    mock_q_svc.quota_storage_limits_service().list.return_value = [mock_sl]

    with patch("ovirt_mcp.tools.quotas.get_client", return_value=mock_client):
        res = get_quota_tool("q-1")

    assert isinstance(res, QuotaDetail)
    assert res.id == "q-1"
    assert len(res.cluster_limits) == 1
    assert res.cluster_limits[0].vcpu_limit == 16
    assert res.cluster_limits[0].memory_limit_gb == 64.0
    assert len(res.storage_limits) == 1
    assert res.storage_limits[0].limit_gb == 500.0


def test_create_quota_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_dcs_svc = MagicMock()
    mock_dc_svc = MagicMock()
    mock_quotas_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.data_centers_service.return_value = mock_dcs_svc
    mock_dcs_svc.data_center_service.return_value = mock_dc_svc
    mock_dc_svc.quotas_service.return_value = mock_quotas_svc

    mock_dc = MagicMock()
    mock_dc.id = "dc-1"
    mock_dc.name = "DefaultDC"
    mock_client.find_resource_by_id_or_name.return_value = mock_dc

    mock_quotas_svc.list.return_value = []  # No collision

    mock_created = MagicMock()
    mock_created.id = "new-q-id"
    mock_quotas_svc.add.return_value = mock_created

    with patch("ovirt_mcp.tools.quotas.get_client", return_value=mock_client):
        res = create_quota_tool("DevQuota", "DefaultDC", description="Developer quota")

    assert isinstance(res, QuotaResult)
    assert res.success is True
    assert res.quota_id == "new-q-id"
    assert res.action == "create"
    mock_quotas_svc.add.assert_called_once()


def test_delete_quota_default_guard() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_dcs_svc = MagicMock()
    mock_dc_svc = MagicMock()
    mock_quotas_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.data_centers_service.return_value = mock_dcs_svc
    mock_dcs_svc.data_center_service.return_value = mock_dc_svc
    mock_dc_svc.quotas_service.return_value = mock_quotas_svc

    mock_dc = MagicMock()
    mock_dc.id = "dc-1"
    mock_dc.name = "DefaultDC"
    mock_client.find_resource_by_id_or_name.return_value = mock_dc

    mock_q = MagicMock()
    mock_q.id = "default-q-id"
    mock_q.name = "Default"
    mock_quotas_svc.quota_service("Default").get.return_value = mock_q

    with (
        patch("ovirt_mcp.tools.quotas.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="Cannot delete system Default quota"),
    ):
        delete_quota_tool("Default", "DefaultDC", confirm=True)


def test_delete_quota_safe_mode_guard() -> None:
    mock_cfg = OvirtConfig(
        ovirt_url="https://olvm-engine.example.com/ovirt-engine/api",
        ovirt_username="admin@internal",
        ovirt_password=SecretStr("pwd"),
        mcp_safe_mode=True,
    )
    with (
        patch("ovirt_mcp.config.get_config", return_value=mock_cfg),
        patch("ovirt_mcp.tools.guards.get_config", return_value=mock_cfg),
        pytest.raises(OvirtValidationError, match="Operation 'ovirt_quota_delete' is destructive"),
    ):
        delete_quota_tool("DevQuota", "DefaultDC", confirm=False)
