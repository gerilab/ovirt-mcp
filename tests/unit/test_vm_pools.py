"""Unit tests for Virtual Machine Pool management tools."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.vm_pool import (
    VmPoolDetail,
    VmPoolResult,
    VmPoolSummary,
)
from ovirt_mcp.tools.vm_pools import (
    _extract_pool_summary,
    allocate_vm_pool_vm_tool,
    create_vm_pool_tool,
    delete_vm_pool_tool,
    get_vm_pool_tool,
    list_vm_pools_tool,
    update_vm_pool_tool,
)


def _safe_mode_config(enabled: bool = True) -> OvirtConfig:
    return OvirtConfig(
        ovirt_url="https://olvm.example.com/ovirt-engine/api",
        ovirt_username="admin@internal",
        ovirt_password=SecretStr("secret"),
        ovirt_insecure=True,
        mcp_safe_mode=enabled,
        mcp_read_only=False,
    )


def test_extract_pool_summary() -> None:
    mock_pool = MagicMock()
    mock_pool.id = "pool-uuid-1"
    mock_pool.name = "DeveloperPool"
    mock_pool.description = "Pool for dev team"
    mock_pool.cluster.id = "c-1"
    mock_pool.cluster.name = "DefaultCluster"
    mock_pool.template.id = "t-1"
    mock_pool.template.name = "RHEL9_Template"
    mock_pool.size = 10
    mock_pool.prestarted_vms = 2
    mock_pool.max_user_vms = 1
    mock_pool.type.value = "automatic"
    mock_pool.stateful = False

    summary = _extract_pool_summary(mock_pool)

    assert isinstance(summary, VmPoolSummary)
    assert summary.id == "pool-uuid-1"
    assert summary.name == "DeveloperPool"
    assert summary.cluster_name == "DefaultCluster"
    assert summary.template_name == "RHEL9_Template"
    assert summary.size == 10
    assert summary.prestarted_vms == 2
    assert summary.max_user_vms == 1
    assert summary.type == "automatic"


def test_list_vm_pools_tool() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_pools_svc = MagicMock()
    mock_clusters_svc = MagicMock()
    mock_templates_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vm_pools_service.return_value = mock_pools_svc
    mock_sys.clusters_service.return_value = mock_clusters_svc
    mock_sys.templates_service.return_value = mock_templates_svc

    mock_clusters_svc.list.return_value = []
    mock_templates_svc.list.return_value = []

    mock_p1 = MagicMock()
    mock_p1.id = "p-1"
    mock_p1.name = "SalesPool"
    mock_p1.description = "Sales VMs"
    mock_p1.cluster.id = "c-1"
    mock_p1.cluster.name = "Cluster01"
    mock_p1.template.id = "t-1"
    mock_p1.template.name = "Win11_Template"
    mock_p1.size = 5
    mock_p1.prestarted_vms = 1
    mock_p1.max_user_vms = 1
    mock_p1.type.value = "automatic"
    mock_p1.stateful = False

    mock_pools_svc.list.return_value = [mock_p1]

    with patch("ovirt_mcp.tools.vm_pools.get_client", return_value=mock_client):
        res = list_vm_pools_tool()

    assert len(res) == 1
    assert res[0].name == "SalesPool"
    assert res[0].size == 5


def test_get_vm_pool_tool() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_pools_svc = MagicMock()
    mock_vms_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vm_pools_service.return_value = mock_pools_svc
    mock_sys.vms_service.return_value = mock_vms_svc

    mock_p = MagicMock()
    mock_p.id = "p-2"
    mock_p.name = "QAPool"
    mock_p.cluster.id = "c-1"
    mock_p.cluster.name = "Cluster01"
    mock_p.template.id = "t-1"
    mock_p.template.name = "Template01"
    mock_p.size = 3
    mock_p.prestarted_vms = 1
    mock_p.max_user_vms = 1
    mock_p.type.value = "automatic"
    mock_p.stateful = False
    mock_client.find_resource_by_id_or_name.return_value = mock_p

    # Member VMs
    mock_vm1 = MagicMock(id="vm-1")
    mock_vm1.name = "QAPool-1"
    mock_vm1.status.value = "up"
    mock_vm2 = MagicMock(id="vm-2")
    mock_vm2.name = "QAPool-2"
    mock_vm2.status.value = "down"
    mock_vms_svc.list.return_value = [mock_vm1, mock_vm2]

    with patch("ovirt_mcp.tools.vm_pools.get_client", return_value=mock_client):
        detail = get_vm_pool_tool("QAPool")

    assert isinstance(detail, VmPoolDetail)
    assert detail.name == "QAPool"
    assert len(detail.vms) == 2
    assert detail.allocated_vms_count == 1


def test_create_vm_pool_safe_mode() -> None:
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        create_vm_pool_tool(
            name="NewPool",
            cluster="Cluster01",
            template="Tpl01",
            size=5,
            confirm=False,
        )


def test_create_vm_pool_validation_errors() -> None:
    with pytest.raises(OvirtValidationError, match="VM pool name cannot be empty"):
        create_vm_pool_tool(name="  ", cluster="c", template="t")

    with pytest.raises(OvirtValidationError, match="size must be at least 1"):
        create_vm_pool_tool(name="p", cluster="c", template="t", size=0)

    with pytest.raises(OvirtValidationError, match="Prestarted VMs"):
        create_vm_pool_tool(name="p", cluster="c", template="t", size=2, prestarted_vms=5)


def test_create_vm_pool_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_pools_svc = MagicMock()
    mock_clusters_svc = MagicMock()
    mock_templates_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vm_pools_service.return_value = mock_pools_svc
    mock_sys.clusters_service.return_value = mock_clusters_svc
    mock_sys.templates_service.return_value = mock_templates_svc

    mock_cluster = MagicMock(id="c-uuid", name="Cluster01")
    mock_template = MagicMock(id="t-uuid", name="Tpl01")
    mock_client.find_resource_by_id_or_name.side_effect = [mock_cluster, mock_template]

    mock_new_pool = MagicMock(id="new-pool-123")
    mock_pools_svc.add.return_value = mock_new_pool

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.vm_pools.get_client", return_value=mock_client),
    ):
        res = create_vm_pool_tool(
            name="DevTeamPool",
            cluster="Cluster01",
            template="Tpl01",
            size=3,
            prestarted_vms=1,
            confirm=True,
        )

    assert isinstance(res, VmPoolResult)
    assert res.success is True
    assert res.action == "create"
    assert res.pool_id == "new-pool-123"
    mock_pools_svc.add.assert_called_once()


def test_update_vm_pool_safe_mode() -> None:
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        update_vm_pool_tool("DevTeamPool", size=10, confirm=False)


def test_update_vm_pool_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_pools_svc = MagicMock()
    mock_pool_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vm_pools_service.return_value = mock_pools_svc
    mock_pools_svc.pool_service.return_value = mock_pool_svc

    mock_pool = MagicMock(id="pool-1", name="DevTeamPool")
    mock_client.find_resource_by_id_or_name.return_value = mock_pool

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.vm_pools.get_client", return_value=mock_client),
    ):
        res = update_vm_pool_tool("DevTeamPool", size=8, prestarted_vms=2, confirm=True)

    assert isinstance(res, VmPoolResult)
    assert res.success is True
    assert res.action == "update"
    mock_pool_svc.update.assert_called_once()


def test_delete_vm_pool_safe_mode() -> None:
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        delete_vm_pool_tool("DevTeamPool", confirm=False)


def test_delete_vm_pool_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_pools_svc = MagicMock()
    mock_pool_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vm_pools_service.return_value = mock_pools_svc
    mock_pools_svc.pool_service.return_value = mock_pool_svc

    mock_pool = MagicMock(id="pool-del", name="OldPool")
    mock_client.find_resource_by_id_or_name.return_value = mock_pool

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.vm_pools.get_client", return_value=mock_client),
    ):
        res = delete_vm_pool_tool("OldPool", confirm=True)

    assert isinstance(res, VmPoolResult)
    assert res.success is True
    assert res.action == "delete"
    mock_pool_svc.remove.assert_called_once()


def test_allocate_vm_pool_vm_tool() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_pools_svc = MagicMock()
    mock_pool_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vm_pools_service.return_value = mock_pools_svc
    mock_pools_svc.pool_service.return_value = mock_pool_svc

    mock_pool = MagicMock(id="pool-alloc", name="DevTeamPool")
    mock_client.find_resource_by_id_or_name.return_value = mock_pool

    mock_alloc_vm = MagicMock(id="assigned-vm-1")
    mock_alloc_vm.name = "DevTeamPool-1"
    mock_pool_svc.allocate_vm.return_value = mock_alloc_vm

    with patch("ovirt_mcp.tools.vm_pools.get_client", return_value=mock_client):
        res = allocate_vm_pool_vm_tool("DevTeamPool")

    assert isinstance(res, VmPoolResult)
    assert res.success is True
    assert res.action == "allocate_vm"
    assert res.allocated_vm_name == "DevTeamPool-1"
    assert res.allocated_vm_id == "assigned-vm-1"
    mock_pool_svc.allocate_vm.assert_called_once()
