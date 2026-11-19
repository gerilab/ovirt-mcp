"""Unit tests for oVirt / OLVM users, roles, and authorization permission tools."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.user import (
    PermissionResult,
    PermissionSummary,
    RoleResult,
    UserDetail,
    UserResult,
    UserSummary,
)
from ovirt_mcp.tools.users import (
    _extract_user_summary,
    add_permission_tool,
    add_role_tool,
    add_user_tool,
    delete_role_tool,
    delete_user_tool,
    get_user_tool,
    list_permissions_tool,
    list_roles_tool,
    list_users_tool,
    remove_permission_tool,
)


def _safe_mode_config(enabled: bool = True) -> OvirtConfig:
    """Helper to return an OvirtConfig with safe_mode set."""
    return OvirtConfig(
        ovirt_url="https://olvm.example.com/ovirt-engine/api",
        ovirt_username="admin@internal",
        ovirt_password=SecretStr("secret"),
        ovirt_insecure=True,
        mcp_safe_mode=enabled,
        mcp_read_only=False,
    )


def test_extract_user_summary() -> None:
    """Test extracting UserSummary from mock SDK User object."""
    mock_user = MagicMock()
    mock_user.id = "user-uuid-123"
    mock_user.name = "mcp-service"
    mock_user.user_name = "mcp-service@internal-authz"
    mock_user.principal = "mcp-service"
    mock_domain = MagicMock()
    mock_domain.name = "internal-authz"
    mock_user.domain = mock_domain
    mock_user.email = "mcp@example.com"
    mock_user.department = "DevOps"
    mock_user.logged_in = True

    summary = _extract_user_summary(mock_user)

    assert isinstance(summary, UserSummary)
    assert summary.id == "user-uuid-123"
    assert summary.name == "mcp-service"
    assert summary.user_name == "mcp-service@internal-authz"
    assert summary.principal == "mcp-service"
    assert summary.domain_name == "internal-authz"
    assert summary.email == "mcp@example.com"
    assert summary.department == "DevOps"
    assert summary.logged_in is True


def test_list_users_tool() -> None:
    """Test list_users_tool queries users_service with limit and search query."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc

    mock_u1 = MagicMock()
    mock_u1.id = "u-1"
    mock_u1.name = "admin"
    mock_u1.user_name = "admin@internal-authz"
    mock_u1.domain = MagicMock(name="domain")
    mock_u1.domain.name = "internal-authz"
    mock_u1.logged_in = True

    mock_users_svc.list.return_value = [mock_u1]

    with patch("ovirt_mcp.tools.users.get_client", return_value=mock_client):
        res = list_users_tool(search="usrname = admin*", max_results=25)

    assert len(res) == 1
    assert res[0].user_name == "admin@internal-authz"
    mock_users_svc.list.assert_called_once_with(max=25, search="usrname = admin*")


def test_get_user_tool() -> None:
    """Test get_user_tool retrieves roles and permissions count."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()
    mock_user_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc
    mock_users_svc.user_service.return_value = mock_user_svc

    mock_user = MagicMock()
    mock_user.id = "u-2"
    mock_user.name = "mcp-user"
    mock_user.user_name = "mcp-user@internal-authz"
    mock_user.domain = MagicMock()
    mock_user.domain.name = "internal-authz"
    mock_user.logged_in = False
    mock_client.find_resource_by_id_or_name.return_value = mock_user

    # Mock roles
    mock_role = MagicMock()
    mock_role.name = "UserRole"
    mock_user_svc.roles_service().list.return_value = [mock_role]

    # Mock permissions
    mock_perm = MagicMock()
    mock_user_svc.permissions_service().list.return_value = [mock_perm, mock_perm]

    with patch("ovirt_mcp.tools.users.get_client", return_value=mock_client):
        detail = get_user_tool("mcp-user@internal-authz")

    assert isinstance(detail, UserDetail)
    assert detail.user_name == "mcp-user@internal-authz"
    assert detail.roles == ["UserRole"]
    assert detail.permissions_count == 2


def test_add_user_tool_success() -> None:
    """Test add_user_tool imports user from domain."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc

    mock_created = MagicMock()
    mock_created.id = "new-uuid-777"
    mock_users_svc.add.return_value = mock_created

    with patch("ovirt_mcp.tools.users.get_client", return_value=mock_client):
        res = add_user_tool(
            user_name="mcp-service",
            domain="internal-authz",
            principal="mcp-service",
        )

    assert isinstance(res, UserResult)
    assert res.success is True
    assert res.action == "add"
    assert res.user_id == "new-uuid-777"
    assert res.user_name == "mcp-service@internal-authz"
    mock_users_svc.add.assert_called_once()


def test_delete_user_tool_safe_mode() -> None:
    """Test delete_user_tool enforces Safe Mode confirm=True."""
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        delete_user_tool("test-user@internal-authz", confirm=False)


def test_delete_user_tool_lockout_protection() -> None:
    """Test delete_user_tool blocks deleting admin@ accounts to prevent operator lockout."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc

    mock_admin_user = MagicMock()
    mock_admin_user.id = "admin-uuid"
    mock_admin_user.name = "admin"
    mock_admin_user.user_name = "admin@internal-authz"
    mock_client.find_resource_by_id_or_name.return_value = mock_admin_user

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.users.get_client", return_value=mock_client),
        pytest.raises(
            OvirtValidationError, match="Safety Guard: Deleting root administrative account"
        ),
    ):
        delete_user_tool("admin@internal-authz", confirm=True)


def test_delete_user_tool_success() -> None:
    """Test delete_user_tool removes non-admin user when confirmed."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()
    mock_user_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc
    mock_users_svc.user_service.return_value = mock_user_svc

    mock_user = MagicMock()
    mock_user.id = "u-del"
    mock_user.name = "temp-user"
    mock_user.user_name = "temp-user@internal-authz"
    mock_client.find_resource_by_id_or_name.return_value = mock_user

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.users.get_client", return_value=mock_client),
    ):
        res = delete_user_tool("temp-user@internal-authz", confirm=True)

    assert isinstance(res, UserResult)
    assert res.success is True
    assert res.action == "delete"
    mock_user_svc.remove.assert_called_once()


def test_list_roles_tool() -> None:
    """Test list_roles_tool with and without administrative filter."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_roles_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.roles_service.return_value = mock_roles_svc

    r_admin = MagicMock()
    r_admin.id = "r-1"
    r_admin.name = "SuperUser"
    r_admin.description = "Administrator role"
    r_admin.administrative = True
    r_admin.mutable = False

    r_user = MagicMock()
    r_user.id = "r-2"
    r_user.name = "UserRole"
    r_user.description = "Basic user role"
    r_user.administrative = False
    r_user.mutable = True

    mock_roles_svc.list.return_value = [r_admin, r_user]

    with patch("ovirt_mcp.tools.users.get_client", return_value=mock_client):
        # All roles
        all_roles = list_roles_tool()
        assert len(all_roles) == 2

        # Admin only
        admin_roles = list_roles_tool(administrative=True)
        assert len(admin_roles) == 1
        assert admin_roles[0].name == "SuperUser"

        # User only
        user_roles = list_roles_tool(administrative=False)
        assert len(user_roles) == 1
        assert user_roles[0].name == "UserRole"


def test_list_permissions_tool_system_wide() -> None:
    """Test list_permissions_tool resolves roles and targets."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()
    mock_roles_svc = MagicMock()
    mock_perms_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc
    mock_sys.roles_service.return_value = mock_roles_svc
    mock_sys.permissions_service.return_value = mock_perms_svc

    # Mock role caching
    role_obj = MagicMock()
    role_obj.id = "role-super"
    role_obj.name = "SuperUser"
    mock_roles_svc.list.return_value = [role_obj]

    # Mock permission
    perm_obj = MagicMock()
    perm_obj.id = "perm-1"
    perm_obj.role.id = "role-super"
    perm_obj.user.id = "user-admin"
    perm_obj.user.name = "admin@internal-authz"
    perm_obj.vm = None
    perm_obj.cluster = None
    perm_obj.data_center = None
    perm_obj.storage_domain = None

    mock_perms_svc.list.return_value = [perm_obj]

    with patch("ovirt_mcp.tools.users.get_client", return_value=mock_client):
        perms = list_permissions_tool()

    assert len(perms) == 1
    assert isinstance(perms[0], PermissionSummary)
    assert perms[0].id == "perm-1"
    assert perms[0].role_name == "SuperUser"
    assert perms[0].user_name == "admin@internal-authz"
    assert perms[0].target_type == "system"


def test_list_permissions_tool_entity_resolution() -> None:
    """Test list_permissions_tool correctly identifies target entity types."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()
    mock_roles_svc = MagicMock()
    mock_perms_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc
    mock_sys.roles_service.return_value = mock_roles_svc
    mock_sys.permissions_service.return_value = mock_perms_svc

    mock_roles_svc.list.return_value = []

    # VM target
    p_vm = MagicMock()
    p_vm.id = "p-vm"
    p_vm.role = None
    p_vm.user = None
    vm_obj = MagicMock(id="vm-1")
    vm_obj.name = "testvm001"
    p_vm.vm = vm_obj
    p_vm.cluster = None
    p_vm.data_center = None
    p_vm.storage_domain = None

    # Storage Domain target
    p_sd = MagicMock()
    p_sd.id = "p-sd"
    p_sd.role = None
    p_sd.user = None
    p_sd.vm = None
    p_sd.cluster = None
    p_sd.data_center = None
    sd_obj = MagicMock(id="sd-1")
    sd_obj.name = "Data01"
    p_sd.storage_domain = sd_obj

    mock_perms_svc.list.return_value = [p_vm, p_sd]

    with patch("ovirt_mcp.tools.users.get_client", return_value=mock_client):
        perms = list_permissions_tool()

    assert len(perms) == 2
    assert perms[0].target_type == "vm"
    assert perms[0].target_name == "testvm001"
    assert perms[1].target_type == "storage_domain"
    assert perms[1].target_name == "Data01"


def test_add_permission_tool_admin_safe_mode() -> None:
    """Test add_permission_tool requires confirm=True when assigning administrative roles in Safe Mode."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()
    mock_roles_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc
    mock_sys.roles_service.return_value = mock_roles_svc

    mock_user = MagicMock(id="u-1", user_name="mcp@internal")
    mock_role = MagicMock(id="r-admin", administrative=True)
    mock_role.name = "SuperUser"
    mock_client.find_resource_by_id_or_name.side_effect = [mock_user, mock_role]

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.users.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        add_permission_tool(
            user_name_or_id="mcp@internal",
            role_name_or_id="SuperUser",
            confirm=False,
        )


def test_add_permission_tool_success() -> None:
    """Test add_permission_tool assigns role on VM entity."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_users_svc = MagicMock()
    mock_roles_svc = MagicMock()
    mock_vms_svc = MagicMock()
    mock_perms_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.users_service.return_value = mock_users_svc
    mock_sys.roles_service.return_value = mock_roles_svc
    mock_sys.vms_service.return_value = mock_vms_svc
    mock_sys.permissions_service.return_value = mock_perms_svc

    mock_user = MagicMock(id="u-1", user_name="operator@internal")
    mock_role = MagicMock(id="r-user", administrative=False)
    mock_role.name = "UserRole"
    mock_vm = MagicMock(id="vm-99")
    mock_vm.name = "testvm001"

    mock_client.find_resource_by_id_or_name.side_effect = [mock_user, mock_role, mock_vm]

    mock_new_perm = MagicMock()
    mock_new_perm.id = "new-perm-uuid"
    mock_perms_svc.add.return_value = mock_new_perm

    with patch("ovirt_mcp.tools.users.get_client", return_value=mock_client):
        res = add_permission_tool(
            user_name_or_id="operator@internal",
            role_name_or_id="UserRole",
            target_type="vm",
            target_name_or_id="testvm001",
        )

    assert isinstance(res, PermissionResult)
    assert res.success is True
    assert res.permission_id == "new-perm-uuid"
    assert res.role_name == "UserRole"
    assert res.target_type == "vm"
    assert res.target_name == "testvm001"
    mock_perms_svc.add.assert_called_once()


def test_add_permission_tool_invalid_target_type() -> None:
    """Test add_permission_tool raises OvirtValidationError on unknown target_type."""
    with pytest.raises(OvirtValidationError, match="Invalid target_type"):
        add_permission_tool(
            user_name_or_id="mcp@internal",
            role_name_or_id="UserRole",
            target_type="invalid_entity",
        )


def test_remove_permission_tool_safe_mode() -> None:
    """Test remove_permission_tool enforces Safe Mode confirm=True."""
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        remove_permission_tool("perm-1234", confirm=False)


def test_remove_permission_tool_success() -> None:
    """Test remove_permission_tool revokes permission grant when confirmed."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_perms_svc = MagicMock()
    mock_perm_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.permissions_service.return_value = mock_perms_svc
    mock_perms_svc.permission_service.return_value = mock_perm_svc

    mock_perm = MagicMock()
    mock_perm.role = MagicMock(name="SuperUser")
    mock_perm.role.name = "SuperUser"
    mock_perm.user = MagicMock(name="operator")
    mock_perm.user.name = "operator@internal"
    mock_perm_svc.get.return_value = mock_perm

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.users.get_client", return_value=mock_client),
    ):
        res = remove_permission_tool("perm-1234", confirm=True)

    assert isinstance(res, PermissionResult)
    assert res.success is True
    assert res.action == "remove"
    assert res.permission_id == "perm-1234"
    mock_perm_svc.remove.assert_called_once()


def test_add_role_tool_user_role_success() -> None:
    """Test add_role_tool creates a regular custom role with permits."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_roles_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.roles_service.return_value = mock_roles_svc

    mock_created = MagicMock()
    mock_created.id = "new-role-uuid-1"
    mock_roles_svc.add.return_value = mock_created

    with patch("ovirt_mcp.tools.users.get_client", return_value=mock_client):
        res = add_role_tool(
            name="DevOpsOperator",
            description="Role for DevOps VM operators",
            administrative=False,
            permits=["create_vm", "delete_vm"],
        )

    assert isinstance(res, RoleResult)
    assert res.success is True
    assert res.role_name == "DevOpsOperator"
    assert res.role_id == "new-role-uuid-1"
    mock_roles_svc.add.assert_called_once()


def test_add_role_tool_admin_safe_mode() -> None:
    """Test add_role_tool requires confirm=True when administrative=True in Safe Mode."""
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        add_role_tool(
            name="CustomAdmin",
            administrative=True,
            confirm=False,
        )


def test_add_role_tool_empty_name() -> None:
    """Test add_role_tool rejects empty role name."""
    with pytest.raises(OvirtValidationError, match="Role name cannot be empty"):
        add_role_tool(name="   ")


def test_delete_role_tool_safe_mode() -> None:
    """Test delete_role_tool enforces Safe Mode confirm=True."""
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        delete_role_tool("CustomRole", confirm=False)


def test_delete_role_tool_immutable_guard() -> None:
    """Test delete_role_tool blocks deleting built-in immutable system roles."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_roles_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.roles_service.return_value = mock_roles_svc

    mock_builtin_role = MagicMock(id="super-uuid", administrative=True, mutable=False)
    mock_builtin_role.name = "SuperUser"
    mock_client.find_resource_by_id_or_name.return_value = mock_builtin_role

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.users.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="built-in immutable system role"),
    ):
        delete_role_tool("SuperUser", confirm=True)


def test_delete_role_tool_success() -> None:
    """Test delete_role_tool removes mutable custom role when confirmed."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_roles_svc = MagicMock()
    mock_role_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.roles_service.return_value = mock_roles_svc
    mock_roles_svc.role_service.return_value = mock_role_svc

    mock_custom_role = MagicMock(id="custom-role-id", administrative=False, mutable=True)
    mock_custom_role.name = "DevOpsOperator"
    mock_client.find_resource_by_id_or_name.return_value = mock_custom_role

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.users.get_client", return_value=mock_client),
    ):
        res = delete_role_tool("DevOpsOperator", confirm=True)

    assert isinstance(res, RoleResult)
    assert res.success is True
    assert res.action == "delete"
    assert res.role_name == "DevOpsOperator"
    mock_role_svc.remove.assert_called_once()
