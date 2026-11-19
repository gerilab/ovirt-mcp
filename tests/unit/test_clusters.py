"""Unit tests for oVirt / OLVM Clusters tools."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.models.cluster import ClusterDetail, ClusterSummary
from ovirt_mcp.tools.clusters import (
    get_cluster_tool,
    list_clusters_tool,
)


def _setup_mock_cluster_context() -> dict[str, Any]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_clusters_svc = MagicMock()
    mock_dcs_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.clusters_service.return_value = mock_clusters_svc
    mock_sys.data_centers_service.return_value = mock_dcs_svc

    mock_dc = MagicMock(id="dc-1")
    mock_dc.name = "DefaultDC"
    mock_dcs_svc.list.return_value = [mock_dc]

    mock_c1 = MagicMock(id="c-1")
    mock_c1.name = "ProdCluster"
    mock_c1.description = "Production cluster"
    mock_c1.data_center = MagicMock(id="dc-1", name="DefaultDC")
    mock_c1.cpu.type = "Intel SandyBridge Family"
    mock_c1.cpu.architecture.value = "x86_64"
    mock_c1.version.full_version = "4.7"
    mock_c1.ballooning_enabled = True
    mock_c1.ha_reservation = True
    mock_c1.memory_policy.over_commit.percent = 150
    mock_c1.fips_mode.value = "disabled"
    mock_c1.bios_type.value = "q35_secure_boot"
    mock_c1.threads_as_cores = True
    mock_c1.migration.encrypted = True
    mock_c1.migration.bandwidth.assignment_method = "auto"
    mock_c1.fencing_policy.enabled = True
    mock_c1.ksm.enabled = True
    mock_c1.switch_type.value = "legacy"

    mock_clusters_svc.list.return_value = [mock_c1]
    mock_client.find_resource_by_id_or_name.return_value = mock_c1

    return {
        "client": mock_client,
        "clusters_svc": mock_clusters_svc,
        "dcs_svc": mock_dcs_svc,
        "cluster": mock_c1,
        "dc": mock_dc,
    }


def test_list_clusters_tool() -> None:
    ctx = _setup_mock_cluster_context()

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=ctx["client"]):
        res = list_clusters_tool()

    assert len(res) == 1
    assert isinstance(res[0], ClusterSummary)
    assert res[0].id == "c-1"
    assert res[0].name == "ProdCluster"
    assert res[0].cpu_type == "Intel SandyBridge Family"
    assert res[0].cpu_architecture == "x86_64"
    assert res[0].ballooning_enabled is True


def test_list_clusters_tool_with_filter() -> None:
    ctx = _setup_mock_cluster_context()

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=ctx["client"]):
        res = list_clusters_tool(search="name=Prod*")

    assert len(res) == 1
    ctx["clusters_svc"].list.assert_called_once_with(search="name=Prod*")


def test_get_cluster_tool_success() -> None:
    ctx = _setup_mock_cluster_context()

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=ctx["client"]):
        res = get_cluster_tool("ProdCluster")

    assert isinstance(res, ClusterDetail)
    assert res.id == "c-1"
    assert res.name == "ProdCluster"
    assert res.memory_overcommit_percent == 150
    assert res.bios_type == "q35_secure_boot"
    assert res.migration_encrypted is True
    assert res.fencing_enabled is True


def test_get_cluster_tool_not_found() -> None:
    ctx = _setup_mock_cluster_context()
    ctx["client"].find_resource_by_id_or_name.return_value = None

    with (
        patch("ovirt_mcp.tools.clusters.get_client", return_value=ctx["client"]),
        pytest.raises(OvirtValidationError),
    ):
        get_cluster_tool("NonExistentCluster")
