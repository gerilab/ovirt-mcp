"""Unit tests for virtual machine creation (ovirt_vm_create)."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import NotFoundError, OvirtMCPError, OvirtPermissionError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.vm import VmCreateResult
from ovirt_mcp.tools.vms import create_vm_tool


def test_create_vm_success() -> None:
    """Test standard VM creation from Blank template."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_clusters_service = MagicMock()
    mock_templates_service = MagicMock()
    mock_vms_service = MagicMock()

    mock_cluster = MagicMock()
    mock_cluster.id = "cl-uuid-1"
    mock_cluster.name = "ProdCluster"

    mock_template = MagicMock()
    mock_template.id = "tmpl-uuid-1"
    mock_template.name = "Blank"

    mock_created_vm = MagicMock()
    mock_created_vm.id = "new-vm-uuid-123"
    mock_created_vm.name = "test-node-01"
    mock_created_vm.status.value = "down"

    mock_system.clusters_service.return_value = mock_clusters_service
    mock_system.templates_service.return_value = mock_templates_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    def mock_find(service: MagicMock, identifier: str, res_type: str) -> MagicMock:
        if res_type == "cluster":
            return mock_cluster
        if res_type == "template":
            return mock_template
        return MagicMock()

    mock_client.find_resource_by_id_or_name.side_effect = mock_find
    mock_vms_service.add.return_value = mock_created_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = create_vm_tool(
            name="test-node-01",
            cluster="ProdCluster",
            template="Blank",
            memory_mb=4096,
            cpu_cores=2,
            cpu_sockets=1,
            description="Test VM",
        )
        assert isinstance(res, VmCreateResult)
        assert res.success is True
        assert res.vm_id == "new-vm-uuid-123"
        assert res.vm_name == "test-node-01"
        assert res.cluster_name == "ProdCluster"
        assert res.template_name == "Blank"
        assert res.memory_mb == 4096
        assert res.cpu_cores == 2
        mock_vms_service.add.assert_called_once()


def test_create_vm_with_disk_and_nic() -> None:
    """Test VM creation including disk provisioning and network interface."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_clusters_service = MagicMock()
    mock_templates_service = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()
    mock_disk_att_service = MagicMock()
    mock_nics_service = MagicMock()
    mock_sds_service = MagicMock()
    mock_vnics_service = MagicMock()

    mock_cluster = MagicMock(id="cl-1", name="ProdCluster")
    mock_template = MagicMock(id="tmpl-1", name="Blank")
    mock_sd = MagicMock(id="sd-1", name="data-domain")
    mock_vnic = MagicMock(id="vnic-1", name="ovirtmgmt")
    mock_created_vm = MagicMock(id="vm-999", name="db-node")
    mock_created_vm.status.value = "down"

    mock_vm_service.disk_attachments_service.return_value = mock_disk_att_service
    mock_vm_service.nics_service.return_value = mock_nics_service
    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_vms_service.add.return_value = mock_created_vm

    mock_system.clusters_service.return_value = mock_clusters_service
    mock_system.templates_service.return_value = mock_templates_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_system.storage_domains_service.return_value = mock_sds_service
    mock_system.vnic_profiles_service.return_value = mock_vnics_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    def mock_find(service: MagicMock, identifier: str, res_type: str) -> MagicMock:
        if res_type == "cluster":
            return mock_cluster
        if res_type == "template":
            return mock_template
        if res_type == "storage_domain":
            return mock_sd
        if res_type == "vnic_profile":
            return mock_vnic
        return MagicMock()

    mock_client.find_resource_by_id_or_name.side_effect = mock_find

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = create_vm_tool(
            name="db-node",
            cluster="ProdCluster",
            disk_size_gb=50,
            storage_domain="data-domain",
            network_profile="ovirtmgmt",
        )
        assert res.success is True
        assert res.vm_name == "db-node"
        mock_disk_att_service.add.assert_called_once()
        mock_nics_service.add.assert_called_once()


def test_create_vm_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test VM creation blocked when MCP_READ_ONLY=true."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        create_vm_tool(name="new-vm", cluster="Default")
    assert "read-only mode" in str(exc_info.value)


def test_create_vm_cluster_not_found() -> None:
    """Test exception when cluster cannot be found."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.side_effect = NotFoundError("cluster", "NonExistent")

    with (
        patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client),
        pytest.raises(NotFoundError),
    ):
        create_vm_tool(name="new-vm", cluster="NonExistent")


def test_create_vm_sdk_error() -> None:
    """Test mapping SDK error during add to OvirtMCPError."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()

    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    mock_cluster = MagicMock(id="cl-1", name="ProdCluster")
    mock_template = MagicMock(id="tmpl-1", name="Blank")
    mock_client.find_resource_by_id_or_name.side_effect = [mock_cluster, mock_template]

    mock_vms_service.add.side_effect = RuntimeError("Storage domain out of space")

    with (
        patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client),
        pytest.raises(OvirtMCPError) as exc_info,
    ):
        create_vm_tool(name="new-vm", cluster="ProdCluster")
    assert "Storage domain out of space" in str(exc_info.value)
