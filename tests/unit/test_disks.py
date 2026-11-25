"""Unit tests for virtual disk management tools."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtPermissionError, OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.disk import (
    DiskCreateResult,
    DiskDetail,
    DiskOperationResult,
    DiskResizeResult,
    VmDiskAttachmentInfo,
    VmDiskAttachmentResult,
)
from ovirt_mcp.tools.disks import (
    attach_vm_disk_tool,
    copy_disk_tool,
    create_disk_tool,
    create_vm_disk_tool,
    detach_vm_disk_tool,
    list_disks_tool,
    list_vm_disks_tool,
    move_disk_tool,
    resize_disk_tool,
    sparsify_disk_tool,
)


def _setup_mock_vm_and_disks(
    vm_id: str = "vm-uuid-1",
    vm_name: str = "test-vm",
) -> tuple[MagicMock, MagicMock, MagicMock]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()
    mock_disks_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = vm_id
    mock_vm.name = vm_name

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_system.disks_service.return_value = mock_disks_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    return mock_client, mock_vm_service, mock_disks_service


# ── LIST VM DISKS TESTS ───────────────────────────────────────────────────────


def test_list_vm_disks_success() -> None:
    mock_client, mock_vm_service, mock_disks_service = _setup_mock_vm_and_disks()

    mock_att = MagicMock()
    mock_att.id = "att-1"
    mock_att.disk.id = "disk-1"
    mock_att.bootable = True
    mock_att.active = True
    mock_att.read_only = False
    mock_att.interface.value = "virtio_scsi"

    mock_vm_service.disk_attachments_service().list.return_value = [mock_att]

    mock_disk = MagicMock()
    mock_disk.id = "disk-1"
    mock_disk.name = "test-vm_os"
    mock_disk.provisioned_size = 20 * (1024**3)
    mock_disk.actual_size = 5 * (1024**3)
    mock_disk.format.value = "cow"
    mock_disk.status.value = "ok"
    mock_sd = MagicMock()
    mock_sd.name = "Data"
    mock_disk.storage_domains = [mock_sd]

    mock_disks_service.disk_service("disk-1").get.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = list_vm_disks_tool("test-vm")

    assert len(res) == 1
    assert isinstance(res[0], VmDiskAttachmentInfo)
    assert res[0].attachment_id == "att-1"
    assert res[0].disk_id == "disk-1"
    assert res[0].disk_name == "test-vm_os"
    assert res[0].interface == "virtio_scsi"
    assert res[0].provisioned_size_gb == 20.0
    assert res[0].actual_size_gb == 5.0
    assert res[0].bootable is True


# ── ATTACH DISK TESTS ─────────────────────────────────────────────────────────


def test_attach_vm_disk_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        attach_vm_disk_tool("test-vm", disk_id="disk-1")
    assert "read-only mode" in str(exc_info.value)


def test_attach_vm_disk_invalid_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, mock_disks_service = _setup_mock_vm_and_disks()
    mock_disk = MagicMock()
    mock_disk.name = "datadisk"
    mock_disks_service.disk_service("disk-1").get.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            attach_vm_disk_tool("test-vm", disk_id="disk-1", interface="invalid_iface")
        assert "Invalid disk interface" in str(exc_info.value)


def test_attach_vm_disk_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, mock_disks_service = _setup_mock_vm_and_disks()
    mock_disk = MagicMock()
    mock_disk.name = "extra_disk"
    mock_disks_service.disk_service("disk-1").get.return_value = mock_disk

    mock_created = MagicMock()
    mock_created.id = "att-new-123"
    mock_vm_service.disk_attachments_service().add.return_value = mock_created

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = attach_vm_disk_tool(
            "test-vm",
            disk_id="disk-1",
            interface="virtio",
            bootable=False,
            active=True,
        )

    assert isinstance(res, VmDiskAttachmentResult)
    assert res.success is True
    assert res.action == "attach"
    assert res.disk_id == "disk-1"
    assert res.interface == "virtio"
    mock_vm_service.disk_attachments_service().add.assert_called_once()


# ── DETACH DISK TESTS ─────────────────────────────────────────────────────────


def test_detach_vm_disk_safe_mode_unconfirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        detach_vm_disk_tool("test-vm", disk_id="disk-1", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_detach_vm_disk_not_attached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm_and_disks()
    mock_vm_service.disk_attachments_service().list.return_value = []

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            detach_vm_disk_tool("test-vm", disk_id="disk-1", confirm=True)
        assert "not attached to virtual machine" in str(exc_info.value)


def test_detach_vm_disk_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm_and_disks()

    mock_att = MagicMock()
    mock_att.id = "att-1"
    mock_att.disk.id = "disk-1"
    mock_vm_service.disk_attachments_service().list.return_value = [mock_att]

    mock_att_svc = MagicMock()
    mock_vm_service.disk_attachments_service().attachment_service.return_value = mock_att_svc

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = detach_vm_disk_tool("test-vm", disk_id="disk-1", confirm=True, wait=False)

    assert isinstance(res, VmDiskAttachmentResult)
    assert res.success is True
    assert res.action == "detach"
    mock_att_svc.remove.assert_called_once_with(detach_only=True)


# ── CREATE VM DISK TESTS ──────────────────────────────────────────────────────


def test_create_vm_disk_invalid_size() -> None:
    with pytest.raises(OvirtValidationError) as exc_info:
        create_vm_disk_tool("test-vm", size_gb=0, storage_domain="Data")
    assert "greater than 0 GB" in str(exc_info.value)


def test_create_vm_disk_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm_and_disks()

    mock_sd = MagicMock()
    mock_sd.id = "sd-data-1"
    mock_sd.name = "Data"
    mock_client.find_resource_by_id_or_name.side_effect = [
        MagicMock(id="vm-1", name="test-vm"),
        mock_sd,
    ]

    mock_created = MagicMock()
    mock_created.disk.id = "new-disk-uuid"
    mock_vm_service.disk_attachments_service().add.return_value = mock_created

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = create_vm_disk_tool(
            "test-vm",
            size_gb=10,
            storage_domain="Data",
            disk_name="data_disk",
            disk_format="cow",
            interface="virtio",
            wait=False,
        )

    assert isinstance(res, VmDiskAttachmentResult)
    assert res.success is True
    assert res.action == "create"
    assert res.disk_id == "new-disk-uuid"
    assert res.disk_name == "data_disk"


def test_create_disk_floating_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_disks_svc = MagicMock()
    mock_sds_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_sys.storage_domains_service.return_value = mock_sds_svc

    mock_sd = MagicMock()
    mock_sd.id = "sd-data-1"
    mock_sd.name = "Data"
    mock_client.find_resource_by_id_or_name.return_value = mock_sd

    mock_created = MagicMock()
    mock_created.id = "floating-disk-uuid"
    mock_disks_svc.add.return_value = mock_created

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = create_disk_tool(
            size_gb=20,
            storage_domain="Data",
            disk_name="floating_disk_01",
            disk_format="cow",
            vm_name_or_id=None,
            wait=False,
        )

    assert isinstance(res, DiskCreateResult)
    assert res.success is True
    assert res.disk_id == "floating-disk-uuid"
    assert res.disk_name == "floating_disk_01"
    assert res.provisioned_size_gb == 20.0
    assert res.storage_domain == "Data"


def test_create_disk_with_vm_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm_and_disks()

    mock_sd = MagicMock()
    mock_sd.id = "sd-data-1"
    mock_sd.name = "Data"
    mock_client.find_resource_by_id_or_name.side_effect = [
        MagicMock(id="vm-1", name="test-vm"),
        mock_sd,
    ]

    mock_created = MagicMock()
    mock_created.disk.id = "attached-disk-uuid"
    mock_vm_service.disk_attachments_service().add.return_value = mock_created

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = create_disk_tool(
            size_gb=15,
            storage_domain="Data",
            disk_name="attached_disk_01",
            vm_name_or_id="test-vm",
            wait=False,
        )

    assert isinstance(res, VmDiskAttachmentResult)
    assert res.success is True
    assert res.disk_id == "attached-disk-uuid"


# ── RESIZE DISK TESTS ─────────────────────────────────────────────────────────


def test_resize_disk_safe_mode_unconfirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        resize_disk_tool("disk-1", size_gb=50, confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_resize_disk_shrink_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, mock_disks_service = _setup_mock_vm_and_disks()
    mock_disk = MagicMock()
    mock_disk.name = "large_disk"
    mock_disk.provisioned_size = 50 * (1024**3)
    mock_disks_service.disk_service("disk-1").get.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            resize_disk_tool("disk-1", size_gb=40, confirm=True)
        assert "must be strictly greater" in str(exc_info.value)


def test_resize_disk_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, mock_disks_service = _setup_mock_vm_and_disks()
    mock_disk = MagicMock()
    mock_disk.name = "database_disk"
    mock_disk.provisioned_size = 20 * (1024**3)
    mock_disk_svc = mock_disks_service.disk_service("disk-1")
    mock_disk_svc.get.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = resize_disk_tool("disk-1", size_gb=35, confirm=True)

    assert isinstance(res, DiskResizeResult)
    assert res.success is True
    assert res.old_size_gb == 20.0
    assert res.new_size_gb == 35.0
    mock_disk_svc.update.assert_called_once()


def test_resize_disk_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, mock_disks_service = _setup_mock_vm_and_disks()
    mock_disk = MagicMock()
    mock_disk.name = "database_disk"
    mock_disk.provisioned_size = 20 * (1024**3)
    mock_disk_svc = mock_disks_service.disk_service("disk-1")
    mock_disk_svc.get.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = resize_disk_tool("disk-1", size_gb=35, confirm=True, dry_run=True)

    assert isinstance(res, DiskResizeResult)
    assert res.success is True
    assert res.dry_run is True
    assert res.old_size_gb == 20.0
    assert res.new_size_gb == 35.0
    assert "[DRY RUN]" in res.message
    mock_disk_svc.update.assert_not_called()


# ── LIST DISKS TESTS ──────────────────────────────────────────────────────────


def test_list_disks_success() -> None:
    mock_client, _, mock_disks_service = _setup_mock_vm_and_disks()

    mock_d1 = MagicMock()
    mock_d1.id = "d-1"
    mock_d1.name = "disk1"
    mock_d1.status.value = "ok"
    mock_d1.provisioned_size = 10 * (1024**3)
    mock_d1.actual_size = 2 * (1024**3)
    mock_d1.format.value = "cow"
    mock_d1.content_type.value = "data"
    mock_sd = MagicMock()
    mock_sd.id = "sd-1"
    mock_sd.name = "Data"
    mock_d1.storage_domains = [mock_sd]

    mock_disks_service.list.return_value = [mock_d1]

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = list_disks_tool()

    assert len(res) == 1
    assert isinstance(res[0], DiskDetail)
    assert res[0].id == "d-1"
    assert res[0].name == "disk1"
    assert res[0].provisioned_size_gb == 10.0
    assert res[0].storage_domain_name == "Data"


# ── DISK MOBILITY & SPARSIFY TESTS ──────────────────────────────────────────


def test_move_disk_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_disks_svc = MagicMock()
    mock_disk_svc = MagicMock()
    mock_sds_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_sys.storage_domains_service.return_value = mock_sds_svc
    mock_disks_svc.disk_service.return_value = mock_disk_svc

    mock_src_sd = MagicMock()
    mock_src_sd.id = "sd-src-1"
    mock_src_sd.name = "Data"

    mock_target_sd = MagicMock()
    mock_target_sd.id = "sd-tgt-2"
    mock_target_sd.name = "Data3"

    mock_disk = MagicMock()
    mock_disk.id = "disk-uuid-1"
    mock_disk.name = "vm_disk_1"
    mock_disk.status = "ok"
    mock_disk.storage_domains = [mock_src_sd]

    def _find_resource(svc: MagicMock, ident: str, res_type: str) -> MagicMock:
        if res_type == "disk":
            return mock_disk
        return mock_target_sd

    mock_client.find_resource_by_id_or_name.side_effect = _find_resource
    mock_disk_svc.get.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = move_disk_tool("disk-uuid-1", "Data3", wait=False)

    assert isinstance(res, DiskOperationResult)
    assert res.success is True
    assert res.action == "move"
    assert res.source_storage_domain == "Data"
    assert res.target_storage_domain == "Data3"
    mock_disk_svc.move.assert_called_once()


def test_move_disk_dry_run() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_disks_svc = MagicMock()
    mock_disk_svc = MagicMock()
    mock_sds_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_sys.storage_domains_service.return_value = mock_sds_svc
    mock_disks_svc.disk_service.return_value = mock_disk_svc

    mock_src_sd = MagicMock()
    mock_src_sd.id = "sd-src-1"
    mock_src_sd.name = "Data"

    mock_target_sd = MagicMock()
    mock_target_sd.id = "sd-tgt-2"
    mock_target_sd.name = "Data3"

    mock_disk = MagicMock()
    mock_disk.id = "disk-uuid-1"
    mock_disk.name = "vm_disk_1"
    mock_disk.status = "ok"
    mock_disk.storage_domains = [mock_src_sd]

    def _find_resource(svc: MagicMock, ident: str, res_type: str) -> MagicMock:
        if res_type == "disk":
            return mock_disk
        return mock_target_sd

    mock_client.find_resource_by_id_or_name.side_effect = _find_resource
    mock_disk_svc.get.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = move_disk_tool("disk-uuid-1", "Data3", dry_run=True)

    assert isinstance(res, DiskOperationResult)
    assert res.success is True
    assert res.dry_run is True
    assert res.action == "move"
    assert "[DRY RUN]" in res.message
    mock_disk_svc.move.assert_not_called()


def test_move_disk_already_on_target() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_disks_svc = MagicMock()
    mock_sds_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_sys.storage_domains_service.return_value = mock_sds_svc

    mock_sd = MagicMock()
    mock_sd.id = "sd-common-id"
    mock_sd.name = "Data"

    mock_disk = MagicMock()
    mock_disk.id = "disk-uuid-1"
    mock_disk.name = "vm_disk_1"
    mock_disk.storage_domains = [mock_sd]

    mock_client.find_resource_by_id_or_name.side_effect = lambda svc, ident, res_type: (
        mock_disk if res_type == "disk" else mock_sd
    )

    with (
        patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="already on target"),
    ):
        move_disk_tool("disk-uuid-1", "Data", wait=False)


def test_move_disk_locked_guard() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_disks_svc = MagicMock()
    mock_sds_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_sys.storage_domains_service.return_value = mock_sds_svc

    mock_src_sd = MagicMock()
    mock_src_sd.id = "sd-1"
    mock_src_sd.name = "Data"

    mock_target_sd = MagicMock()
    mock_target_sd.id = "sd-2"
    mock_target_sd.name = "Data3"

    mock_disk = MagicMock()
    mock_disk.id = "disk-uuid-1"
    mock_disk.name = "vm_disk_1"
    mock_disk.status = "locked"
    mock_disk.storage_domains = [mock_src_sd]

    mock_client.find_resource_by_id_or_name.side_effect = lambda svc, ident, res_type: (
        mock_disk if res_type == "disk" else mock_target_sd
    )

    with (
        patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="currently locked"),
    ):
        move_disk_tool("disk-uuid-1", "Data3", wait=False)


def test_copy_disk_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_disks_svc = MagicMock()
    mock_disk_svc = MagicMock()
    mock_sds_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_sys.storage_domains_service.return_value = mock_sds_svc
    mock_disks_svc.disk_service.return_value = mock_disk_svc

    mock_src_sd = MagicMock()
    mock_src_sd.id = "sd-1"
    mock_src_sd.name = "Data"

    mock_target_sd = MagicMock()
    mock_target_sd.id = "sd-2"
    mock_target_sd.name = "Data3"

    mock_disk = MagicMock()
    mock_disk.id = "disk-uuid-1"
    mock_disk.name = "original_disk"
    mock_disk.status = "ok"
    mock_disk.storage_domains = [mock_src_sd]

    mock_client.find_resource_by_id_or_name.side_effect = lambda svc, ident, res_type: (
        mock_disk if res_type == "disk" else mock_target_sd
    )
    mock_disk_svc.get.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = copy_disk_tool("original_disk", "Data3", new_alias="cloned_disk", wait=False)

    assert isinstance(res, DiskOperationResult)
    assert res.success is True
    assert res.action == "copy"
    assert res.disk_name == "cloned_disk"
    assert res.target_storage_domain == "Data3"
    mock_disk_svc.copy.assert_called_once()


def test_sparsify_disk_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_disks_svc = MagicMock()
    mock_disk_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_disks_svc.disk_service.return_value = mock_disk_svc

    mock_disk = MagicMock()
    mock_disk.id = "disk-uuid-raw"
    mock_disk.name = "raw_disk"
    mock_disk.format = "raw"
    mock_disk.status = "ok"

    mock_client.find_resource_by_id_or_name.return_value = mock_disk
    mock_disk_svc.get.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = sparsify_disk_tool("raw_disk", wait=False)

    assert isinstance(res, DiskOperationResult)
    assert res.success is True
    assert res.action == "sparsify"
    mock_disk_svc.sparsify.assert_called_once()


def test_sparsify_disk_dry_run() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_disks_svc = MagicMock()
    mock_disk_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_disks_svc.disk_service.return_value = mock_disk_svc

    mock_disk = MagicMock()
    mock_disk.id = "disk-uuid-raw"
    mock_disk.name = "raw_disk"
    mock_disk.format = "raw"
    mock_disk.status = "ok"

    mock_client.find_resource_by_id_or_name.return_value = mock_disk
    mock_disk_svc.get.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = sparsify_disk_tool("raw_disk", dry_run=True)

    assert isinstance(res, DiskOperationResult)
    assert res.success is True
    assert res.dry_run is True
    assert res.action == "sparsify"
    assert "[DRY RUN]" in res.message
    mock_disk_svc.sparsify.assert_not_called()


def test_sparsify_disk_cow_format_guard() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_disks_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.disks_service.return_value = mock_disks_svc

    mock_disk = MagicMock()
    mock_disk.id = "disk-uuid-cow"
    mock_disk.name = "cow_disk"
    mock_disk.format = "cow"

    mock_client.find_resource_by_id_or_name.return_value = mock_disk

    with (
        patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="disk format is 'cow'"),
    ):
        sparsify_disk_tool("cow_disk", wait=False)
