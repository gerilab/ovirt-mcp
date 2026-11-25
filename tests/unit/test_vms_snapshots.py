"""Unit tests for virtual machine snapshot management tools."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import (
    OvirtPermissionError,
    OvirtValidationError,
)
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.vm import VmSnapshotInfo, VmSnapshotResult
from ovirt_mcp.tools.vms import (
    commit_vm_snapshot_tool,
    create_vm_snapshot_tool,
    delete_vm_snapshot_tool,
    list_vm_snapshots_tool,
    preview_vm_snapshot_tool,
    restore_vm_snapshot_tool,
    undo_vm_snapshot_tool,
)


def _setup_mock_vm(
    vm_id: str = "vm-uuid-1",
    vm_name: str = "test-vm",
    status_str: str = "down",
) -> tuple[MagicMock, MagicMock, MagicMock]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = vm_id
    mock_vm.name = vm_name
    mock_status = MagicMock()
    mock_status.value = status_str
    mock_vm.status = mock_status

    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    return mock_client, mock_vm_service, mock_vm


# ── LIST SNAPSHOTS TESTS ───────────────────────────────────────────────────────


def test_list_vm_snapshots_success() -> None:
    mock_client, mock_vm_service, _ = _setup_mock_vm()

    mock_snap1 = MagicMock()
    mock_snap1.id = "snap-1"
    mock_snap1.description = "Baseline Snapshot"
    mock_snap1.snapshot_status.value = "ok"
    mock_snap1.snapshot_type.value = "regular"
    mock_snap1.date = "2026-11-18T10:00:00Z"
    mock_snap1.persist_memorystate = False

    mock_snap2 = MagicMock()
    mock_snap2.id = "snap-2"
    mock_snap2.description = "Active VM state"
    mock_snap2.snapshot_status.value = "ok"
    mock_snap2.snapshot_type.value = "active"
    mock_snap2.date = None
    mock_snap2.persist_memorystate = False

    mock_vm_service.snapshots_service().list.return_value = [mock_snap1, mock_snap2]

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = list_vm_snapshots_tool("test-vm")

    assert len(res) == 2
    assert isinstance(res[0], VmSnapshotInfo)
    assert res[0].id == "snap-1"
    assert res[0].description == "Baseline Snapshot"
    assert res[0].snapshot_status == "ok"
    assert res[0].snapshot_type == "regular"
    assert res[1].snapshot_type == "active"


# ── CREATE SNAPSHOT TESTS ─────────────────────────────────────────────────────


def test_create_vm_snapshot_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        create_vm_snapshot_tool("test-vm", description="Pre-upgrade")
    assert "read-only mode" in str(exc_info.value)


def test_create_vm_snapshot_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm()

    mock_created = MagicMock()
    mock_created.id = "new-snap-123"
    mock_vm_service.snapshots_service().add.return_value = mock_created

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = create_vm_snapshot_tool(
            "test-vm",
            description="Pre-patching snapshot",
            persist_memory=False,
            wait=False,
        )

    assert isinstance(res, VmSnapshotResult)
    assert res.success is True
    assert res.action == "create"
    assert res.snapshot_id == "new-snap-123"
    assert "Pre-patching snapshot" in res.message


def test_create_vm_snapshot_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_vm_snapshot with dry_run=True returns simulated snapshot without calling SDK add."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm()

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = create_vm_snapshot_tool("test-vm", description="Pre-dry-run", dry_run=True)

    assert res.success is True
    assert res.dry_run is True
    assert "[DRY RUN]" in res.message
    mock_vm_service.snapshots_service().add.assert_not_called()


# ── RESTORE SNAPSHOT TESTS ────────────────────────────────────────────────────


def test_restore_vm_snapshot_safe_mode_unconfirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        restore_vm_snapshot_tool("test-vm", snapshot_id="snap-1", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_restore_vm_snapshot_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        restore_vm_snapshot_tool("test-vm", snapshot_id="snap-1", confirm=True)
    assert "read-only mode" in str(exc_info.value)


def test_restore_vm_snapshot_vm_not_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, _ = _setup_mock_vm(status_str="up")

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            restore_vm_snapshot_tool("test-vm", snapshot_id="snap-1", confirm=True)
        assert "stop the virtual machine first" in str(exc_info.value).lower()


def test_restore_vm_snapshot_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="down")
    mock_snap_svc = MagicMock()
    mock_vm_service.snapshots_service().snapshot_service.return_value = mock_snap_svc

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = restore_vm_snapshot_tool("test-vm", snapshot_id="snap-1", confirm=True, wait=False)

    mock_snap_svc.restore.assert_called_once()
    assert isinstance(res, VmSnapshotResult)
    assert res.success is True
    assert res.action == "restore"
    assert res.snapshot_id == "snap-1"


# ── DELETE SNAPSHOT TESTS ─────────────────────────────────────────────────────


def test_delete_vm_snapshot_safe_mode_unconfirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        delete_vm_snapshot_tool("test-vm", snapshot_id="snap-1", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_delete_vm_snapshot_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        delete_vm_snapshot_tool("test-vm", snapshot_id="snap-1", confirm=True)
    assert "read-only mode" in str(exc_info.value)


def test_delete_vm_snapshot_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm()
    mock_snap_svc = MagicMock()
    mock_vm_service.snapshots_service().snapshot_service.return_value = mock_snap_svc

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = delete_vm_snapshot_tool("test-vm", snapshot_id="snap-1", confirm=True, wait=False)

    mock_snap_svc.remove.assert_called_once()
    assert isinstance(res, VmSnapshotResult)
    assert res.success is True
    assert res.action == "delete"
    assert res.snapshot_id == "snap-1"


# ── RESTORE MEMORY & PREVIEW / COMMIT / UNDO TESTS ─────────────────────────────


def test_restore_vm_snapshot_memory_preflight_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="down")
    mock_snap_svc = MagicMock()
    mock_snap = MagicMock()
    mock_snap.persist_memorystate = False
    mock_snap_svc.get.return_value = mock_snap
    mock_vm_service.snapshots_service().snapshot_service.return_value = mock_snap_svc

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            restore_vm_snapshot_tool(
                "test-vm",
                snapshot_id="snap-1",
                restore_memory=True,
                confirm=True,
            )
        assert "does not have a saved memory state" in str(exc_info.value)


def test_restore_vm_snapshot_with_memory_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="down")
    mock_snap_svc = MagicMock()
    mock_snap = MagicMock()
    mock_snap.persist_memorystate = True
    mock_snap_svc.get.return_value = mock_snap
    mock_vm_service.snapshots_service().snapshot_service.return_value = mock_snap_svc

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = restore_vm_snapshot_tool(
            "test-vm",
            snapshot_id="snap-1",
            restore_memory=True,
            confirm=True,
            wait=False,
        )

    mock_snap_svc.restore.assert_called_once_with(restore_memory=True)
    assert res.success is True
    assert res.restore_memory is True


def test_preview_vm_snapshot_safe_mode_unconfirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        preview_vm_snapshot_tool("test-vm", snapshot_id="snap-1", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_preview_vm_snapshot_memory_preflight_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="down")
    mock_snap_svc = MagicMock()
    mock_snap = MagicMock()
    mock_snap.persist_memorystate = False
    mock_snap_svc.get.return_value = mock_snap
    mock_vm_service.snapshots_service().snapshot_service.return_value = mock_snap_svc

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            preview_vm_snapshot_tool(
                "test-vm",
                snapshot_id="snap-1",
                restore_memory=True,
                confirm=True,
            )
        assert "saved memory state" in str(exc_info.value)


def test_preview_vm_snapshot_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="down")

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = preview_vm_snapshot_tool(
            "test-vm",
            snapshot_id="snap-1",
            restore_memory=False,
            confirm=True,
            wait=False,
        )

    mock_vm_service.preview_snapshot.assert_called_once()
    assert res.success is True
    assert res.action == "preview"
    assert res.snapshot_id == "snap-1"


def test_commit_vm_snapshot_safe_mode_unconfirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        commit_vm_snapshot_tool("test-vm", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_commit_vm_snapshot_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="down")

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = commit_vm_snapshot_tool("test-vm", confirm=True, wait=False)

    mock_vm_service.commit_snapshot.assert_called_once()
    assert res.success is True
    assert res.action == "commit"


def test_undo_vm_snapshot_safe_mode_unconfirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        undo_vm_snapshot_tool("test-vm", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_undo_vm_snapshot_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="down")

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        res = undo_vm_snapshot_tool("test-vm", confirm=True, wait=False)

    mock_vm_service.undo_snapshot.assert_called_once()
    assert res.success is True
    assert res.action == "undo"
