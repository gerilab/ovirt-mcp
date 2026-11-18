"""Unit tests for oVirt / OLVM Template management tools."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.template import (
    TemplateDetail,
    TemplateResult,
    TemplateSummary,
)
from ovirt_mcp.tools.templates import (
    BLANK_TEMPLATE_ID,
    create_template_from_vm_tool,
    delete_template_tool,
    get_template_tool,
    list_templates_tool,
)


def _setup_mock_template() -> MagicMock:
    mock_t = MagicMock()
    mock_t.id = "tpl-uuid-1"
    mock_t.name = "OracleLinux8-Golden"
    mock_t.description = "Golden master template"
    mock_t.status = "ok"
    mock_t.memory = 4 * 1024 * 1024 * 1024
    mock_t.cpu.topology.cores = 2
    mock_t.cpu.topology.sockets = 1
    mock_t.version.version_number = 1
    mock_t.version.version_name = "base"
    mock_t.version.base_template = None
    mock_t.os.type = "rhel_8x64"
    mock_t.cluster.id = "cl-uuid-1"
    mock_t.creation_time = None
    return mock_t


def test_list_templates_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_t_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.templates_service.return_value = mock_t_svc

    mock_t = _setup_mock_template()
    mock_t_svc.list.return_value = [mock_t]

    with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
        res = list_templates_tool()

    assert len(res) == 1
    assert isinstance(res[0], TemplateSummary)
    assert res[0].id == "tpl-uuid-1"
    assert res[0].name == "OracleLinux8-Golden"
    assert res[0].memory_mb == 4096
    assert res[0].cpu_cores == 2
    assert res[0].cpu_sockets == 1


def test_get_template_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_t_svc = MagicMock()
    mock_t_inst = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.templates_service.return_value = mock_t_svc
    mock_t_svc.template_service.return_value = mock_t_inst

    mock_t = _setup_mock_template()
    mock_client.find_resource_by_id_or_name.return_value = mock_t

    mock_att = MagicMock()
    mock_att.id = "att-uuid-1"
    mock_att.disk.id = "disk-uuid-1"
    mock_att.interface = "virtio_scsi"
    mock_att.bootable = True
    mock_t_inst.disk_attachments_service().list.return_value = [mock_att]

    mock_nic = MagicMock()
    mock_t_inst.nics_service().list.return_value = [mock_nic]

    with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
        res = get_template_tool("OracleLinux8-Golden")

    assert isinstance(res, TemplateDetail)
    assert res.id == "tpl-uuid-1"
    assert res.name == "OracleLinux8-Golden"
    assert res.os_type == "rhel_8x64"
    assert len(res.disks) == 1
    assert res.disks[0].disk_id == "disk-uuid-1"
    assert res.disks[0].bootable is True
    assert res.nic_count == 1


def test_create_template_from_vm_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_vms_svc = MagicMock()
    mock_t_svc = MagicMock()
    mock_t_inst = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vms_service.return_value = mock_vms_svc
    mock_sys.templates_service.return_value = mock_t_svc
    mock_t_svc.template_service.return_value = mock_t_inst

    mock_vm = MagicMock()
    mock_vm.id = "vm-uuid-1"
    mock_vm.name = "source-vm"
    mock_vm.status = "down"

    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_t_svc.list.return_value = []  # No collision

    mock_created = MagicMock()
    mock_created.id = "new-tpl-uuid"
    mock_t_svc.add.return_value = mock_created

    mock_t_updated = MagicMock()
    mock_t_updated.status = "ok"
    mock_t_inst.get.return_value = mock_t_updated

    with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
        res = create_template_from_vm_tool(
            "source-vm", "NewTemplate", description="Test template", wait=False
        )

    assert isinstance(res, TemplateResult)
    assert res.success is True
    assert res.action == "create"
    assert res.template_id == "new-tpl-uuid"
    assert res.template_name == "NewTemplate"
    mock_t_svc.add.assert_called_once()


def test_create_template_vm_not_down_guard() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_vms_svc = MagicMock()
    mock_t_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vms_service.return_value = mock_vms_svc
    mock_sys.templates_service.return_value = mock_t_svc

    mock_vm = MagicMock()
    mock_vm.id = "vm-uuid-1"
    mock_vm.name = "source-vm"
    mock_vm.status = "up"

    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with (
        patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="VM is currently 'up'"),
    ):
        create_template_from_vm_tool("source-vm", "NewTemplate")


def test_create_template_name_collision_guard() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_vms_svc = MagicMock()
    mock_t_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vms_service.return_value = mock_vms_svc
    mock_sys.templates_service.return_value = mock_t_svc

    mock_vm = MagicMock()
    mock_vm.id = "vm-uuid-1"
    mock_vm.name = "source-vm"
    mock_vm.status = "down"

    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    mock_existing = MagicMock()
    mock_existing.id = "existing-tpl-id"
    mock_t_svc.list.return_value = [mock_existing]

    with (
        patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="already exists"),
    ):
        create_template_from_vm_tool("source-vm", "ExistingTemplate")


def test_delete_template_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_t_svc = MagicMock()
    mock_t_inst = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.templates_service.return_value = mock_t_svc
    mock_t_svc.template_service.return_value = mock_t_inst

    mock_t = MagicMock()
    mock_t.id = "custom-tpl-uuid"
    mock_t.name = "OldTemplate"

    mock_client.find_resource_by_id_or_name.return_value = mock_t

    with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
        res = delete_template_tool("OldTemplate", confirm=True, wait=False)

    assert isinstance(res, TemplateResult)
    assert res.success is True
    assert res.action == "delete"
    assert res.template_id == "custom-tpl-uuid"
    mock_t_inst.remove.assert_called_once()


def test_delete_template_safe_mode_guard() -> None:
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
            OvirtValidationError, match="Operation 'ovirt_template_delete' is destructive"
        ),
    ):
        delete_template_tool("OldTemplate", confirm=False)


def test_delete_template_blank_guard() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_t_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.templates_service.return_value = mock_t_svc

    mock_blank = MagicMock()
    mock_blank.id = BLANK_TEMPLATE_ID
    mock_blank.name = "Blank"

    mock_client.find_resource_by_id_or_name.return_value = mock_blank

    with (
        patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="Cannot delete system template"),
    ):
        delete_template_tool("Blank", confirm=True)
