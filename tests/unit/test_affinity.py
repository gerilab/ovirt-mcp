"""Unit tests for Affinity Labels and Cluster Affinity Groups tools."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import (
    OvirtPermissionError,
    OvirtValidationError,
)
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.affinity import (
    AffinityGroupInfo,
    AffinityGroupResult,
    AffinityLabelInfo,
    AffinityLabelResult,
    EntityLabelResult,
)
from ovirt_mcp.tools.affinity import (
    ovirt_affinity_label_create,
    ovirt_affinity_label_delete,
    ovirt_affinity_label_list,
    ovirt_cluster_affinity_group_create,
    ovirt_cluster_affinity_group_delete,
    ovirt_cluster_affinity_group_list,
    ovirt_host_label_assign,
    ovirt_host_label_list,
    ovirt_host_label_unassign,
    ovirt_vm_label_assign,
    ovirt_vm_label_list,
    ovirt_vm_label_unassign,
)


@pytest.fixture
def mock_client() -> tuple[MagicMock, MagicMock]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys

    # Mock collections
    mock_labels_svc = MagicMock()
    mock_hosts_svc = MagicMock()
    mock_vms_svc = MagicMock()
    mock_clusters_svc = MagicMock()

    mock_sys.affinity_labels_service.return_value = mock_labels_svc
    mock_sys.hosts_service.return_value = mock_hosts_svc
    mock_sys.vms_service.return_value = mock_vms_svc
    mock_sys.clusters_service.return_value = mock_clusters_svc

    mock_hosts_svc.list.return_value = []
    mock_vms_svc.list.return_value = []
    mock_labels_svc.list.return_value = []
    mock_clusters_svc.list.return_value = []

    return mock_client, mock_sys


# =========================================================================
# 1. Global Affinity Labels Tests
# =========================================================================


def test_list_affinity_labels(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    labels_svc = sys_svc.affinity_labels_service.return_value

    lbl = MagicMock()
    lbl.id = "lbl-123"
    lbl.name = "db-nodes"
    labels_svc.list.return_value = [lbl]

    single_lbl_svc = MagicMock()
    labels_svc.label_service.return_value = single_lbl_svc

    mock_host_ref = MagicMock()
    mock_host_ref.id = "host-1"
    mock_host_ref.name = "olvmhost001"
    single_lbl_svc.hosts_service.return_value.list.return_value = [mock_host_ref]

    mock_vm_ref = MagicMock()
    mock_vm_ref.id = "vm-1"
    mock_vm_ref.name = "testvm001"
    single_lbl_svc.vms_service.return_value.list.return_value = [mock_vm_ref]

    with patch("ovirt_mcp.tools.affinity.get_client", return_value=client):
        result = ovirt_affinity_label_list()

    assert len(result) == 1
    assert isinstance(result[0], AffinityLabelInfo)
    assert result[0].name == "db-nodes"
    assert "olvmhost001" in result[0].hosts
    assert "testvm001" in result[0].vms


def test_create_affinity_label_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    labels_svc = sys_svc.affinity_labels_service.return_value
    labels_svc.list.return_value = []

    created_lbl = MagicMock()
    created_lbl.id = "lbl-new-uuid"
    created_lbl.name = "web-tier"
    labels_svc.add.return_value = created_lbl

    with patch("ovirt_mcp.tools.affinity.get_client", return_value=client):
        result = ovirt_affinity_label_create("web-tier")

    assert isinstance(result, AffinityLabelResult)
    assert result.success is True
    assert result.label_name == "web-tier"
    assert result.label_id == "lbl-new-uuid"


def test_create_affinity_label_empty_raises(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, _ = mock_client
    with (
        patch("ovirt_mcp.tools.affinity.get_client", return_value=client),
        pytest.raises(OvirtValidationError, match="must not be empty"),
    ):
        ovirt_affinity_label_create("   ")


def test_create_affinity_label_duplicate_raises(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    labels_svc = sys_svc.affinity_labels_service.return_value
    existing = MagicMock()
    existing.id = "lbl-123"
    existing.name = "existing-label"
    labels_svc.list.return_value = [existing]

    with (
        patch("ovirt_mcp.tools.affinity.get_client", return_value=client),
        pytest.raises(OvirtValidationError, match="already exists"),
    ):
        ovirt_affinity_label_create("existing-label")


def test_delete_affinity_label_unconfirmed_raises(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, _ = mock_client
    with (
        patch("ovirt_mcp.tools.affinity.get_client", return_value=client),
        patch(
            "ovirt_mcp.tools.guards.get_config",
            return_value=OvirtConfig(mcp_safe_mode=True),
        ),
        pytest.raises(OvirtValidationError, match="safe mode is enabled"),
    ):
        ovirt_affinity_label_delete("lbl-123", confirm=False)


def test_delete_affinity_label_with_entities_blocks_without_detach(
    mock_client: tuple[MagicMock, MagicMock],
) -> None:
    client, sys_svc = mock_client
    labels_svc = sys_svc.affinity_labels_service.return_value

    lbl = MagicMock()
    lbl.id = "lbl-123"
    lbl.name = "db-label"
    labels_svc.list.return_value = [lbl]

    single_svc = MagicMock()
    labels_svc.label_service.return_value = single_svc
    mock_host = MagicMock()
    mock_host.id = "host-1"
    single_svc.hosts_service.return_value.list.return_value = [mock_host]
    single_svc.vms_service.return_value.list.return_value = []

    with (
        patch("ovirt_mcp.tools.affinity.get_client", return_value=client),
        patch(
            "ovirt_mcp.tools.guards.get_config",
            return_value=OvirtConfig(mcp_safe_mode=False),
        ),
        pytest.raises(OvirtValidationError, match="detach_first=True"),
    ):
        ovirt_affinity_label_delete("db-label", confirm=True, detach_first=False)


def test_delete_affinity_label_with_detach_first(
    mock_client: tuple[MagicMock, MagicMock],
) -> None:
    client, sys_svc = mock_client
    labels_svc = sys_svc.affinity_labels_service.return_value

    lbl = MagicMock()
    lbl.id = "lbl-123"
    lbl.name = "db-label"
    labels_svc.list.return_value = [lbl]

    single_svc = MagicMock()
    labels_svc.label_service.return_value = single_svc
    mock_host = MagicMock()
    mock_host.id = "host-1"
    single_svc.hosts_service.return_value.list.return_value = [mock_host]
    single_svc.vms_service.return_value.list.return_value = []

    with (
        patch("ovirt_mcp.tools.affinity.get_client", return_value=client),
        patch(
            "ovirt_mcp.tools.guards.get_config",
            return_value=OvirtConfig(mcp_safe_mode=False),
        ),
    ):
        res = ovirt_affinity_label_delete("db-label", confirm=True, detach_first=True)

    assert res.success is True
    assert res.action == "delete"
    single_svc.hosts_service.return_value.host_service("host-1").remove.assert_called_once()
    single_svc.remove.assert_called_once()


# =========================================================================
# 2. Host Affinity Labels Tests
# =========================================================================


def test_host_label_list(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    hosts_svc = sys_svc.hosts_service.return_value

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost002"
    client.find_resource_by_id_or_name.return_value = mock_host

    mock_lbl = MagicMock()
    mock_lbl.name = "gpu-node"
    hosts_svc.host_service.return_value.affinity_labels_service.return_value.list.return_value = [
        mock_lbl
    ]

    with patch("ovirt_mcp.tools.affinity.get_client", return_value=client):
        labels = ovirt_host_label_list("olvmhost002")

    assert labels == ["gpu-node"]


def test_host_label_assign_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    hosts_svc = sys_svc.hosts_service.return_value
    labels_svc = sys_svc.affinity_labels_service.return_value

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost002"
    client.find_resource_by_id_or_name.return_value = mock_host

    mock_lbl = MagicMock()
    mock_lbl.id = "lbl-gpu"
    mock_lbl.name = "gpu-node"
    labels_svc.list.return_value = [mock_lbl]

    h_labels_svc = hosts_svc.host_service.return_value.affinity_labels_service.return_value
    h_labels_svc.list.side_effect = [[], [mock_lbl]]

    with patch("ovirt_mcp.tools.affinity.get_client", return_value=client):
        res = ovirt_host_label_assign("olvmhost002", "gpu-node")

    assert isinstance(res, EntityLabelResult)
    assert res.success is True
    assert res.action == "assign"
    assert "gpu-node" in res.current_labels
    h_labels_svc.add.assert_called_once()


def test_host_label_unassign_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    hosts_svc = sys_svc.hosts_service.return_value
    labels_svc = sys_svc.affinity_labels_service.return_value

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost002"
    client.find_resource_by_id_or_name.return_value = mock_host

    mock_lbl = MagicMock()
    mock_lbl.id = "lbl-gpu"
    mock_lbl.name = "gpu-node"
    labels_svc.list.return_value = [mock_lbl]

    h_labels_svc = hosts_svc.host_service.return_value.affinity_labels_service.return_value
    h_labels_svc.list.side_effect = [[mock_lbl], []]

    with patch("ovirt_mcp.tools.affinity.get_client", return_value=client):
        res = ovirt_host_label_unassign("olvmhost002", "gpu-node")

    assert res.success is True
    assert res.action == "unassign"
    assert res.current_labels == []
    h_labels_svc.label_service(mock_lbl.id).remove.assert_called_once()


# =========================================================================
# 3. VM Affinity Labels Tests
# =========================================================================


def test_vm_label_list(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    vms_svc = sys_svc.vms_service.return_value

    mock_vm = MagicMock()
    mock_vm.id = "vm-1"
    mock_vm.name = "testvm001"
    client.find_resource_by_id_or_name.return_value = mock_vm

    mock_lbl = MagicMock()
    mock_lbl.name = "prod-tier"
    vms_svc.vm_service.return_value.affinity_labels_service.return_value.list.return_value = [
        mock_lbl
    ]

    with patch("ovirt_mcp.tools.affinity.get_client", return_value=client):
        labels = ovirt_vm_label_list("testvm001")

    assert labels == ["prod-tier"]


def test_vm_label_assign_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    vms_svc = sys_svc.vms_service.return_value
    labels_svc = sys_svc.affinity_labels_service.return_value

    mock_vm = MagicMock()
    mock_vm.id = "vm-1"
    mock_vm.name = "testvm001"
    client.find_resource_by_id_or_name.return_value = mock_vm

    mock_lbl = MagicMock()
    mock_lbl.id = "lbl-prod"
    mock_lbl.name = "prod-tier"
    labels_svc.list.return_value = [mock_lbl]

    v_labels_svc = vms_svc.vm_service.return_value.affinity_labels_service.return_value
    v_labels_svc.list.side_effect = [[], [mock_lbl]]

    with patch("ovirt_mcp.tools.affinity.get_client", return_value=client):
        res = ovirt_vm_label_assign("testvm001", "prod-tier")

    assert res.success is True
    assert res.action == "assign"
    assert "prod-tier" in res.current_labels
    v_labels_svc.add.assert_called_once()


def test_vm_label_unassign_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    vms_svc = sys_svc.vms_service.return_value
    labels_svc = sys_svc.affinity_labels_service.return_value

    mock_vm = MagicMock()
    mock_vm.id = "vm-1"
    mock_vm.name = "testvm001"
    client.find_resource_by_id_or_name.return_value = mock_vm

    mock_lbl = MagicMock()
    mock_lbl.id = "lbl-prod"
    mock_lbl.name = "prod-tier"
    labels_svc.list.return_value = [mock_lbl]

    v_labels_svc = vms_svc.vm_service.return_value.affinity_labels_service.return_value
    v_labels_svc.list.side_effect = [[mock_lbl], []]

    with patch("ovirt_mcp.tools.affinity.get_client", return_value=client):
        res = ovirt_vm_label_unassign("testvm001", "prod-tier")

    assert res.success is True
    assert res.action == "unassign"
    assert res.current_labels == []
    v_labels_svc.label_service(mock_lbl.id).remove.assert_called_once()


# =========================================================================
# 4. Cluster Affinity Groups Tests
# =========================================================================


def test_cluster_affinity_group_list(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    clusters_svc = sys_svc.clusters_service.return_value

    mock_cluster = MagicMock()
    mock_cluster.id = "cluster-1"
    mock_cluster.name = "DefaultCluster"
    client.find_resource_by_id_or_name.return_value = mock_cluster

    c_svc = MagicMock()
    clusters_svc.cluster_service.return_value = c_svc
    ag_svc = MagicMock()
    c_svc.affinity_groups_service.return_value = ag_svc

    mock_ag = MagicMock()
    mock_ag.id = "ag-1"
    mock_ag.name = "db-anti-affinity"
    mock_ag.description = "Keep DB VMs on separate hosts"
    mock_ag.priority = 1.0
    mock_ag.vms_rule.enabled = True
    mock_ag.vms_rule.positive = False
    mock_ag.vms_rule.enforcing = True
    mock_ag.hosts_rule = None
    ag_svc.list.return_value = [mock_ag]

    single_ag_svc = MagicMock()
    ag_svc.group_service.return_value = single_ag_svc
    single_ag_svc.get.return_value = mock_ag
    single_ag_svc.vms_service.return_value.list.return_value = []
    single_ag_svc.hosts_service.return_value.list.return_value = []
    single_ag_svc.vm_labels_service.return_value.list.return_value = []
    single_ag_svc.host_labels_service.return_value.list.return_value = []

    with patch("ovirt_mcp.tools.affinity.get_client", return_value=client):
        groups = ovirt_cluster_affinity_group_list("DefaultCluster")

    assert len(groups) == 1
    assert isinstance(groups[0], AffinityGroupInfo)
    assert groups[0].name == "db-anti-affinity"
    assert groups[0].vms_rule is not None
    assert groups[0].vms_rule.positive is False  # Anti-affinity
    assert groups[0].vms_rule.enforcing is True


def test_cluster_affinity_group_create_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    clusters_svc = sys_svc.clusters_service.return_value

    mock_cluster = MagicMock()
    mock_cluster.id = "cluster-1"
    mock_cluster.name = "DefaultCluster"
    client.find_resource_by_id_or_name.return_value = mock_cluster

    c_svc = MagicMock()
    clusters_svc.cluster_service.return_value = c_svc
    ag_svc = MagicMock()
    c_svc.affinity_groups_service.return_value = ag_svc
    ag_svc.list.return_value = []

    created_ag = MagicMock()
    created_ag.id = "ag-new-123"
    created_ag.name = "app-anti-affinity"
    ag_svc.add.return_value = created_ag

    with patch("ovirt_mcp.tools.affinity.get_client", return_value=client):
        res = ovirt_cluster_affinity_group_create(
            cluster_name_or_id="DefaultCluster",
            name="app-anti-affinity",
            description="Anti affinity group for app nodes",
            vm_positive=False,
            vm_enforcing=True,
        )

    assert isinstance(res, AffinityGroupResult)
    assert res.success is True
    assert res.action == "create"
    assert res.group_name == "app-anti-affinity"
    assert res.group_id == "ag-new-123"
    ag_svc.add.assert_called_once()


def test_cluster_affinity_group_create_duplicate_raises(
    mock_client: tuple[MagicMock, MagicMock],
) -> None:
    client, sys_svc = mock_client
    clusters_svc = sys_svc.clusters_service.return_value

    mock_cluster = MagicMock()
    mock_cluster.id = "cluster-1"
    mock_cluster.name = "DefaultCluster"
    client.find_resource_by_id_or_name.return_value = mock_cluster

    c_svc = MagicMock()
    clusters_svc.cluster_service.return_value = c_svc
    ag_svc = MagicMock()
    c_svc.affinity_groups_service.return_value = ag_svc

    existing = MagicMock()
    existing.name = "existing-group"
    ag_svc.list.return_value = [existing]

    with (
        patch("ovirt_mcp.tools.affinity.get_client", return_value=client),
        pytest.raises(OvirtValidationError, match="already exists"),
    ):
        ovirt_cluster_affinity_group_create(
            cluster_name_or_id="DefaultCluster",
            name="existing-group",
        )


def test_cluster_affinity_group_delete_unconfirmed_raises(
    mock_client: tuple[MagicMock, MagicMock],
) -> None:
    client, _ = mock_client
    with (
        patch("ovirt_mcp.tools.affinity.get_client", return_value=client),
        patch(
            "ovirt_mcp.tools.guards.get_config",
            return_value=OvirtConfig(mcp_safe_mode=True),
        ),
        pytest.raises(OvirtValidationError, match="safe mode is enabled"),
    ):
        ovirt_cluster_affinity_group_delete("DefaultCluster", "ag-1", confirm=False)


def test_cluster_affinity_group_delete_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    clusters_svc = sys_svc.clusters_service.return_value

    mock_cluster = MagicMock()
    mock_cluster.id = "cluster-1"
    mock_cluster.name = "DefaultCluster"
    client.find_resource_by_id_or_name.return_value = mock_cluster

    c_svc = MagicMock()
    clusters_svc.cluster_service.return_value = c_svc
    ag_svc = MagicMock()
    c_svc.affinity_groups_service.return_value = ag_svc

    mock_ag = MagicMock()
    mock_ag.id = "ag-1"
    mock_ag.name = "del-group"
    ag_svc.list.return_value = [mock_ag]

    single_svc = MagicMock()
    ag_svc.group_service.return_value = single_svc

    with (
        patch("ovirt_mcp.tools.affinity.get_client", return_value=client),
        patch(
            "ovirt_mcp.tools.guards.get_config",
            return_value=OvirtConfig(mcp_safe_mode=False),
        ),
    ):
        res = ovirt_cluster_affinity_group_delete("DefaultCluster", "del-group", confirm=True)

    assert res.success is True
    assert res.action == "delete"
    single_svc.remove.assert_called_once()


def test_read_only_mode_blocks_affinity_mutations(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, _ = mock_client
    with (
        patch("ovirt_mcp.tools.affinity.get_client", return_value=client),
        patch(
            "ovirt_mcp.tools.guards.get_config",
            return_value=OvirtConfig(mcp_read_only=True),
        ),
    ):
        with pytest.raises(OvirtPermissionError, match="read-only mode"):
            ovirt_affinity_label_create("test-lbl")

        with pytest.raises(OvirtPermissionError, match="read-only mode"):
            ovirt_host_label_assign("host-1", "test-lbl")

        with pytest.raises(OvirtPermissionError, match="read-only mode"):
            ovirt_vm_label_assign("vm-1", "test-lbl")

        with pytest.raises(OvirtPermissionError, match="read-only mode"):
            ovirt_cluster_affinity_group_create("c-1", "ag-test")
