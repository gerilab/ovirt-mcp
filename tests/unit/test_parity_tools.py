"""Unit tests for newly added operational parity tools (vms, hosts, storage)."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.server import mcp
from ovirt_mcp.tools.clusters import (
    create_cluster_tool,
    delete_cluster_tool,
    reset_cluster_emulated_machine_tool,
    sync_all_cluster_networks_tool,
    upgrade_cluster_tool,
)
from ovirt_mcp.tools.datacenters import (
    clean_finished_tasks_datacenter_tool,
    create_datacenter_tool,
    delete_datacenter_tool,
)
from ovirt_mcp.tools.disks import (
    convert_disk_tool,
    delete_disk_tool,
    get_disk_tool,
    reduce_disk_tool,
    refresh_disk_lun_tool,
)
from ovirt_mcp.tools.hosts import (
    approve_host_tool,
    commit_net_config_host_tool,
    copy_host_networks_tool,
    enroll_certificate_host_tool,
    force_select_spm_tool,
    refresh_host_tool,
    sync_all_networks_host_tool,
    update_host_tool,
)
from ovirt_mcp.tools.logical_networks import update_logical_network_tool
from ovirt_mcp.tools.storage import (
    list_unregistered_vms_tool,
    reduce_luns_storage_domain_tool,
    refresh_luns_storage_domain_tool,
    register_unregistered_vm_tool,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_update as update_storage_domain_tool,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_update_ovf_store as update_ovf_store_tool,
)
from ovirt_mcp.tools.templates import export_template_tool, update_template_tool
from ovirt_mcp.tools.vms import (
    add_vm_watchdog_tool,
    attach_vm_host_device_tool,
    auto_pin_vm_tool,
    cancel_vm_migration_tool,
    clone_vm_from_snapshot_tool,
    clone_vm_tool,
    detach_vm_host_device_tool,
    freeze_vm_filesystems_tool,
    list_vm_host_devices_tool,
    list_vm_watchdogs_tool,
    remove_vm_watchdog_tool,
    reset_vm_tool,
    suspend_vm_tool,
    thaw_vm_filesystems_tool,
)

# ── SERVER TOOL REGISTRATION VERIFICATION ─────────────────────────────────────


def test_registered_tools_count() -> None:
    """Verify that all 186 tools are registered in FastMCP."""
    tools = mcp._tool_manager._tools
    assert len(tools) == 186
    assert "ovirt_vm_initialization_set" in tools
    assert "ovirt_vm_initialization_get" in tools
    assert "ovirt_vm_snapshot_clone" in tools
    assert "ovirt_disk_convert" in tools
    assert "ovirt_disk_lun_refresh" in tools
    assert "ovirt_storage_domain_unregistered_vms_list" in tools
    assert "ovirt_storage_domain_unregistered_vm_register" in tools
    assert "ovirt_host_copy_networks" in tools
    assert "ovirt_host_approve" in tools
    assert "ovirt_cluster_upgrade" in tools
    assert "ovirt_vm_watchdog_list" in tools
    assert "ovirt_vm_watchdog_add" in tools
    assert "ovirt_vm_watchdog_remove" in tools
    assert "ovirt_vm_host_device_list" in tools
    assert "ovirt_vm_host_device_attach" in tools
    assert "ovirt_vm_host_device_detach" in tools
    assert "ovirt_host_delete" in tools
    assert "ovirt_host_create" in tools
    assert "ovirt_disk_get" in tools
    assert "ovirt_disk_delete" in tools
    assert "ovirt_vm_clone" in tools
    assert "ovirt_cluster_create" in tools
    assert "ovirt_cluster_delete" in tools
    assert "ovirt_datacenter_create" in tools
    assert "ovirt_datacenter_delete" in tools
    assert "ovirt_host_update" in tools
    assert "ovirt_network_update" in tools
    assert "ovirt_template_update" in tools
    assert "ovirt_storage_domain_update" in tools
    assert "ovirt_vm_cancel_migration" in tools
    assert "ovirt_vm_suspend" in tools
    assert "ovirt_vm_reset" in tools
    assert "ovirt_vm_freeze_filesystems" in tools
    assert "ovirt_vm_thaw_filesystems" in tools
    assert "ovirt_vm_auto_pin" in tools
    assert "ovirt_host_refresh" in tools
    assert "ovirt_host_force_select_spm" in tools
    assert "ovirt_host_enroll_certificate" in tools
    assert "ovirt_host_sync_all_networks" in tools
    assert "ovirt_host_commit_net_config" in tools
    assert "ovirt_storage_domain_update_ovf_store" in tools
    assert "ovirt_storage_domain_refresh_luns" in tools
    assert "ovirt_storage_domain_reduce_luns" in tools
    assert "ovirt_disk_reduce" in tools
    assert "ovirt_cluster_sync_all_networks" in tools
    assert "ovirt_cluster_reset_emulated_machine" in tools
    assert "ovirt_datacenter_clean_finished_tasks" in tools
    assert "ovirt_template_export" in tools


# ── VM CANCEL MIGRATION TESTS ─────────────────────────────────────────────────


def test_cancel_vm_migration_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that cancel_vm_migration raises in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        cancel_vm_migration_tool("vm-01", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_cancel_vm_migration_dry_run() -> None:
    """Test cancel_vm_migration dry-run simulation."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="migrating"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = cancel_vm_migration_tool("vm-01", dry_run=True, confirm=True)
        assert res.success is True
        assert res.dry_run is True
        assert res.action == "cancel_migration"
        assert "DRY RUN" in res.message


def test_cancel_vm_migration_success() -> None:
    """Test successful cancellation of live migration."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="migrating"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_vm_svc = MagicMock()
    mock_client.get_connection().system_service().vms_service().vm_service.return_value = (
        mock_vm_svc
    )

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = cancel_vm_migration_tool("vm-01", dry_run=False, confirm=True)
        assert res.success is True
        assert res.dry_run is False
        mock_vm_svc.cancel_migration.assert_called_once()


# ── VM SUSPEND TESTS ──────────────────────────────────────────────────────────


def test_suspend_vm_blocked_when_not_up() -> None:
    """Test that suspend_vm is blocked if VM is not UP."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="down"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with (
        patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client),
        pytest.raises(
            OvirtValidationError, match="requires the VM to be in one of the following states: 'up'"
        ),
    ):
        suspend_vm_tool("vm-01", confirm=True)


def test_suspend_vm_dry_run() -> None:
    """Test suspend_vm dry run."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = suspend_vm_tool("vm-01", dry_run=True, confirm=True)
        assert res.success is True
        assert res.dry_run is True
        assert res.action == "suspend"


def test_suspend_vm_success() -> None:
    """Test successful VM suspend."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_vm_svc = MagicMock()
    mock_client.get_connection().system_service().vms_service().vm_service.return_value = (
        mock_vm_svc
    )

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = suspend_vm_tool("vm-01", dry_run=False, confirm=True)
        assert res.success is True
        assert res.current_status == "saving_state"
        mock_vm_svc.suspend.assert_called_once()


# ── VM RESET TESTS ────────────────────────────────────────────────────────────


def test_reset_vm_blocked_when_down() -> None:
    """Test that reset_vm is blocked if VM is down."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="down"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with (
        patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client),
        pytest.raises(
            OvirtValidationError,
            match="requires the VM to be in one of the following states: 'up', 'powering_up', 'paused'",
        ),
    ):
        reset_vm_tool("vm-01", confirm=True)


def test_reset_vm_success() -> None:
    """Test successful VM hard reset."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_vm_svc = MagicMock()
    mock_client.get_connection().system_service().vms_service().vm_service.return_value = (
        mock_vm_svc
    )

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = reset_vm_tool("vm-01", dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "reset"
        mock_vm_svc.reset.assert_called_once()


# ── HOST REFRESH & FORCE SPM TESTS ───────────────────────────────────────────


def test_refresh_host_dry_run() -> None:
    """Test refresh_host dry run."""
    mock_host = MagicMock(id="h-1", name="host-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = refresh_host_tool("host-01", dry_run=True)
        assert res.success is True
        assert res.dry_run is True
        assert res.action == "refresh"


def test_refresh_host_success() -> None:
    """Test refresh_host execution."""
    mock_host = MagicMock(id="h-1", name="host-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host
    mock_host_svc = MagicMock()
    mock_client.get_connection().system_service().hosts_service().host_service.return_value = (
        mock_host_svc
    )

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = refresh_host_tool("host-01", dry_run=False)
        assert res.success is True
        mock_host_svc.refresh.assert_called_once()


def test_force_select_spm_blocked_when_maintenance() -> None:
    """Test force_select_spm blocked when host is in maintenance."""
    mock_host = MagicMock(id="h-1", name="host-01", status=MagicMock(value="maintenance"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    with (
        patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="must be 'up'"),
    ):
        force_select_spm_tool("host-01", confirm=True)


def test_force_select_spm_success() -> None:
    """Test force_select_spm execution."""
    mock_host = MagicMock(id="h-1", name="host-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host
    mock_host_svc = MagicMock()
    mock_client.get_connection().system_service().hosts_service().host_service.return_value = (
        mock_host_svc
    )

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = force_select_spm_tool("host-01", dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "force_select_spm"
        mock_host_svc.force_select_spm.assert_called_once()


# ── STORAGE DOMAIN UPDATE OVF STORE TESTS ─────────────────────────────────────


def test_update_ovf_store_dry_run() -> None:
    """Test update_ovf_store dry run."""
    mock_sd = MagicMock(id="sd-1", name="nfs_data")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_sd

    with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
        res = update_ovf_store_tool("nfs_data", dry_run=True)
        assert res.success is True
        assert res.action == "update_ovf_store"
        assert "[DRY RUN]" in res.message


def test_update_ovf_store_success() -> None:
    """Test update_ovf_store execution."""
    mock_sd = MagicMock(id="sd-1", name="nfs_data")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_sd
    mock_sd_svc = MagicMock()
    mock_client.get_connection().system_service().storage_domains_service().storage_domain_service.return_value = mock_sd_svc

    with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
        res = update_ovf_store_tool("nfs_data", dry_run=False)
        assert res.success is True
        mock_sd_svc.update_ovf_store.assert_called_once()


# ── VM FREEZE / THAW / AUTO-PIN TESTS ─────────────────────────────────────────


def test_freeze_vm_filesystems_blocked_when_down() -> None:
    """Test freeze filesystems blocked if VM is down."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="down"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with (
        patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client),
        pytest.raises(
            OvirtValidationError, match="requires the VM to be in one of the following states: 'up'"
        ),
    ):
        freeze_vm_filesystems_tool("vm-01", confirm=True)


def test_freeze_vm_filesystems_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test freeze filesystems blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        freeze_vm_filesystems_tool("vm-01", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_freeze_vm_filesystems_dry_run() -> None:
    """Test freeze filesystems dry run."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = freeze_vm_filesystems_tool("vm-01", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "freeze_filesystems"
        assert res.dry_run is True


def test_freeze_vm_filesystems_success() -> None:
    """Test freeze filesystems execution."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_vm_svc = MagicMock()
    mock_client.get_connection().system_service().vms_service().vm_service.return_value = (
        mock_vm_svc
    )

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = freeze_vm_filesystems_tool("vm-01", dry_run=False, confirm=True)
        assert res.success is True
        mock_vm_svc.freeze_filesystems.assert_called_once()


def test_thaw_vm_filesystems_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test thaw filesystems blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        thaw_vm_filesystems_tool("vm-01", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_thaw_vm_filesystems_dry_run() -> None:
    """Test thaw filesystems dry run."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = thaw_vm_filesystems_tool("vm-01", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "thaw_filesystems"
        assert res.dry_run is True


def test_thaw_vm_filesystems_success() -> None:
    """Test thaw filesystems execution."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_vm_svc = MagicMock()
    mock_client.get_connection().system_service().vms_service().vm_service.return_value = (
        mock_vm_svc
    )

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = thaw_vm_filesystems_tool("vm-01", dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "thaw_filesystems"
        mock_vm_svc.thaw_filesystems.assert_called_once()


def test_auto_pin_vm_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test auto-pin VM blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        auto_pin_vm_tool("vm-01", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_auto_pin_vm_dry_run() -> None:
    """Test auto-pin VM dry run."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = auto_pin_vm_tool("vm-01", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "auto_pin"
        assert res.dry_run is True


def test_auto_pin_vm_success() -> None:
    """Test auto pin VM execution."""
    mock_vm = MagicMock(id="vm-1", name="vm-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_vm_svc = MagicMock()
    mock_client.get_connection().system_service().vms_service().vm_service.return_value = (
        mock_vm_svc
    )

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = auto_pin_vm_tool("vm-01", optimize_cpu_settings=True, dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "auto_pin"
        mock_vm_svc.auto_pin_cpu_and_numa_nodes.assert_called_once_with(optimize_cpu_settings=True)


# ── HOST CERTIFICATE / NETWORKS / COMMIT TESTS ────────────────────────────────


def test_enroll_certificate_host_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test host certificate enrollment blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        enroll_certificate_host_tool("host-01", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_enroll_certificate_host_dry_run() -> None:
    """Test host certificate enrollment dry run."""
    mock_host = MagicMock(id="h-1", name="host-01", status=MagicMock(value="maintenance"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = enroll_certificate_host_tool("host-01", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "enroll_certificate"
        assert res.dry_run is True


def test_enroll_certificate_host_success() -> None:
    """Test host certificate enrollment."""
    mock_host = MagicMock(id="h-1", name="host-01", status=MagicMock(value="maintenance"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host
    mock_host_svc = MagicMock()
    mock_client.get_connection().system_service().hosts_service().host_service.return_value = (
        mock_host_svc
    )

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = enroll_certificate_host_tool("host-01", dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "enroll_certificate"
        mock_host_svc.enroll_certificate.assert_called_once()


def test_sync_all_networks_host_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test host network sync blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        sync_all_networks_host_tool("host-01", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_sync_all_networks_host_dry_run() -> None:
    """Test host network sync dry run."""
    mock_host = MagicMock(id="h-1", name="host-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = sync_all_networks_host_tool("host-01", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "sync_all_networks"
        assert res.dry_run is True


def test_sync_all_networks_host_success() -> None:
    """Test host network sync execution."""
    mock_host = MagicMock(id="h-1", name="host-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host
    mock_host_svc = MagicMock()
    mock_client.get_connection().system_service().hosts_service().host_service.return_value = (
        mock_host_svc
    )

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = sync_all_networks_host_tool("host-01", dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "sync_all_networks"
        mock_host_svc.sync_all_networks.assert_called_once()


def test_commit_net_config_host_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test host network commit blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        commit_net_config_host_tool("host-01", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_commit_net_config_host_dry_run() -> None:
    """Test host network commit dry run."""
    mock_host = MagicMock(id="h-1", name="host-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = commit_net_config_host_tool("host-01", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "commit_net_config"
        assert res.dry_run is True


def test_commit_net_config_host_success() -> None:
    """Test host network commit execution."""
    mock_host = MagicMock(id="h-1", name="host-01", status=MagicMock(value="up"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host
    mock_host_svc = MagicMock()
    mock_client.get_connection().system_service().hosts_service().host_service.return_value = (
        mock_host_svc
    )

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = commit_net_config_host_tool("host-01", dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "commit_net_config"
        mock_host_svc.commit_net_config.assert_called_once()


# ── STORAGE DOMAIN REFRESH / REDUCE LUNS TESTS ────────────────────────────────


def test_refresh_luns_storage_domain_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test storage domain refresh LUNs blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        refresh_luns_storage_domain_tool("san_data", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_refresh_luns_storage_domain_dry_run() -> None:
    """Test storage domain refresh LUNs dry run."""
    mock_sd = MagicMock(id="sd-1", name="san_data")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_sd

    with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
        res = refresh_luns_storage_domain_tool("san_data", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "refresh_luns"
        assert res.dry_run is True


def test_refresh_luns_storage_domain_success() -> None:
    """Test storage domain refresh LUNs execution."""
    mock_sd = MagicMock(id="sd-1", name="san_data")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_sd
    mock_sd_svc = MagicMock()
    mock_client.get_connection().system_service().storage_domains_service().storage_domain_service.return_value = mock_sd_svc

    with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
        res = refresh_luns_storage_domain_tool("san_data", dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "refresh_luns"
        mock_sd_svc.refresh_luns.assert_called_once()


def test_reduce_luns_storage_domain_validation_empty() -> None:
    """Test reduce LUNs raises validation error on empty LUN list."""
    mock_sd = MagicMock(id="sd-1", name="san_data")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_sd

    with (
        patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError, match="At least one LUN ID"),
    ):
        reduce_luns_storage_domain_tool("san_data", logical_units=[], confirm=True)


def test_reduce_luns_storage_domain_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test reduce LUNs blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        reduce_luns_storage_domain_tool("san_data", logical_units=["lun-1"], confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_reduce_luns_storage_domain_dry_run() -> None:
    """Test reduce LUNs dry run."""
    mock_sd = MagicMock(id="sd-1", name="san_data")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_sd

    with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
        res = reduce_luns_storage_domain_tool(
            "san_data", logical_units=["lun-1"], dry_run=True, confirm=True
        )
        assert res.success is True
        assert res.action == "reduce_luns"
        assert res.dry_run is True


def test_reduce_luns_storage_domain_success() -> None:
    """Test reduce LUNs execution."""
    mock_sd = MagicMock(id="sd-1", name="san_data")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_sd
    mock_sd_svc = MagicMock()
    mock_client.get_connection().system_service().storage_domains_service().storage_domain_service.return_value = mock_sd_svc

    with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
        res = reduce_luns_storage_domain_tool(
            "san_data", logical_units=["lun-1", "lun-2"], dry_run=False, confirm=True
        )
        assert res.success is True
        assert res.action == "reduce_luns"
        mock_sd_svc.reduce_luns.assert_called_once()


# ── DISK REDUCE TESTS ─────────────────────────────────────────────────────────


def test_reduce_disk_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test reduce disk blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        reduce_disk_tool("data_disk", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_reduce_disk_dry_run() -> None:
    """Test reduce disk dry run."""
    mock_disk = MagicMock(id="d-1", name="data_disk")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = reduce_disk_tool("data_disk", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "reduce"
        assert res.dry_run is True


def test_reduce_disk_success() -> None:
    """Test reduce disk execution."""
    mock_disk = MagicMock(id="d-1", name="data_disk", status=MagicMock(value="ok"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_disk
    mock_disk_svc = MagicMock()
    mock_disk_svc.get.return_value = mock_disk
    mock_client.get_connection().system_service().disks_service().disk_service.return_value = (
        mock_disk_svc
    )

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = reduce_disk_tool("data_disk", wait=False, dry_run=False, confirm=True)
        assert res.success is True
        mock_disk_svc.reduce.assert_called_once()


# ── CLUSTER SYNC NETWORKS & RESET EMULATED MACHINE TESTS ──────────────────────


def test_sync_all_cluster_networks_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test cluster sync networks blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        sync_all_cluster_networks_tool("Default", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_sync_all_cluster_networks_dry_run() -> None:
    """Test cluster sync networks dry run."""
    mock_cluster = MagicMock(id="c-1", name="Default")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_cluster

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        res = sync_all_cluster_networks_tool("Default", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "sync_all_networks"
        assert res.dry_run is True


def test_sync_all_cluster_networks_success() -> None:
    """Test sync all cluster networks execution."""
    mock_cluster = MagicMock(id="c-1", name="Default")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_cluster
    mock_cluster_svc = MagicMock()
    mock_client.get_connection().system_service().clusters_service().cluster_service.return_value = mock_cluster_svc

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        res = sync_all_cluster_networks_tool("Default", dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "sync_all_networks"
        mock_cluster_svc.sync_all_networks.assert_called_once()


def test_reset_cluster_emulated_machine_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test cluster reset emulated machine blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        reset_cluster_emulated_machine_tool("Default", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_reset_cluster_emulated_machine_dry_run() -> None:
    """Test cluster reset emulated machine dry run."""
    mock_cluster = MagicMock(id="c-1", name="Default")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_cluster

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        res = reset_cluster_emulated_machine_tool("Default", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "reset_emulated_machine"
        assert res.dry_run is True


def test_reset_cluster_emulated_machine_success() -> None:
    """Test reset cluster emulated machine execution."""
    mock_cluster = MagicMock(id="c-1", name="Default")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_cluster
    mock_cluster_svc = MagicMock()
    mock_client.get_connection().system_service().clusters_service().cluster_service.return_value = mock_cluster_svc

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        res = reset_cluster_emulated_machine_tool("Default", dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "reset_emulated_machine"
        mock_cluster_svc.reset_emulated_machine.assert_called_once()


# ── DATA CENTER CLEAN FINISHED TASKS TESTS ────────────────────────────────────


def test_clean_finished_tasks_datacenter_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test clean finished tasks blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        clean_finished_tasks_datacenter_tool("Default_DC", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_clean_finished_tasks_datacenter_dry_run() -> None:
    """Test clean finished tasks dry run."""
    mock_dc = MagicMock(id="dc-1", name="Default_DC")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_dc

    with patch("ovirt_mcp.tools.datacenters.get_client", return_value=mock_client):
        res = clean_finished_tasks_datacenter_tool("Default_DC", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "clean_finished_tasks"
        assert res.dry_run is True


def test_clean_finished_tasks_datacenter_success() -> None:
    """Test clean finished tasks for datacenter."""
    mock_dc = MagicMock(id="dc-1", name="Default_DC")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_dc
    mock_dc_svc = MagicMock()
    mock_client.get_connection().system_service().data_centers_service().data_center_service.return_value = mock_dc_svc

    with patch("ovirt_mcp.tools.datacenters.get_client", return_value=mock_client):
        res = clean_finished_tasks_datacenter_tool("Default_DC", dry_run=False, confirm=True)
        assert res.success is True
        assert res.action == "clean_finished_tasks"
        mock_dc_svc.clean_finished_tasks.assert_called_once()


# ── TEMPLATE EXPORT TESTS ─────────────────────────────────────────────────────


def test_export_template_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test export template blocked in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        export_template_tool("rhel9_template", "export_domain", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_export_template_dry_run() -> None:
    """Test export template dry run."""
    mock_tpl = MagicMock(id="tpl-1", name="rhel9_template")
    mock_sd = MagicMock(id="sd-exp-1", name="export_domain")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.side_effect = [mock_tpl, mock_sd]

    with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
        res = export_template_tool("rhel9_template", "export_domain", dry_run=True, confirm=True)
        assert res.success is True
        assert res.action == "export"
        assert res.dry_run is True


def test_export_template_success() -> None:
    """Test export template execution."""
    mock_tpl = MagicMock(id="tpl-1", name="rhel9_template")
    mock_sd = MagicMock(id="sd-exp-1", name="export_domain")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.side_effect = [mock_tpl, mock_sd]
    mock_tpl_svc = MagicMock()
    mock_client.get_connection().system_service().templates_service().template_service.return_value = mock_tpl_svc

    with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
        res = export_template_tool(
            "rhel9_template", "export_domain", exclusive=True, dry_run=False, confirm=True
        )
        assert res.success is True
        assert res.action == "export"
        mock_tpl_svc.export.assert_called_once()


# ── DISK GET & DELETE TESTS ───────────────────────────────────────────────────


def test_get_disk_tool_success() -> None:
    """Test retrieving details of a virtual disk."""
    mock_disk = MagicMock(
        id="disk-01",
        name="boot_disk_vm01",
        provisioned_size=20 * 1024**3,
        actual_size=5 * 1024**3,
        format=MagicMock(value="cow"),
        content_type=MagicMock(value="data"),
        status=MagicMock(value="ok"),
        storage_domains=[MagicMock(id="sd-01", name="data_domain_01")],
        backup=None,
        backup_mode=None,
        shareable=False,
        read_only=False,
        wipe_after_delete=False,
        sparse=True,
        qcow_version="qcow2_v3",
        sgio=None,
        propagate_errors=None,
        description="Boot disk for test VM",
        comment=None,
    )
    mock_disk.name = "boot_disk_vm01"
    mock_sd = MagicMock(id="sd-01")
    mock_sd.name = "data_domain_01"
    mock_disk.storage_domains = [mock_sd]
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_disk
    mock_client.get_connection().system_service().disks_service().disk_service().statistics_service().list.return_value = []

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        detail = get_disk_tool("boot_disk_vm01")
        assert detail.id == "disk-01"
        assert detail.name == "boot_disk_vm01"
        assert detail.provisioned_size_gb == 20.0
        assert detail.actual_size_gb == 5.0
        assert detail.disk_format == "cow"
        assert detail.storage_domain_name == "data_domain_01"


def test_delete_disk_tool_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test delete_disk raises in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc:
        delete_disk_tool("disk-01", confirm=False)
    assert "confirm=True" in str(exc.value)


def test_delete_disk_tool_locked() -> None:
    """Test delete_disk raises if the disk is locked."""
    mock_disk = MagicMock(id="disk-01", name="disk_01", status=MagicMock(value="locked"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc:
            delete_disk_tool("disk-01", confirm=True)
        assert "locked" in str(exc.value)


def test_delete_disk_tool_dry_run() -> None:
    """Test delete_disk dry-run simulation."""
    mock_disk = MagicMock(id="disk-01", name="disk_01", status=MagicMock(value="ok"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = delete_disk_tool("disk-01", dry_run=True, confirm=True)
        assert res.success is True
        assert res.dry_run is True
        assert "DRY RUN" in res.message


def test_delete_disk_tool_success() -> None:
    """Test successful deletion of virtual disk."""
    mock_disk = MagicMock(id="disk-01", name="disk_01", status=MagicMock(value="ok"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_disk
    mock_disk_svc = MagicMock()
    mock_client.get_connection().system_service().disks_service().disk_service.return_value = (
        mock_disk_svc
    )

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = delete_disk_tool("disk-01", dry_run=False, confirm=True)
        assert res.success is True
        assert res.dry_run is False
        mock_disk_svc.remove.assert_called_once()


# ── VM CLONE TESTS ────────────────────────────────────────────────────────────


def test_clone_vm_tool_duplicate_name() -> None:
    """Test clone_vm raises if target name already exists."""
    mock_src_vm = MagicMock(id="vm-src-1")
    mock_src_vm.name = "web01"
    mock_src_vm.status = MagicMock(value="down")
    mock_existing = MagicMock(id="vm-exist-1")
    mock_existing.name = "web01_clone"
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_src_vm
    mock_vms_svc = mock_client.get_connection().system_service().vms_service()
    mock_vms_svc.list.return_value = [mock_existing]

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc:
            clone_vm_tool("web01", "web01_clone")
        assert "already exists" in str(exc.value)


def test_clone_vm_tool_dry_run() -> None:
    """Test clone_vm dry-run simulation."""
    mock_src_vm = MagicMock(id="vm-src-1")
    mock_src_vm.name = "web01"
    mock_src_vm.status = MagicMock(value="down")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_src_vm
    mock_vms_svc = mock_client.get_connection().system_service().vms_service()
    mock_vms_svc.list.return_value = []

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = clone_vm_tool("web01", "web01_clone", dry_run=True)
        assert res.success is True
        assert res.dry_run is True
        assert res.source_vm_name == "web01"
        assert res.cloned_vm_name == "web01_clone"


def test_clone_vm_tool_success() -> None:
    """Test clone_vm execution."""
    mock_src_vm = MagicMock(id="vm-src-1")
    mock_src_vm.name = "web01"
    mock_src_vm.status = MagicMock(value="down")
    mock_cloned = MagicMock(id="vm-new-1")
    mock_cloned.name = "web01_clone"
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_src_vm
    mock_vms_svc = mock_client.get_connection().system_service().vms_service()
    mock_vms_svc.list.return_value = []
    mock_vm_svc = mock_vms_svc.vm_service.return_value
    mock_vm_svc.clone.return_value = mock_cloned

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = clone_vm_tool("web01", "web01_clone", dry_run=False)
        assert res.success is True
        assert res.cloned_vm_id == "vm-new-1"
        assert res.cloned_vm_name == "web01_clone"
        mock_vm_svc.clone.assert_called_once()


# ── CLUSTER CREATE & DELETE TESTS ─────────────────────────────────────────────


def test_create_cluster_tool_duplicate_name() -> None:
    """Test create_cluster raises if cluster name already exists."""
    mock_existing = MagicMock(id="c-exist-1")
    mock_existing.name = "Production-Cluster"
    mock_client = MagicMock()
    mock_clusters_svc = mock_client.get_connection().system_service().clusters_service()
    mock_clusters_svc.list.return_value = [mock_existing]

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc:
            create_cluster_tool("Production-Cluster", "Default-DC")
        assert "already exists" in str(exc.value)


def test_create_cluster_tool_dry_run() -> None:
    """Test create_cluster dry-run simulation."""
    mock_dc = MagicMock(id="dc-1", name="Default-DC")
    mock_client = MagicMock()
    mock_clusters_svc = mock_client.get_connection().system_service().clusters_service()
    mock_clusters_svc.list.return_value = []
    mock_client.find_resource_by_id_or_name.return_value = mock_dc

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        res = create_cluster_tool(
            "New-Cluster", "Default-DC", cpu_type="Intel SandyBridge", dry_run=True
        )
        assert res.success is True
        assert res.dry_run is True
        assert res.action == "create"
        assert res.cluster_name == "New-Cluster"


def test_create_cluster_tool_success() -> None:
    """Test create_cluster execution."""
    mock_dc = MagicMock(id="dc-1", name="Default-DC")
    mock_created = MagicMock(id="c-created-1", name="New-Cluster")
    mock_client = MagicMock()
    mock_clusters_svc = mock_client.get_connection().system_service().clusters_service()
    mock_clusters_svc.list.return_value = []
    mock_clusters_svc.add.return_value = mock_created
    mock_client.find_resource_by_id_or_name.return_value = mock_dc

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        res = create_cluster_tool(
            "New-Cluster", "Default-DC", cpu_type="Intel SandyBridge", dry_run=False
        )
        assert res.success is True
        assert res.cluster_id == "c-created-1"
        assert res.action == "create"
        mock_clusters_svc.add.assert_called_once()


def test_delete_cluster_tool_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test delete_cluster raises in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc:
        delete_cluster_tool("Old-Cluster", confirm=False)
    assert "confirm=True" in str(exc.value)


def test_delete_cluster_tool_hosts_remain() -> None:
    """Test delete_cluster raises if hosts remain in the cluster."""
    mock_cluster = MagicMock(id="c-1", name="Old-Cluster")
    mock_host = MagicMock(id="h-1", name="node01.example.com")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_cluster
    mock_hosts_svc = mock_client.get_connection().system_service().hosts_service()
    mock_hosts_svc.list.return_value = [mock_host]

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc:
            delete_cluster_tool("Old-Cluster", confirm=True)
        assert "contains 1 host" in str(exc.value)


def test_delete_cluster_tool_success() -> None:
    """Test delete_cluster execution."""
    mock_cluster = MagicMock(id="c-1", name="Empty-Cluster")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_cluster
    sys_svc = mock_client.get_connection().system_service()
    sys_svc.hosts_service().list.return_value = []
    sys_svc.vms_service().list.return_value = []
    mock_c_svc = sys_svc.clusters_service().cluster_service.return_value

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        res = delete_cluster_tool("Empty-Cluster", confirm=True)
        assert res.success is True
        assert res.action == "delete"
        mock_c_svc.remove.assert_called_once()


# ── DATA CENTER CREATE & DELETE TESTS ─────────────────────────────────────────


def test_create_datacenter_tool_duplicate() -> None:
    """Test create_datacenter raises if DC name already exists."""
    mock_existing = MagicMock(id="dc-exist-1")
    mock_existing.name = "Default-DC"
    mock_client = MagicMock()
    mock_dcs_svc = mock_client.get_connection().system_service().data_centers_service()
    mock_dcs_svc.list.return_value = [mock_existing]

    with patch("ovirt_mcp.tools.datacenters.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc:
            create_datacenter_tool("Default-DC")
        assert "already exists" in str(exc.value)


def test_create_datacenter_tool_dry_run() -> None:
    """Test create_datacenter dry-run simulation."""
    mock_client = MagicMock()
    mock_dcs_svc = mock_client.get_connection().system_service().data_centers_service()
    mock_dcs_svc.list.return_value = []

    with patch("ovirt_mcp.tools.datacenters.get_client", return_value=mock_client):
        res = create_datacenter_tool("Branch-DC", local_storage=True, dry_run=True)
        assert res.success is True
        assert res.dry_run is True
        assert res.action == "create"
        assert res.data_center_name == "Branch-DC"


def test_create_datacenter_tool_success() -> None:
    """Test create_datacenter execution."""
    mock_created = MagicMock(id="dc-new-1", name="Branch-DC")
    mock_client = MagicMock()
    mock_dcs_svc = mock_client.get_connection().system_service().data_centers_service()
    mock_dcs_svc.list.return_value = []
    mock_dcs_svc.add.return_value = mock_created

    with patch("ovirt_mcp.tools.datacenters.get_client", return_value=mock_client):
        res = create_datacenter_tool("Branch-DC", local_storage=False, dry_run=False)
        assert res.success is True
        assert res.data_center_id == "dc-new-1"
        assert res.action == "create"
        mock_dcs_svc.add.assert_called_once()


def test_delete_datacenter_tool_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test delete_datacenter raises in Safe Mode without confirm=True."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc:
        delete_datacenter_tool("Old-DC", confirm=False)
    assert "confirm=True" in str(exc.value)


def test_delete_datacenter_tool_clusters_remain() -> None:
    """Test delete_datacenter raises without force=True if clusters remain."""
    mock_dc = MagicMock(id="dc-1", name="Old-DC")
    mock_cluster = MagicMock(id="c-1", name="Attached-Cluster")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_dc
    mock_dc_svc = (
        mock_client.get_connection()
        .system_service()
        .data_centers_service()
        .data_center_service.return_value
    )
    mock_dc_svc.clusters_service().list.return_value = [mock_cluster]

    with patch("ovirt_mcp.tools.datacenters.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc:
            delete_datacenter_tool("Old-DC", force=False, confirm=True)
        assert "contains 1 cluster" in str(exc.value)


def test_delete_datacenter_tool_success() -> None:
    """Test delete_datacenter execution."""
    mock_dc = MagicMock(id="dc-1", name="Empty-DC")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_dc
    mock_dc_svc = (
        mock_client.get_connection()
        .system_service()
        .data_centers_service()
        .data_center_service.return_value
    )
    mock_dc_svc.clusters_service().list.return_value = []
    mock_dc_svc.storage_domains_service().list.return_value = []

    with patch("ovirt_mcp.tools.datacenters.get_client", return_value=mock_client):
        res = delete_datacenter_tool("Empty-DC", force=False, confirm=True)
        assert res.success is True
        assert res.action == "delete"
        mock_dc_svc.remove.assert_called_once()


# ── RESOURCE UPDATE TESTS ─────────────────────────────────────────────────────


def test_update_host_tool_no_fields() -> None:
    """Test update_host raises when no parameters are provided."""
    mock_host = MagicMock(id="h-1", name="node01.example.com")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc:
            update_host_tool("node01.example.com")
        assert "No attributes provided" in str(exc.value)


def test_update_host_tool_success() -> None:
    """Test update_host execution."""
    mock_host = MagicMock(id="h-1", name="node01.example.com")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host
    mock_h_svc = (
        mock_client.get_connection().system_service().hosts_service().host_service.return_value
    )

    with (
        patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client),
        patch("ovirt_mcp.tools.hosts.get_host_tool") as mock_get_host,
    ):
        mock_get_host.return_value = MagicMock(
            id="h-1", name="node01.example.com", comment="Updated comment"
        )
        res = update_host_tool("node01.example.com", comment="Updated comment", dry_run=False)
        assert res.id == "h-1"
        mock_h_svc.update.assert_called_once()


def test_update_logical_network_tool_invalid_vlan() -> None:
    """Test update_logical_network raises on invalid VLAN ID."""
    mock_net = MagicMock(id="net-1", name="vlan100")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_net

    with patch("ovirt_mcp.tools.logical_networks.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc:
            update_logical_network_tool("vlan100", vlan_tag=5000)
        assert "Invalid VLAN tag" in str(exc.value)


def test_update_logical_network_tool_success() -> None:
    """Test update_logical_network execution."""
    mock_net = MagicMock(id="net-1", name="vlan100")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_net
    mock_net_svc = (
        mock_client.get_connection()
        .system_service()
        .networks_service()
        .network_service.return_value
    )

    with (
        patch("ovirt_mcp.tools.logical_networks.get_client", return_value=mock_client),
        patch("ovirt_mcp.tools.logical_networks.get_logical_network_tool") as mock_get_net,
    ):
        mock_get_net.return_value = MagicMock(id="net-1", name="vlan100", mtu=9000)
        res = update_logical_network_tool("vlan100", mtu=9000, dry_run=False)
        assert res.id == "net-1"
        mock_net_svc.update.assert_called_once()


def test_update_template_tool_no_fields() -> None:
    """Test update_template raises when no parameters are provided."""
    mock_tpl = MagicMock(id="tpl-1", name="rhel9-gold")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_tpl

    with patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc:
            update_template_tool("rhel9-gold")
        assert "No attributes provided" in str(exc.value)


def test_update_template_tool_success() -> None:
    """Test update_template execution."""
    mock_tpl = MagicMock(id="tpl-1", name="rhel9-gold")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_tpl
    mock_tpl_svc = (
        mock_client.get_connection()
        .system_service()
        .templates_service()
        .template_service.return_value
    )

    with (
        patch("ovirt_mcp.tools.templates.get_client", return_value=mock_client),
        patch("ovirt_mcp.tools.templates.get_template_tool") as mock_get_tpl,
    ):
        mock_get_tpl.return_value = MagicMock(
            id="tpl-1", name="rhel9-gold", description="Gold master image"
        )
        res = update_template_tool("rhel9-gold", description="Gold master image", dry_run=False)
        assert res.id == "tpl-1"
        mock_tpl_svc.update.assert_called_once()


def test_update_storage_domain_tool_invalid_threshold() -> None:
    """Test update_storage_domain raises on invalid warning threshold."""
    mock_sd = MagicMock(id="sd-1", name="data_nfs")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_sd

    with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc:
            update_storage_domain_tool("data_nfs", warning_low_space_indicator=150)
        assert "between 0 and 100" in str(exc.value)


def test_update_storage_domain_tool_success() -> None:
    """Test update_storage_domain execution."""
    mock_sd = MagicMock(id="sd-1", name="data_nfs")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_sd
    mock_sd_svc = (
        mock_client.get_connection()
        .system_service()
        .storage_domains_service()
        .storage_domain_service.return_value
    )

    with (
        patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client),
        patch("ovirt_mcp.tools.storage.ovirt_storage_domain_get") as mock_get_sd,
    ):
        mock_get_sd.return_value = MagicMock(
            id="sd-1", name="data_nfs", warning_low_space_indicator=15
        )
        res = update_storage_domain_tool("data_nfs", warning_low_space_indicator=15, dry_run=False)
        assert res.id == "sd-1"
        mock_sd_svc.update.assert_called_once()


# ── DISK CONVERT AND LUN REFRESH TESTS ────────────────────────────────────────


def test_convert_disk_tool_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test convert_disk requires confirmation in safe mode."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc:
        convert_disk_tool("disk-1", target_format="cow", confirm=False)
    assert "confirm=True" in str(exc.value)


def test_convert_disk_tool_invalid_format() -> None:
    """Test convert_disk raises on invalid target format."""
    with pytest.raises(OvirtValidationError) as exc:
        convert_disk_tool("disk-1", target_format="vmdk", confirm=True)
    assert "Allowed values are 'cow' or 'raw'" in str(exc.value)


def test_convert_disk_tool_dry_run() -> None:
    """Test convert_disk dry run."""
    mock_disk = MagicMock(id="disk-1", name="disk-01", status=MagicMock(value="ok"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = convert_disk_tool("disk-1", target_format="raw", dry_run=True, confirm=True)
        assert res.success is True
        assert res.dry_run is True
        assert res.action == "convert"


def test_convert_disk_tool_success() -> None:
    """Test convert_disk execution."""
    mock_disk = MagicMock(id="disk-1", name="disk-01", status=MagicMock(value="ok"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_disk
    mock_disk_svc = (
        mock_client.get_connection().system_service().disks_service().disk_service.return_value
    )

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = convert_disk_tool(
            "disk-1", target_format="raw", sparse=False, dry_run=False, confirm=True
        )
        assert res.success is True
        assert res.dry_run is False
        mock_disk_svc.convert.assert_called_once()


def test_refresh_disk_lun_tool_dry_run() -> None:
    """Test refresh_disk_lun dry run."""
    mock_disk = MagicMock(id="lun-1", name="direct-lun-01")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_disk

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = refresh_disk_lun_tool("lun-1", dry_run=True)
        assert res.success is True
        assert res.dry_run is True
        assert res.action == "refresh_lun"


def test_refresh_disk_lun_tool_success() -> None:
    """Test refresh_disk_lun execution."""
    mock_disk = MagicMock(id="lun-1", name="direct-lun-01")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_disk
    mock_disk_svc = (
        mock_client.get_connection().system_service().disks_service().disk_service.return_value
    )

    with patch("ovirt_mcp.tools.disks.get_client", return_value=mock_client):
        res = refresh_disk_lun_tool("lun-1", dry_run=False)
        assert res.success is True
        assert res.dry_run is False
        mock_disk_svc.refresh_lun.assert_called_once()


# ── UNREGISTERED VM TOOLS TESTS ───────────────────────────────────────────────


def test_list_unregistered_vms_tool() -> None:
    """Test listing unregistered VMs from storage domain."""
    mock_sd = MagicMock(id="sd-1", name="export-domain")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_sd

    mock_unreg_vm = MagicMock(
        id="vm-unreg-1",
        status=MagicMock(value="down"),
        memory=1073741824,
        cpu=MagicMock(topology=MagicMock(cores=2, sockets=1, threads=1)),
        description="Unregistered VM",
    )
    mock_unreg_vm.name = "dr-vm-01"
    mock_unreg_vm.cluster = MagicMock()
    mock_unreg_vm.cluster.name = "Cluster-01"
    (
        mock_client.get_connection()
        .system_service()
        .storage_domains_service()
        .storage_domain_service.return_value.vms_service.return_value.list.return_value
    ) = [mock_unreg_vm]

    with (
        patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client),
        patch("ovirt_mcp.tools.storage._is_mock_object", return_value=False),
    ):
        res = list_unregistered_vms_tool("export-domain")
        assert len(res) == 1
        assert res[0].id == "vm-unreg-1"
        assert res[0].name == "dr-vm-01"


def test_register_unregistered_vm_tool_dry_run() -> None:
    """Test register_unregistered_vm dry run."""
    mock_sd = MagicMock(id="sd-1", name="export-domain")
    mock_cluster = MagicMock(id="c-1", name="Production-Cluster")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.side_effect = [mock_sd, mock_cluster]

    with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
        res = register_unregistered_vm_tool(
            storage_domain="export-domain",
            vm_id="vm-unreg-1",
            cluster="Production-Cluster",
            new_name="restored-vm-01",
            dry_run=True,
        )
        assert res.success is True
        assert res.vm_id == "vm-unreg-1"
        assert res.vm_name == "restored-vm-01"


def test_register_unregistered_vm_tool_success() -> None:
    """Test register_unregistered_vm execution."""
    mock_sd = MagicMock(id="sd-1", name="export-domain")
    mock_cluster = MagicMock(id="c-1", name="Production-Cluster")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.side_effect = [mock_sd, mock_cluster]

    mock_vm_svc = (
        mock_client.get_connection()
        .system_service()
        .storage_domains_service()
        .storage_domain_service.return_value.vms_service.return_value.vm_service.return_value
    )
    mock_vm_svc.register.return_value = MagicMock(name="restored-vm-01")

    with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
        res = register_unregistered_vm_tool(
            storage_domain="export-domain",
            vm_id="vm-unreg-1",
            cluster="Production-Cluster",
            new_name="restored-vm-01",
            dry_run=False,
        )
        assert res.success is True
        assert res.vm_name == "restored-vm-01"
        mock_vm_svc.register.assert_called_once()


# ── HOST NETWORK COPY & APPROVE TESTS ─────────────────────────────────────────


def test_copy_host_networks_tool_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test copy_host_networks requires confirmation in safe mode."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc:
        copy_host_networks_tool("host-src", "host-dst", confirm=False)
    assert "confirm=True" in str(exc.value)


def test_copy_host_networks_tool_dry_run() -> None:
    """Test copy_host_networks dry run."""
    mock_src = MagicMock(id="h-src", name="host-01")
    mock_dst = MagicMock(id="h-dst", name="host-02", status=MagicMock(value="maintenance"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.side_effect = [mock_dst, mock_src]

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = copy_host_networks_tool("host-01", "host-02", dry_run=True, confirm=True)
        assert res.success is True
        assert res.dry_run is True
        assert res.action == "copy_networks"


def test_copy_host_networks_tool_success() -> None:
    """Test copy_host_networks execution."""
    mock_src = MagicMock(id="h-src", name="host-01")
    mock_dst = MagicMock(id="h-dst", name="host-02", status=MagicMock(value="maintenance"))
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.side_effect = [mock_dst, mock_src]
    mock_host_svc = (
        mock_client.get_connection().system_service().hosts_service().host_service.return_value
    )

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = copy_host_networks_tool("host-01", "host-02", dry_run=False, confirm=True)
        assert res.success is True
        assert res.dry_run is False
        mock_host_svc.copy_host_networks.assert_called_once()


def test_approve_host_tool_dry_run() -> None:
    """Test approve_host dry run."""
    mock_host = MagicMock(
        id="h-pending", name="host-pending", status=MagicMock(value="pending_approval")
    )
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = approve_host_tool("host-pending", dry_run=True)
        assert res.success is True
        assert res.dry_run is True
        assert res.action == "approve"


def test_approve_host_tool_success() -> None:
    """Test approve_host execution."""
    mock_host = MagicMock(
        id="h-pending", name="host-pending", status=MagicMock(value="pending_approval")
    )
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_host
    mock_host_svc = (
        mock_client.get_connection().system_service().hosts_service().host_service.return_value
    )

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = approve_host_tool("host-pending", activate=True, reboot=False, dry_run=False)
        assert res.success is True
        assert res.dry_run is False
        mock_host_svc.approve.assert_called_once()


# ── CLUSTER UPGRADE TESTS ─────────────────────────────────────────────────────


def test_upgrade_cluster_tool_invalid_action() -> None:
    """Test upgrade_cluster raises on invalid action."""
    with pytest.raises(OvirtValidationError) as exc:
        upgrade_cluster_tool("Cluster-01", action="invalid_action", confirm=True)
    assert "Invalid upgrade action" in str(exc.value)


def test_upgrade_cluster_tool_safe_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test upgrade_cluster requires confirmation in safe mode."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc:
        upgrade_cluster_tool("Cluster-01", action="start", confirm=False)
    assert "confirm=True" in str(exc.value)


def test_upgrade_cluster_tool_dry_run() -> None:
    """Test upgrade_cluster dry run."""
    mock_cluster = MagicMock(id="c-1", name="Production-Cluster")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_cluster

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        res = upgrade_cluster_tool("Production-Cluster", action="start", dry_run=True, confirm=True)
        assert res.success is True
        assert res.dry_run is True
        assert res.action == "upgrade_start"


def test_upgrade_cluster_tool_success() -> None:
    """Test upgrade_cluster execution."""
    mock_cluster = MagicMock(id="c-1", name="Production-Cluster")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_cluster
    mock_cluster_svc = (
        mock_client.get_connection()
        .system_service()
        .clusters_service()
        .cluster_service.return_value
    )

    with patch("ovirt_mcp.tools.clusters.get_client", return_value=mock_client):
        res = upgrade_cluster_tool(
            "Production-Cluster", action="update_progress", percent_complete=50, dry_run=False
        )
        assert res.success is True
        assert res.dry_run is False
        mock_cluster_svc.upgrade.assert_called_once()


# ── VM WATCHDOG TESTS ─────────────────────────────────────────────────────────


def test_vm_watchdog_tools() -> None:
    """Test list, add, and remove VM watchdog devices."""
    mock_vm = MagicMock(id="vm-1", name="vm-01")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    mock_wd = MagicMock(
        id="wd-1",
        model=MagicMock(value="i6300esb"),
        action=MagicMock(value="reset"),
    )
    mock_vms_svc = (
        mock_client.get_connection().system_service().vms_service().vm_service.return_value
    )
    mock_wds_svc = mock_vms_svc.watchdogs_service.return_value
    mock_wds_svc.list.return_value = [mock_wd]

    with (
        patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client),
        patch("ovirt_mcp.tools.vms._is_mock_object", return_value=False),
    ):
        # List
        wds = list_vm_watchdogs_tool("vm-01")
        assert len(wds) == 1
        assert wds[0].model == "i6300esb"

        # Add dry run
        add_dry = add_vm_watchdog_tool("vm-01", model="i6300esb", action="reset", dry_run=True)
        assert add_dry.success is True
        assert add_dry.dry_run is True

        # Add real
        add_real = add_vm_watchdog_tool("vm-01", model="i6300esb", action="reset", dry_run=False)
        assert add_real.success is True
        mock_wds_svc.add.assert_called_once()

        # Remove dry run
        rem_dry = remove_vm_watchdog_tool("vm-01", watchdog_id="wd-1", dry_run=True, confirm=True)
        assert rem_dry.success is True
        assert rem_dry.dry_run is True

        # Remove real
        rem_real = remove_vm_watchdog_tool("vm-01", watchdog_id="wd-1", dry_run=False, confirm=True)
        assert rem_real.success is True
        mock_wds_svc.watchdog_service.return_value.remove.assert_called_once()


# ── VM HOST DEVICE TESTS ──────────────────────────────────────────────────────


def test_vm_host_device_tools() -> None:
    """Test list, attach, and detach VM host devices."""
    mock_vm = MagicMock(id="vm-1", name="vm-01")
    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    mock_dev = MagicMock(
        id="dev-1",
        driver="e1000e",
        iommu_group=12,
    )
    mock_dev.name = "pci_0000_00_1f_6"
    mock_dev.product = MagicMock()
    mock_dev.product.name = "Ethernet Connection"
    mock_dev.vendor = MagicMock()
    mock_dev.vendor.name = "Intel Corp"
    mock_vms_svc = (
        mock_client.get_connection().system_service().vms_service().vm_service.return_value
    )
    mock_devs_svc = mock_vms_svc.host_devices_service.return_value
    mock_devs_svc.list.return_value = [mock_dev]

    with (
        patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client),
        patch("ovirt_mcp.tools.vms._is_mock_object", return_value=False),
    ):
        # List
        devs = list_vm_host_devices_tool("vm-01")
        assert len(devs) == 1
        assert devs[0].name == "pci_0000_00_1f_6"

        # Attach dry run
        att_dry = attach_vm_host_device_tool(
            "vm-01", host_device_name="pci_0000_00_1f_6", dry_run=True
        )
        assert att_dry.success is True
        assert att_dry.dry_run is True

        # Attach real
        att_real = attach_vm_host_device_tool(
            "vm-01", host_device_name="pci_0000_00_1f_6", dry_run=False
        )
        assert att_real.success is True
        mock_devs_svc.add.assert_called_once()

        # Detach dry run
        det_dry = detach_vm_host_device_tool(
            "vm-01", host_device_name="pci_0000_00_1f_6", dry_run=True, confirm=True
        )
        assert det_dry.success is True
        assert det_dry.dry_run is True

        # Detach real
        det_real = detach_vm_host_device_tool(
            "vm-01", host_device_name="pci_0000_00_1f_6", dry_run=False, confirm=True
        )
        assert det_real.success is True
        mock_devs_svc.device_service.return_value.remove.assert_called_once()


# ── VM SNAPSHOT CLONE TESTS ───────────────────────────────────────────────────


def test_clone_vm_from_snapshot_tool() -> None:
    """Test cloning a new VM from a snapshot."""
    mock_src_vm = MagicMock(id="vm-src-1", name="vm-src-01")
    mock_src_vm.cluster = MagicMock(id="c-1", name="Cluster-01")
    mock_snap = MagicMock(id="snap-1", description="Gold-Snapshot")

    mock_client = MagicMock()
    mock_client.find_resource_by_id_or_name.return_value = mock_src_vm

    mock_vms_svc = mock_client.get_connection().system_service().vms_service()
    mock_vms_svc.list.return_value = []
    mock_vms_svc.vm_service.return_value.snapshots_service.return_value.snapshot_service.return_value.get.return_value = mock_snap

    mock_created_vm = MagicMock(id="vm-cloned-1", name="vm-cloned-01")
    mock_vms_svc.add.return_value = mock_created_vm

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        # Dry run
        dry_res = clone_vm_from_snapshot_tool(
            name_or_id="vm-src-01",
            snapshot_id="snap-1",
            new_name="vm-cloned-01",
            dry_run=True,
        )
        assert dry_res.success is True
        assert dry_res.dry_run is True
        assert dry_res.cloned_vm_name == "vm-cloned-01"

        # Real execution
        real_res = clone_vm_from_snapshot_tool(
            name_or_id="vm-src-01",
            snapshot_id="snap-1",
            new_name="vm-cloned-01",
            dry_run=False,
        )
        assert real_res.success is True
        assert real_res.dry_run is False
        assert real_res.cloned_vm_id == "vm-cloned-1"
        mock_vms_svc.add.assert_called_once()
