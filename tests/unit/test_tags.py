"""Unit tests for Inventory Tags and tag assignment tools."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.tag import (
    TagAssignmentResult,
    TagResult,
    TagSummary,
)
from ovirt_mcp.tools.tags import (
    ROOT_TAG_ID,
    assign_host_tag_tool,
    assign_user_tag_tool,
    assign_vm_tag_tool,
    create_tag_tool,
    delete_tag_tool,
    list_tags_tool,
    list_user_tags_tool,
    unassign_host_tag_tool,
    unassign_user_tag_tool,
    unassign_vm_tag_tool,
)


def test_list_tags_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_tags_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.tags_service.return_value = mock_tags_svc

    mock_t1 = MagicMock()
    mock_t1.id = "t-1"
    mock_t1.name = "Production"
    mock_t1.description = "Production workloads"
    mock_t1.parent = None

    mock_tags_svc.list.return_value = [mock_t1]

    with patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client):
        res = list_tags_tool()

    assert len(res) == 1
    assert isinstance(res[0], TagSummary)
    assert res[0].id == "t-1"
    assert res[0].name == "Production"


def test_create_tag_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_tags_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.tags_service.return_value = mock_tags_svc
    mock_tags_svc.list.return_value = []

    mock_created = MagicMock()
    mock_created.id = "new-t-id"
    mock_tags_svc.add.return_value = mock_created

    with patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client):
        res = create_tag_tool("Staging", description="Staging environment")

    assert isinstance(res, TagResult)
    assert res.success is True
    assert res.tag_id == "new-t-id"
    assert res.tag_name == "Staging"
    mock_tags_svc.add.assert_called_once()


def test_create_tag_duplicate_guard() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_tags_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.tags_service.return_value = mock_tags_svc

    mock_existing = MagicMock()
    mock_existing.id = "existing-id"
    mock_existing.name = "Production"
    mock_tags_svc.list.return_value = [mock_existing]

    with (
        patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="already exists"),
    ):
        create_tag_tool("Production")


def test_delete_tag_root_guard() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_tags_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.tags_service.return_value = mock_tags_svc

    mock_root = MagicMock()
    mock_root.id = ROOT_TAG_ID
    mock_root.name = "root"
    mock_client.find_resource_by_id_or_name.return_value = mock_root

    with (
        patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="Cannot delete system root tag"),
    ):
        delete_tag_tool("root", confirm=True)


def test_delete_tag_safe_mode_guard() -> None:
    mock_cfg = OvirtConfig(
        ovirt_url="https://olvm.example.com",
        ovirt_username="admin@internal",
        ovirt_password=SecretStr("pwd"),
        mcp_safe_mode=True,
    )
    with (
        patch("ovirt_mcp.config.get_config", return_value=mock_cfg),
        patch("ovirt_mcp.tools.guards.get_config", return_value=mock_cfg),
        pytest.raises(OvirtValidationError, match="Operation 'ovirt_tag_delete' is destructive"),
    ):
        delete_tag_tool("CustomTag", confirm=False)


def test_assign_vm_tag_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_vms_svc = MagicMock()
    mock_tags_svc = MagicMock()
    mock_vm_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vms_service.return_value = mock_vms_svc
    mock_sys.tags_service.return_value = mock_tags_svc
    mock_vms_svc.vm_service.return_value = mock_vm_svc
    mock_vm_svc.tags_service().list.return_value = []

    mock_vm = MagicMock()
    mock_vm.id = "vm-1"
    mock_vm.name = "app-server-01"

    mock_tag = MagicMock()
    mock_tag.id = "t-1"
    mock_tag.name = "Production"

    mock_client.find_resource_by_id_or_name.side_effect = lambda svc, ident, res_type: (
        mock_vm if res_type == "vm" else mock_tag
    )

    with patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client):
        res = assign_vm_tag_tool("app-server-01", "Production")

    assert isinstance(res, TagAssignmentResult)
    assert res.success is True
    assert res.action == "assign"
    assert res.entity_name == "app-server-01"
    assert res.tag_name == "Production"
    mock_vm_svc.tags_service().add.assert_called_once()


def test_unassign_vm_tag_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_vms_svc = MagicMock()
    mock_tags_svc = MagicMock()
    mock_vm_svc = MagicMock()
    mock_vm_tag_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vms_service.return_value = mock_vms_svc
    mock_sys.tags_service.return_value = mock_tags_svc
    mock_vms_svc.vm_service.return_value = mock_vm_svc
    mock_vm_svc.tags_service().tag_service.return_value = mock_vm_tag_svc

    mock_vm = MagicMock()
    mock_vm.id = "vm-1"
    mock_vm.name = "app-server-01"

    mock_tag = MagicMock()
    mock_tag.id = "t-1"
    mock_tag.name = "Production"

    mock_client.find_resource_by_id_or_name.side_effect = lambda svc, ident, res_type: (
        mock_vm if res_type == "vm" else mock_tag
    )

    with patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client):
        res = unassign_vm_tag_tool("app-server-01", "Production")

    assert isinstance(res, TagAssignmentResult)
    assert res.success is True
    assert res.action == "unassign"
    mock_vm_tag_svc.remove.assert_called_once()


def test_assign_host_tag_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_hosts_svc = MagicMock()
    mock_tags_svc = MagicMock()
    mock_h_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.hosts_service.return_value = mock_hosts_svc
    mock_sys.tags_service.return_value = mock_tags_svc
    mock_hosts_svc.host_service.return_value = mock_h_svc
    mock_h_svc.tags_service().list.return_value = []

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost001"

    mock_tag = MagicMock()
    mock_tag.id = "t-1"
    mock_tag.name = "HypervisorNode"

    mock_client.find_resource_by_id_or_name.side_effect = lambda svc, ident, res_type: (
        mock_host if res_type == "host" else mock_tag
    )

    with patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client):
        res = assign_host_tag_tool("olvmhost001", "HypervisorNode")

    assert isinstance(res, TagAssignmentResult)
    assert res.success is True
    assert res.entity_name == "olvmhost001"
    mock_h_svc.tags_service().add.assert_called_once()


def test_unassign_host_tag_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_hosts_svc = MagicMock()
    mock_tags_svc = MagicMock()
    mock_h_svc = MagicMock()
    mock_h_tag_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.hosts_service.return_value = mock_hosts_svc
    mock_sys.tags_service.return_value = mock_tags_svc
    mock_hosts_svc.host_service.return_value = mock_h_svc
    mock_h_svc.tags_service().tag_service.return_value = mock_h_tag_svc

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost001"

    mock_tag = MagicMock()
    mock_tag.id = "t-1"
    mock_tag.name = "HypervisorNode"

    mock_client.find_resource_by_id_or_name.side_effect = lambda svc, ident, res_type: (
        mock_host if res_type == "host" else mock_tag
    )

    with patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client):
        res = unassign_host_tag_tool("olvmhost001", "HypervisorNode")

    assert isinstance(res, TagAssignmentResult)
    assert res.success is True
    assert res.action == "unassign"
    mock_h_tag_svc.remove.assert_called_once()


def test_list_user_tags_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()
    mock_u_svc = MagicMock()
    mock_u_tags_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc
    mock_users_svc.user_service.return_value = mock_u_svc
    mock_u_svc.tags_service.return_value = mock_u_tags_svc

    mock_user = MagicMock()
    mock_user.id = "u-1"
    mock_user.user_name = "admin@internal"
    mock_client.find_resource_by_id_or_name.return_value = mock_user

    mock_tag = MagicMock()
    mock_tag.id = "t-1"
    mock_tag.name = "Admins"
    mock_tag.description = "Admin users"
    mock_tag.parent = None
    mock_u_tags_svc.list.return_value = [mock_tag]

    with patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client):
        res = list_user_tags_tool("admin@internal")

    assert len(res) == 1
    assert isinstance(res[0], TagSummary)
    assert res[0].id == "t-1"
    assert res[0].name == "Admins"


def test_assign_user_tag_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()
    mock_tags_svc = MagicMock()
    mock_u_svc = MagicMock()
    mock_u_tags_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc
    mock_sys.tags_service.return_value = mock_tags_svc
    mock_users_svc.user_service.return_value = mock_u_svc
    mock_u_svc.tags_service.return_value = mock_u_tags_svc
    mock_u_tags_svc.list.return_value = []

    mock_user = MagicMock()
    mock_user.id = "u-1"
    mock_user.user_name = "admin@internal"

    mock_tag = MagicMock()
    mock_tag.id = "t-1"
    mock_tag.name = "Admins"

    mock_client.find_resource_by_id_or_name.side_effect = lambda svc, ident, res_type: (
        mock_user if res_type == "user" else mock_tag
    )

    with patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client):
        res = assign_user_tag_tool("admin@internal", "Admins")

    assert isinstance(res, TagAssignmentResult)
    assert res.success is True
    assert res.entity_name == "admin@internal"
    assert res.entity_type == "user"
    mock_u_tags_svc.add.assert_called_once()


def test_unassign_user_tag_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()
    mock_tags_svc = MagicMock()
    mock_u_svc = MagicMock()
    mock_u_tag_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc
    mock_sys.tags_service.return_value = mock_tags_svc
    mock_users_svc.user_service.return_value = mock_u_svc
    mock_u_svc.tags_service().tag_service.return_value = mock_u_tag_svc

    mock_user = MagicMock()
    mock_user.id = "u-1"
    mock_user.user_name = "admin@internal"

    mock_tag = MagicMock()
    mock_tag.id = "t-1"
    mock_tag.name = "Admins"

    mock_client.find_resource_by_id_or_name.side_effect = lambda svc, ident, res_type: (
        mock_user if res_type == "user" else mock_tag
    )

    with patch("ovirt_mcp.tools.tags.get_client", return_value=mock_client):
        res = unassign_user_tag_tool("admin@internal", "Admins")

    assert isinstance(res, TagAssignmentResult)
    assert res.success is True
    assert res.action == "unassign"
    assert res.entity_type == "user"
    mock_u_tag_svc.remove.assert_called_once()
