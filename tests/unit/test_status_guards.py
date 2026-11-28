"""Unit tests for centralized Pre-flight Status Guards across oVirt entities."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.tools.backups import start_vm_backup_tool
from ovirt_mcp.tools.disks import (
    attach_vm_disk_tool,
    create_disk_tool,
    create_vm_disk_tool,
    detach_vm_disk_tool,
    resize_disk_tool,
)
from ovirt_mcp.tools.guards import (
    TRANSITIONAL_DISK_STATUSES,
    TRANSITIONAL_HOST_STATUSES,
    TRANSITIONAL_SNAPSHOT_STATUSES,
    TRANSITIONAL_STORAGE_STATUSES,
    TRANSITIONAL_TEMPLATE_STATUSES,
    TRANSITIONAL_VM_STATUSES,
    require_disk_status,
    require_host_status,
    require_snapshot_status,
    require_storage_domain_status,
    require_template_status,
    require_vm_status,
)
from ovirt_mcp.tools.hosts import (
    activate_host_tool,
    commit_net_config_host_tool,
    enroll_certificate_host_tool,
    maintenance_host_tool,
    refresh_host_tool,
    sync_all_networks_host_tool,
)
from ovirt_mcp.tools.networks import add_vm_nic_tool, remove_vm_nic_tool
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_update_ovf_store,
    refresh_luns_storage_domain_tool,
)
from ovirt_mcp.tools.templates import (
    create_template_from_vm_tool,
    delete_template_tool,
    export_template_tool,
    update_template_tool,
)
from ovirt_mcp.tools.vm_exports import export_disk_tool, export_vm_tool
from ovirt_mcp.tools.vms import (
    clone_vm_from_snapshot_tool,
    clone_vm_tool,
    create_vm_snapshot_tool,
    delete_vm_snapshot_tool,
    preview_vm_snapshot_tool,
)


class TestStatusGuardPrimitives:
    """Direct tests for guard functions in guards.py."""

    @pytest.mark.parametrize("status", TRANSITIONAL_HOST_STATUSES)
    def test_require_host_status_rejects_transitional(self, status: str) -> None:
        with pytest.raises(OvirtValidationError) as exc_info:
            require_host_status(
                host_name="node01.example.com",
                current_status=status,
                allowed_statuses=("up", "maintenance", "non_operational"),
                action_name="refresh_host",
            )
        assert f"Current status is '{status}'" in str(exc_info.value)
        assert exc_info.value.details.get("is_transitional") is True

    def test_require_host_status_accepts_allowed(self) -> None:
        # Should not raise
        require_host_status(
            host_name="node01.example.com",
            current_status="up",
            allowed_statuses=("up", "maintenance", "non_operational"),
            action_name="refresh_host",
        )
        require_host_status(
            host_name="node01.example.com",
            current_status="maintenance",
            allowed_statuses=("up", "maintenance", "non_operational"),
            action_name="refresh_host",
        )

    @pytest.mark.parametrize("status", TRANSITIONAL_VM_STATUSES)
    def test_require_vm_status_rejects_transitional(self, status: str) -> None:
        with pytest.raises(OvirtValidationError) as exc_info:
            require_vm_status(
                vm_name="vm-prod-01",
                current_status=status,
                allowed_statuses=("up",),
                action_name="suspend_vm",
            )
        assert f"Current status is '{status}'" in str(exc_info.value)
        assert exc_info.value.details.get("is_transitional") is True

    def test_require_vm_status_accepts_allowed(self) -> None:
        require_vm_status(
            vm_name="vm-prod-01",
            current_status="up",
            allowed_statuses=("up",),
            action_name="suspend_vm",
        )

    @pytest.mark.parametrize("status", TRANSITIONAL_STORAGE_STATUSES)
    def test_require_storage_domain_status_rejects_transitional(self, status: str) -> None:
        with pytest.raises(OvirtValidationError) as exc_info:
            require_storage_domain_status(
                domain_name="iscsi_domain_01",
                current_status=status,
                allowed_statuses=("active",),
                action_name="update_ovf_store",
            )
        assert f"Current status is '{status}'" in str(exc_info.value)
        assert exc_info.value.details.get("is_transitional") is True

    @pytest.mark.parametrize("status", TRANSITIONAL_DISK_STATUSES)
    def test_require_disk_status_rejects_transitional(self, status: str) -> None:
        with pytest.raises(OvirtValidationError) as exc_info:
            require_disk_status(
                disk_id_or_name="disk-uuid-001",
                current_status=status,
                allowed_statuses=("ok",),
                action_name="resize_disk",
            )
        assert f"Current status is '{status}'" in str(exc_info.value)
        assert exc_info.value.details.get("is_transitional") is True

    @pytest.mark.parametrize("status", TRANSITIONAL_SNAPSHOT_STATUSES)
    def test_require_snapshot_status_rejects_transitional(self, status: str) -> None:
        with pytest.raises(OvirtValidationError) as exc_info:
            require_snapshot_status(
                snapshot_desc_or_id="snap-pre-patch",
                current_status=status,
                allowed_statuses=("ok",),
                action_name="restore_snapshot",
            )
        assert f"Current status is '{status}'" in str(exc_info.value)
        assert exc_info.value.details.get("is_transitional") is True


class TestHostToolStatusGuards:
    """Integration unit tests verifying that host tools enforce status guards."""

    def _setup_mock(self, status: str) -> MagicMock:
        mock_client = MagicMock()
        mock_conn = MagicMock()
        mock_system = MagicMock()
        mock_hosts_svc = MagicMock()
        mock_host_svc = MagicMock()

        mock_host = MagicMock()
        mock_host.id = "h-uuid-1"
        mock_host.name = "node01.example.com"
        mock_status = MagicMock()
        mock_status.value = status
        mock_host.status = mock_status

        mock_hosts_svc.host_service.return_value = mock_host_svc
        mock_system.hosts_service.return_value = mock_hosts_svc
        mock_system.vms_service.return_value.list.return_value = []
        mock_conn.system_service.return_value = mock_system
        mock_client.get_connection.return_value = mock_conn
        mock_client.find_resource_by_id_or_name.return_value = mock_host
        return mock_client

    def test_refresh_host_blocked_in_reboot(self) -> None:
        mock_client = self._setup_mock(status="reboot")
        with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                refresh_host_tool(name_or_id="node01.example.com", dry_run=True)
            assert "Current status is 'reboot'" in str(exc_info.value)

    def test_refresh_host_allowed_in_maintenance_and_up(self) -> None:
        mock_client = self._setup_mock(status="maintenance")
        with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
            res = refresh_host_tool(name_or_id="node01.example.com", dry_run=True)
            assert res.success is True

        mock_client_up = self._setup_mock(status="up")
        with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client_up):
            res_up = refresh_host_tool(name_or_id="node01.example.com", dry_run=True)
            assert res_up.success is True

    def test_enroll_certificate_blocked_in_up_and_reboot(self) -> None:
        mock_client_up = self._setup_mock(status="up")
        with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client_up):
            with pytest.raises(OvirtValidationError) as exc_info:
                enroll_certificate_host_tool(name_or_id="node01.example.com", dry_run=True)
            assert "Current status is 'up'" in str(exc_info.value)

        mock_client_reboot = self._setup_mock(status="reboot")
        with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client_reboot):
            with pytest.raises(OvirtValidationError) as exc_info:
                enroll_certificate_host_tool(name_or_id="node01.example.com", dry_run=True)
            assert "Current status is 'reboot'" in str(exc_info.value)

    def test_enroll_certificate_allowed_in_maintenance(self) -> None:
        mock_client = self._setup_mock(status="maintenance")
        with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
            res = enroll_certificate_host_tool(name_or_id="node01.example.com", dry_run=True)
            assert res.success is True

    def test_activate_host_blocked_in_reboot(self) -> None:
        mock_client = self._setup_mock(status="reboot")
        with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                activate_host_tool(name_or_id="node01.example.com", dry_run=True)
            assert "Current status is 'reboot'" in str(exc_info.value)

    def test_maintenance_host_blocked_in_reboot(self) -> None:
        mock_client = self._setup_mock(status="reboot")
        with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                maintenance_host_tool(
                    name_or_id="node01.example.com",
                    stop_pinned_vms=True,
                    confirm=True,
                    dry_run=True,
                )
            assert "Current status is 'reboot'" in str(exc_info.value)

    def test_sync_networks_blocked_in_reboot(self) -> None:
        mock_client = self._setup_mock(status="reboot")
        with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                sync_all_networks_host_tool(
                    name_or_id="node01.example.com", confirm=True, dry_run=True
                )
            assert "Current status is 'reboot'" in str(exc_info.value)

    def test_commit_net_config_blocked_in_reboot(self) -> None:
        mock_client = self._setup_mock(status="reboot")
        with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                commit_net_config_host_tool(
                    name_or_id="node01.example.com", confirm=True, dry_run=True
                )
            assert "Current status is 'reboot'" in str(exc_info.value)


class TestVmToolStatusGuards:
    """Integration unit tests verifying VM and snapshot status guards."""

    def _setup_mock_vm(self, vm_status: str, snap_status: str = "ok") -> MagicMock:
        mock_client = MagicMock()
        mock_conn = MagicMock()
        mock_sys = MagicMock()
        mock_vms_svc = MagicMock()
        mock_vm_svc = MagicMock()
        mock_snaps_svc = MagicMock()
        mock_snap_svc = MagicMock()

        mock_vm = MagicMock()
        mock_vm.id = "vm-uuid-1"
        mock_vm.name = "vm-test-01"
        mock_vm.status = MagicMock(value=vm_status)

        mock_snap = MagicMock()
        mock_snap.id = "snap-uuid-1"
        mock_snap.description = "snap-01"
        mock_snap.snapshot_status = MagicMock(value=snap_status)
        mock_snap.persist_memorystate = False

        mock_snap_svc.get.return_value = mock_snap
        mock_snaps_svc.snapshot_service.return_value = mock_snap_svc
        mock_snaps_svc.list.return_value = [mock_snap]
        mock_vm_svc.snapshots_service.return_value = mock_snaps_svc
        mock_vms_svc.vm_service.return_value = mock_vm_svc
        mock_vms_svc.list.return_value = []
        mock_sys.vms_service.return_value = mock_vms_svc
        mock_conn.system_service.return_value = mock_sys
        mock_client.get_connection.return_value = mock_conn
        mock_client.find_resource_by_id_or_name.return_value = mock_vm
        return mock_client

    def test_create_vm_memory_snapshot_blocked_when_vm_down(self) -> None:
        mock_client = self._setup_mock_vm(vm_status="down")
        with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                create_vm_snapshot_tool(
                    name_or_id="vm-test-01",
                    description="snap-with-ram",
                    persist_memory=True,
                    dry_run=True,
                )
            assert "Current status is 'down'" in str(exc_info.value)
            assert "create_vm_memory_snapshot" in str(exc_info.value)

    def test_create_vm_snapshot_blocked_in_transitional_state(self) -> None:
        mock_client = self._setup_mock_vm(vm_status="image_locked")
        with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                create_vm_snapshot_tool(
                    name_or_id="vm-test-01",
                    description="snap-disk-only",
                    persist_memory=False,
                    dry_run=True,
                )
            assert "Current status is 'image_locked'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_preview_vm_snapshot_blocked_when_vm_up(self) -> None:
        mock_client = self._setup_mock_vm(vm_status="up", snap_status="ok")
        with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                preview_vm_snapshot_tool(
                    name_or_id="vm-test-01",
                    snapshot_id="snap-uuid-1",
                    confirm=True,
                )
            assert "Current status is 'up'" in str(exc_info.value)

    def test_preview_vm_snapshot_blocked_when_snapshot_locked(self) -> None:
        mock_client = self._setup_mock_vm(vm_status="down", snap_status="locked")
        with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                preview_vm_snapshot_tool(
                    name_or_id="vm-test-01",
                    snapshot_id="snap-uuid-1",
                    confirm=True,
                )
            assert "Current status is 'locked'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_delete_vm_snapshot_blocked_when_snapshot_locked(self) -> None:
        mock_client = self._setup_mock_vm(vm_status="down", snap_status="locked")
        with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                delete_vm_snapshot_tool(
                    name_or_id="vm-test-01",
                    snapshot_id="snap-uuid-1",
                    confirm=True,
                    dry_run=True,
                )
            assert "Current status is 'locked'" in str(exc_info.value)

    def test_clone_vm_blocked_when_source_vm_up(self) -> None:
        mock_client = self._setup_mock_vm(vm_status="up")
        with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                clone_vm_tool(
                    source_name_or_id="vm-test-01",
                    new_name="vm-cloned-01",
                    dry_run=True,
                )
            assert "Current status is 'up'" in str(exc_info.value)

    def test_clone_vm_from_snapshot_blocked_when_snapshot_locked(self) -> None:
        mock_client = self._setup_mock_vm(vm_status="down", snap_status="locked")
        with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                clone_vm_from_snapshot_tool(
                    name_or_id="vm-test-01",
                    snapshot_id="snap-uuid-1",
                    new_name="vm-cloned-snap-01",
                    dry_run=True,
                )
            assert "Current status is 'locked'" in str(exc_info.value)


class TestDiskAndStorageToolStatusGuards:
    """Integration unit tests verifying disk and storage domain status guards."""

    def test_resize_disk_blocked_when_locked(self) -> None:
        mock_client = MagicMock()
        mock_disk = MagicMock(id="d-1", name="disk_01")
        mock_disk.status = MagicMock(value="locked")
        mock_disk.provisioned_size = 10 * 1024**3
        mock_client.find_resource_by_id_or_name.return_value = mock_disk
        mock_client.get_connection().system_service().disks_service().disk_service.return_value.get.return_value = mock_disk

        with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                resize_disk_tool(disk_id="disk_01", size_gb=20, dry_run=True)
            assert "Current status is 'locked'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_update_ovf_store_blocked_when_storage_locked(self) -> None:
        mock_client = MagicMock()
        mock_sd = MagicMock(id="sd-1", name="storage_01")
        mock_sd.status = MagicMock(value="locked")
        mock_client.find_resource_by_id_or_name.return_value = mock_sd

        with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                ovirt_storage_domain_update_ovf_store(name_or_id="storage_01", dry_run=True)
            assert "Current status is 'locked'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_refresh_luns_blocked_when_storage_locked(self) -> None:
        mock_client = MagicMock()
        mock_sd = MagicMock(id="sd-1", name="storage_01")
        mock_sd.status = MagicMock(value="locked")
        mock_client.find_resource_by_id_or_name.return_value = mock_sd

        with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                refresh_luns_storage_domain_tool(name_or_id="storage_01", dry_run=True)
            assert "Current status is 'locked'" in str(exc_info.value)


class TestTemplateStatusGuards:
    """Tests verifying template status validation and guards."""

    def test_require_template_status_ok(self) -> None:
        # Should not raise
        require_template_status("tpl-01", "ok", ("ok",), action_name="test_action")

    @pytest.mark.parametrize("status", TRANSITIONAL_TEMPLATE_STATUSES)
    def test_require_template_status_rejects_transitional(self, status: str) -> None:
        with pytest.raises(OvirtValidationError) as exc_info:
            require_template_status("tpl-01", status, ("ok",), action_name="export_template")
        assert f"Current status is '{status}'" in str(exc_info.value)
        assert exc_info.value.details.get("is_transitional") is True

    def test_require_template_status_rejects_illegal(self) -> None:
        with pytest.raises(OvirtValidationError) as exc_info:
            require_template_status("tpl-01", "illegal", ("ok",), action_name="delete_template")
        assert "Current status is 'illegal'" in str(exc_info.value)
        assert exc_info.value.details.get("is_transitional") is False

    def test_delete_template_blocked_when_locked(self) -> None:
        mock_client = MagicMock()
        mock_tpl = MagicMock(id="tpl-uuid-1")
        mock_tpl.name = "GoldenTemplate"
        mock_tpl.status = MagicMock(value="locked")
        mock_client.find_resource_by_id_or_name.return_value = mock_tpl

        with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                delete_template_tool("GoldenTemplate", dry_run=True)
            assert "Current status is 'locked'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_export_template_blocked_when_locked(self) -> None:
        mock_client = MagicMock()
        mock_tpl = MagicMock(id="tpl-uuid-1")
        mock_tpl.name = "GoldenTemplate"
        mock_tpl.status = MagicMock(value="locked")
        mock_sd = MagicMock(id="sd-uuid-1")
        mock_sd.name = "ExportDomain"
        mock_client.find_resource_by_id_or_name.side_effect = [mock_tpl, mock_sd]

        with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                export_template_tool("GoldenTemplate", "ExportDomain", dry_run=True)
            assert "Current status is 'locked'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_update_template_blocked_when_locked(self) -> None:
        mock_client = MagicMock()
        mock_tpl = MagicMock(id="tpl-uuid-1")
        mock_tpl.name = "GoldenTemplate"
        mock_tpl.status = MagicMock(value="locked")
        mock_client.find_resource_by_id_or_name.return_value = mock_tpl

        with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                update_template_tool("GoldenTemplate", description="New description", dry_run=True)
            assert "Current status is 'locked'" in str(exc_info.value)

    def test_create_template_from_vm_blocked_when_vm_up(self) -> None:
        mock_client = MagicMock()
        mock_vm = MagicMock(id="vm-uuid-1")
        mock_vm.name = "RunningVM"
        mock_vm.status = MagicMock(value="up")
        mock_client.find_resource_by_id_or_name.return_value = mock_vm

        with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                create_template_from_vm_tool("RunningVM", "NewTemplate", dry_run=True)
            assert "Current status is 'up'" in str(exc_info.value)
            assert "requires the VM to be in one of the following states: 'down'" in str(
                exc_info.value
            )

    def test_start_vm_backup_blocked_when_vm_down(self) -> None:
        mock_client = MagicMock()
        mock_vm = MagicMock(id="vm-uuid-1")
        mock_vm.name = "StoppedVM"
        mock_vm.status = MagicMock(value="down")
        mock_client.find_resource_by_id_or_name.return_value = mock_vm

        with patch("ovirt_mcp.tools.backups.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                start_vm_backup_tool("StoppedVM", confirm=True)
            assert "Current status is 'down'" in str(exc_info.value)
            assert "requires the VM to be in one of the following states: 'up'" in str(
                exc_info.value
            )

    def test_export_vm_blocked_when_vm_up(self) -> None:
        mock_client = MagicMock()
        mock_vm = MagicMock(id="vm-uuid-1")
        mock_vm.name = "ActiveVM"
        mock_vm.status = MagicMock(value="up")
        mock_client.find_resource_by_id_or_name.return_value = mock_vm

        with patch("ovirt_mcp.tools.vm_exports.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                export_vm_tool("ActiveVM", storage_domain="ExportDomain", confirm=True)
            assert "Current status is 'up'" in str(exc_info.value)
            assert "requires the VM to be in one of the following states: 'down'" in str(
                exc_info.value
            )

    def test_export_disk_blocked_when_disk_locked(self) -> None:
        mock_client = MagicMock()
        mock_disk = MagicMock(id="disk-uuid-1")
        mock_disk.name = "LockedDisk"
        mock_disk.status = MagicMock(value="locked")
        mock_sd = MagicMock(id="sd-uuid-1")
        mock_sd.name = "ExportDomain"
        mock_client.find_resource_by_id_or_name.side_effect = [mock_disk, mock_sd]

        with patch("ovirt_mcp.tools.vm_exports.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                export_disk_tool("LockedDisk", "ExportDomain", confirm=True)
            assert "Current status is 'locked'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True


class TestNetworkAndDiskAttachmentStatusGuards:
    """Tests verifying status guards in networks and disk attachment modules."""

    def test_add_vm_nic_blocked_when_vm_saving_state(self) -> None:
        mock_client = MagicMock()
        mock_vm = MagicMock(id="vm-uuid-1", name="SavingVM")
        mock_vm.status = MagicMock(value="saving_state")
        mock_client.find_resource_by_id_or_name.return_value = mock_vm

        with patch("ovirt_mcp.tools.networks.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                add_vm_nic_tool("SavingVM", name="nic1", profile="ovirtmgmt")
            assert "Current status is 'saving_state'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_remove_vm_nic_blocked_when_vm_saving_state(self) -> None:
        mock_client = MagicMock()
        mock_vm = MagicMock(id="vm-uuid-1", name="SavingVM")
        mock_vm.status = MagicMock(value="saving_state")
        mock_client.find_resource_by_id_or_name.return_value = mock_vm

        with patch("ovirt_mcp.tools.networks.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                remove_vm_nic_tool("SavingVM", nic_name_or_id="nic1", confirm=True)
            assert "Current status is 'saving_state'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_attach_vm_disk_blocked_when_vm_saving_state(self) -> None:
        mock_client = MagicMock()
        mock_vm = MagicMock(id="vm-uuid-1", name="SavingVM")
        mock_vm.status = MagicMock(value="saving_state")
        mock_client.find_resource_by_id_or_name.return_value = mock_vm

        with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                attach_vm_disk_tool("SavingVM", disk_id="disk-uuid-1")
            assert "Current status is 'saving_state'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_detach_vm_disk_blocked_when_vm_saving_state(self) -> None:
        mock_client = MagicMock()
        mock_vm = MagicMock(id="vm-uuid-1", name="SavingVM")
        mock_vm.status = MagicMock(value="saving_state")
        mock_client.find_resource_by_id_or_name.return_value = mock_vm

        with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                detach_vm_disk_tool("SavingVM", disk_id="disk-uuid-1", confirm=True)
            assert "Current status is 'saving_state'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_create_vm_disk_blocked_when_vm_saving_state(self) -> None:
        mock_client = MagicMock()
        mock_vm = MagicMock(id="vm-uuid-1", name="SavingVM")
        mock_vm.status = MagicMock(value="saving_state")
        mock_client.find_resource_by_id_or_name.return_value = mock_vm

        with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                create_vm_disk_tool("SavingVM", size_gb=10, storage_domain="DataDomain")
            assert "Current status is 'saving_state'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True

    def test_create_disk_blocked_when_storage_locked(self) -> None:
        mock_client = MagicMock()
        mock_sd = MagicMock(id="sd-uuid-1", name="LockedStorage")
        mock_sd.status = MagicMock(value="locked")
        mock_client.find_resource_by_id_or_name.return_value = mock_sd

        with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
            with pytest.raises(OvirtValidationError) as exc_info:
                create_disk_tool(size_gb=10, storage_domain="LockedStorage")
            assert "Current status is 'locked'" in str(exc_info.value)
            assert exc_info.value.details.get("is_transitional") is True
