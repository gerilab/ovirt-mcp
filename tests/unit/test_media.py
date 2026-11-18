"""Unit tests for VM CD-ROM and ISO media tools."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtPermissionError, OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.media import IsoFileInfo, VmCdromInfo, VmCdromResult
from ovirt_mcp.tools.media import (
    attach_vm_iso_tool,
    eject_vm_iso_tool,
    list_storage_isos_tool,
    list_vm_cdroms_tool,
)


def _setup_mock_vm(
    vm_id: str = "vm-uuid-1",
    vm_name: str = "test-vm",
    status_str: str = "down",
    has_cdrom: bool = True,
    current_file_id: str | None = None,
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

    if has_cdrom:
        mock_cdrom = MagicMock()
        mock_cdrom.id = "cdrom-0000"
        if current_file_id:
            mock_file = MagicMock()
            mock_file.id = current_file_id
            mock_cdrom.file = mock_file
        else:
            mock_cdrom.file = None

        mock_vm_service.cdroms_service().list.return_value = [mock_cdrom]
        mock_cdrom_svc = MagicMock()
        mock_vm_service.cdroms_service().cdrom_service.return_value = mock_cdrom_svc
    else:
        mock_vm_service.cdroms_service().list.return_value = []

    return mock_client, mock_vm_service, mock_vm


# ── LIST CD-ROMS TESTS ────────────────────────────────────────────────────────


def test_list_vm_cdroms_success() -> None:
    mock_client, _, _ = _setup_mock_vm(current_file_id="OracleLinux-R8-U10.iso")

    with patch("ovirt_mcp.tools.media.get_client", return_value=mock_client):
        result = list_vm_cdroms_tool("test-vm")

    assert len(result) == 1
    assert isinstance(result[0], VmCdromInfo)
    assert result[0].id == "cdrom-0000"
    assert result[0].file_id == "OracleLinux-R8-U10.iso"
    assert result[0].is_empty is False


def test_list_vm_cdroms_empty() -> None:
    mock_client, _, _ = _setup_mock_vm(current_file_id=None)

    with patch("ovirt_mcp.tools.media.get_client", return_value=mock_client):
        result = list_vm_cdroms_tool("test-vm")

    assert len(result) == 1
    assert result[0].file_id is None
    assert result[0].is_empty is True


# ── ATTACH ISO TESTS ──────────────────────────────────────────────────────────


def test_attach_vm_iso_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        attach_vm_iso_tool("test-vm", iso_file="boot.iso")
    assert "read-only mode" in str(exc_info.value)


def test_attach_vm_iso_empty_filename() -> None:
    with pytest.raises(OvirtValidationError) as exc_info:
        attach_vm_iso_tool("test-vm", iso_file="   ")
    assert "ISO file name cannot be empty" in str(exc_info.value)


def test_attach_vm_iso_no_cdrom() -> None:
    mock_client, _, _ = _setup_mock_vm(has_cdrom=False)

    with patch("ovirt_mcp.tools.media.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            attach_vm_iso_tool("test-vm", iso_file="boot.iso")
        assert "does not have any CD-ROM drives configured" in str(exc_info.value)


def test_attach_vm_iso_stopped_vm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="down")
    mock_cdrom_svc = mock_vm_service.cdroms_service().cdrom_service("cdrom-0000")

    with patch("ovirt_mcp.tools.media.get_client", return_value=mock_client):
        res = attach_vm_iso_tool("test-vm", iso_file="Rocky-9-x86_64.iso")

    assert isinstance(res, VmCdromResult)
    assert res.success is True
    assert res.action == "attach"
    assert res.iso_file == "Rocky-9-x86_64.iso"
    assert res.current is False
    mock_cdrom_svc.update.assert_called_once()


def test_attach_vm_iso_running_vm_hot_swap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="up")
    mock_cdrom_svc = mock_vm_service.cdroms_service().cdrom_service("cdrom-0000")

    with patch("ovirt_mcp.tools.media.get_client", return_value=mock_client):
        res = attach_vm_iso_tool("test-vm", iso_file="Rocky-9-x86_64.iso")

    assert isinstance(res, VmCdromResult)
    assert res.success is True
    assert res.current is True
    # Should call update twice: once persistent (current=False) and once live (current=True)
    assert mock_cdrom_svc.update.call_count == 2


# ── EJECT ISO TESTS ───────────────────────────────────────────────────────────


def test_eject_vm_iso_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        eject_vm_iso_tool("test-vm")
    assert "read-only mode" in str(exc_info.value)


def test_eject_vm_iso_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_vm_service, _ = _setup_mock_vm(status_str="up", current_file_id="boot.iso")
    mock_cdrom_svc = mock_vm_service.cdroms_service().cdrom_service("cdrom-0000")

    with patch("ovirt_mcp.tools.media.get_client", return_value=mock_client):
        res = eject_vm_iso_tool("test-vm")

    assert isinstance(res, VmCdromResult)
    assert res.success is True
    assert res.action == "eject"
    assert res.iso_file is None
    assert mock_cdrom_svc.update.call_count == 2


# ── STORAGE ISO LIST TESTS ────────────────────────────────────────────────────


def test_list_storage_isos_success() -> None:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sds_svc = MagicMock()

    mock_sd_data = MagicMock()
    mock_sd_data.id = "sd-data-1"
    mock_sd_data.name = "Data"
    mock_sd_data.type.value = "data"

    mock_sd_iso = MagicMock()
    mock_sd_iso.id = "sd-iso-1"
    mock_sd_iso.name = "ISO"
    mock_sd_iso.type.value = "iso"

    mock_sds_svc.list.return_value = [mock_sd_data, mock_sd_iso]

    mock_iso_file = MagicMock()
    mock_iso_file.id = "OracleLinux-R8-U10.iso"
    mock_iso_file.name = "OracleLinux-R8-U10.iso"

    mock_files_svc = MagicMock()
    mock_files_svc.list.return_value = [mock_iso_file]
    mock_sds_svc.storage_domain_service("sd-iso-1").files_service.return_value = mock_files_svc

    mock_conn.system_service().storage_domains_service.return_value = mock_sds_svc
    mock_client.get_connection.return_value = mock_conn

    with patch("ovirt_mcp.tools.media.get_client", return_value=mock_client):
        res = list_storage_isos_tool()

    assert len(res) == 1
    assert isinstance(res[0], IsoFileInfo)
    assert res[0].name == "OracleLinux-R8-U10.iso"
    assert res[0].storage_domain_name == "ISO"
