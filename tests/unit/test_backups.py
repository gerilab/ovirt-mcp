"""Unit tests for oVirt / OLVM VM Backups and Checkpoints tools."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.tools.backups import (
    delete_vm_checkpoint_tool,
    finalize_vm_backup_tool,
    get_vm_backup_tool,
    get_vm_checkpoint_tool,
    list_vm_backups_tool,
    list_vm_checkpoints_tool,
    start_vm_backup_tool,
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


def _setup_mock_vm_context() -> dict[str, Any]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_vms_svc = MagicMock()
    mock_vm_svc = MagicMock()
    mock_cps_svc = MagicMock()
    mock_bks_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vms_service.return_value = mock_vms_svc
    mock_vms_svc.vm_service.return_value = mock_vm_svc
    mock_vm_svc.checkpoints_service.return_value = mock_cps_svc
    mock_vm_svc.backups_service.return_value = mock_bks_svc

    mock_vm = MagicMock()
    mock_vm.id = "vm-100"
    mock_vm.name = "ProdVM01"
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    return {
        "client": mock_client,
        "vms_svc": mock_vms_svc,
        "vm_svc": mock_vm_svc,
        "cps_svc": mock_cps_svc,
        "bks_svc": mock_bks_svc,
        "vm": mock_vm,
    }


def test_list_vm_checkpoints_tool() -> None:
    ctx = _setup_mock_vm_context()
    cp1 = MagicMock()
    cp1.id = "cp-1"
    cp1.parent_id = None
    cp1.creation_date = "2026-03-01T10:00:00Z"
    disk1 = MagicMock(id="disk-1")
    cp1.disks = [disk1]
    cp1.description = "Initial backup checkpoint"

    cp2 = MagicMock()
    cp2.id = "cp-2"
    cp2.parent_id = "cp-1"
    cp2.creation_date = "2026-03-02T10:00:00Z"
    cp2.disks = [disk1]
    cp2.description = None

    ctx["cps_svc"].list.return_value = [cp1, cp2]

    with patch("ovirt_mcp.tools.backups.get_client", return_value=ctx["client"]):
        res = list_vm_checkpoints_tool("ProdVM01")

    assert len(res) == 2
    assert res[0].id == "cp-1"
    assert res[0].vm_id == "vm-100"
    assert res[0].vm_name == "ProdVM01"
    assert res[0].disk_ids == ["disk-1"]
    assert res[1].id == "cp-2"
    assert res[1].parent_id == "cp-1"


def test_get_vm_checkpoint_tool() -> None:
    ctx = _setup_mock_vm_context()
    cp_svc = MagicMock()
    ctx["cps_svc"].checkpoint_service.return_value = cp_svc

    cp = MagicMock()
    cp.id = "cp-1"
    cp.parent_id = None
    cp.creation_date = "2026-03-01T10:00:00Z"
    cp.disks = [MagicMock(id="d-1")]
    cp.description = "Test CP"
    cp_svc.get.return_value = cp

    with patch("ovirt_mcp.tools.backups.get_client", return_value=ctx["client"]):
        res = get_vm_checkpoint_tool("ProdVM01", "cp-1")

    assert res.id == "cp-1"
    assert res.vm_name == "ProdVM01"
    assert res.disk_ids == ["d-1"]


def test_get_vm_checkpoint_tool_not_found() -> None:
    ctx = _setup_mock_vm_context()
    cp_svc = MagicMock()
    ctx["cps_svc"].checkpoint_service.return_value = cp_svc
    cp_svc.get.return_value = None

    with (
        patch("ovirt_mcp.tools.backups.get_client", return_value=ctx["client"]),
        pytest.raises(OvirtValidationError),
    ):
        get_vm_checkpoint_tool("ProdVM01", "cp-unknown")


def test_delete_vm_checkpoint_tool_safe_mode() -> None:
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        delete_vm_checkpoint_tool("ProdVM01", "cp-1", confirm=False)


def test_delete_vm_checkpoint_tool_success() -> None:
    ctx = _setup_mock_vm_context()
    cp_svc = MagicMock()
    ctx["cps_svc"].checkpoint_service.return_value = cp_svc

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.backups.get_client", return_value=ctx["client"]),
    ):
        res = delete_vm_checkpoint_tool("ProdVM01", "cp-1", confirm=True)

    assert res.status == "deleted"
    assert res.checkpoint_id == "cp-1"
    cp_svc.remove.assert_called_once()


def test_list_vm_backups_tool() -> None:
    ctx = _setup_mock_vm_context()
    b1 = MagicMock()
    b1.id = "b-1"
    b1.phase.value = "ready"
    b1.creation_date = "2026-03-01T10:00:00Z"
    b1.modification_date = "2026-03-01T10:05:00Z"
    b1.from_checkpoint_id = None
    b1.to_checkpoint_id = "cp-1"
    b1.disks = [MagicMock(id="d-1")]
    b1.snapshot.id = "snap-1"
    b1.description = "Full daily backup"

    ctx["bks_svc"].list.return_value = [b1]

    with patch("ovirt_mcp.tools.backups.get_client", return_value=ctx["client"]):
        res = list_vm_backups_tool("ProdVM01")

    assert len(res) == 1
    assert res[0].id == "b-1"
    assert res[0].phase == "ready"
    assert res[0].to_checkpoint_id == "cp-1"
    assert res[0].disk_ids == ["d-1"]
    assert res[0].snapshot_id == "snap-1"


def test_get_vm_backup_tool() -> None:
    ctx = _setup_mock_vm_context()
    bk_svc = MagicMock()
    ctx["bks_svc"].backup_service.return_value = bk_svc

    b = MagicMock()
    b.id = "b-2"
    b.phase.value = "succeeded"
    b.creation_date = "2026-03-02T10:00:00Z"
    b.modification_date = "2026-03-02T10:15:00Z"
    b.from_checkpoint_id = "cp-1"
    b.to_checkpoint_id = "cp-2"
    b.disks = [MagicMock(id="d-1")]
    b.snapshot = None
    b.description = "Incremental backup"
    bk_svc.get.return_value = b

    with patch("ovirt_mcp.tools.backups.get_client", return_value=ctx["client"]):
        res = get_vm_backup_tool("ProdVM01", "b-2")

    assert res.id == "b-2"
    assert res.phase == "succeeded"
    assert res.from_checkpoint_id == "cp-1"


def test_start_vm_backup_tool_safe_mode() -> None:
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        start_vm_backup_tool("ProdVM01", confirm=False)


def test_start_vm_backup_tool_success() -> None:
    ctx = _setup_mock_vm_context()
    new_b = MagicMock()
    new_b.id = "b-new"
    new_b.phase.value = "initializing"
    new_b.to_checkpoint_id = "cp-new"
    ctx["bks_svc"].add.return_value = new_b

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.backups.get_client", return_value=ctx["client"]),
    ):
        res = start_vm_backup_tool(
            "ProdVM01",
            from_checkpoint_id="cp-1",
            disk_ids=["d-1"],
            description="Incremental CBT",
            confirm=True,
        )

    assert res.status == "initiated"
    assert res.backup_id == "b-new"
    assert res.checkpoint_id == "cp-new"
    assert res.phase == "initializing"
    ctx["bks_svc"].add.assert_called_once()


def test_finalize_vm_backup_tool_safe_mode() -> None:
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        finalize_vm_backup_tool("ProdVM01", "b-1", confirm=False)


def test_finalize_vm_backup_tool_success() -> None:
    ctx = _setup_mock_vm_context()
    bk_svc = MagicMock()
    ctx["bks_svc"].backup_service.return_value = bk_svc

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.backups.get_client", return_value=ctx["client"]),
    ):
        res = finalize_vm_backup_tool("ProdVM01", "b-1", confirm=True)

    assert res.status == "finalized"
    assert res.backup_id == "b-1"
    bk_svc.finalize.assert_called_once()
