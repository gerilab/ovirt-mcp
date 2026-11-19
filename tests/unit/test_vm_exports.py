"""Unit tests for oVirt / OLVM VM & Disk Export/Import tools."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.compute import VmExportResult, VmImportResult
from ovirt_mcp.models.disk import DiskOperationResult
from ovirt_mcp.tools.vm_exports import (
    export_disk_tool,
    export_vm_tool,
    import_vm_tool,
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


def _setup_mock_context() -> dict[str, Any]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_vms_svc = MagicMock()
    mock_vm_svc = MagicMock()
    mock_sds_svc = MagicMock()
    mock_sd_svc = MagicMock()
    mock_sd_vms_svc = MagicMock()
    mock_clusters_svc = MagicMock()
    mock_hosts_svc = MagicMock()
    mock_disks_svc = MagicMock()
    mock_disk_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vms_service.return_value = mock_vms_svc
    mock_vms_svc.vm_service.return_value = mock_vm_svc
    mock_sys.storage_domains_service.return_value = mock_sds_svc
    mock_sds_svc.storage_domain_service.return_value = mock_sd_svc
    mock_sd_svc.vms_service.return_value = mock_sd_vms_svc
    mock_sys.clusters_service.return_value = mock_clusters_svc
    mock_sys.hosts_service.return_value = mock_hosts_svc
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_disks_svc.disk_service.return_value = mock_disk_svc

    mock_vm = MagicMock(id="vm-1")
    mock_vm.name = "AppVM"
    mock_sd = MagicMock(id="sd-export")
    mock_sd.name = "ExportDomain"
    mock_cluster = MagicMock(id="cl-1")
    mock_cluster.name = "Cluster01"
    mock_host = MagicMock(id="h-1")
    mock_host.name = "Host01"
    mock_disk = MagicMock(id="d-1")
    mock_disk.name = "Disk01"

    return {
        "client": mock_client,
        "vm_svc": mock_vm_svc,
        "sds_svc": mock_sds_svc,
        "sd_svc": mock_sd_svc,
        "sd_vms_svc": mock_sd_vms_svc,
        "clusters_svc": mock_clusters_svc,
        "hosts_svc": mock_hosts_svc,
        "disks_svc": mock_disks_svc,
        "disk_svc": mock_disk_svc,
        "vm": mock_vm,
        "sd": mock_sd,
        "cluster": mock_cluster,
        "host": mock_host,
        "disk": mock_disk,
    }


def test_export_vm_safe_mode() -> None:
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        export_vm_tool("AppVM", storage_domain="ExportDomain", confirm=False)


def test_export_vm_invalid_arguments() -> None:
    with pytest.raises(OvirtValidationError, match="You must specify either"):
        export_vm_tool("AppVM", confirm=True)


def test_export_vm_export_domain_success() -> None:
    ctx = _setup_mock_context()
    ctx["client"].find_resource_by_id_or_name.side_effect = [ctx["vm"], ctx["sd"]]

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.vm_exports.get_client", return_value=ctx["client"]),
    ):
        res = export_vm_tool("AppVM", storage_domain="ExportDomain", confirm=True)

    assert isinstance(res, VmExportResult)
    assert res.success is True
    assert res.format == "export_domain"
    ctx["vm_svc"].export.assert_called_once()


def test_export_vm_ova_success() -> None:
    ctx = _setup_mock_context()
    ctx["client"].find_resource_by_id_or_name.side_effect = [ctx["vm"], ctx["host"]]

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.vm_exports.get_client", return_value=ctx["client"]),
    ):
        res = export_vm_tool(
            "AppVM",
            host="Host01",
            directory="/var/tmp",
            filename="app.ova",
            confirm=True,
        )

    assert isinstance(res, VmExportResult)
    assert res.success is True
    assert res.format == "ova"
    ctx["vm_svc"].export_to_path_on_host.assert_called_once()


def test_import_vm_safe_mode() -> None:
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        import_vm_tool(
            storage_domain="ExportDomain",
            vm_name_or_id="AppVM",
            cluster="Cluster01",
            confirm=False,
        )


def test_import_vm_success() -> None:
    ctx = _setup_mock_context()
    mock_exp_vm = MagicMock(id="exp-vm-1")
    mock_exp_vm.name = "AppVM"
    ctx["sd_vms_svc"].list.return_value = [mock_exp_vm]
    mock_target_vm_svc = MagicMock()
    ctx["sd_vms_svc"].vm_service.return_value = mock_target_vm_svc

    ctx["client"].find_resource_by_id_or_name.side_effect = [ctx["sd"], ctx["cluster"]]

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.vm_exports.get_client", return_value=ctx["client"]),
    ):
        res = import_vm_tool(
            storage_domain="ExportDomain",
            vm_name_or_id="AppVM",
            cluster="Cluster01",
            confirm=True,
        )

    assert isinstance(res, VmImportResult)
    assert res.success is True
    assert res.vm_name == "AppVM"
    mock_target_vm_svc.import_.assert_called_once()


def test_import_vm_not_found_on_domain() -> None:
    ctx = _setup_mock_context()
    ctx["sd_vms_svc"].list.return_value = []
    ctx["client"].find_resource_by_id_or_name.side_effect = [ctx["sd"], ctx["cluster"]]

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.vm_exports.get_client", return_value=ctx["client"]),
        pytest.raises(OvirtValidationError, match="not found on export storage domain"),
    ):
        import_vm_tool(
            storage_domain="ExportDomain",
            vm_name_or_id="AppVM",
            cluster="Cluster01",
            confirm=True,
        )


def test_export_disk_safe_mode() -> None:
    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        pytest.raises(OvirtValidationError, match="explicitly supply confirm=True"),
    ):
        export_disk_tool("Disk01", storage_domain="ExportDomain", confirm=False)


def test_export_disk_success() -> None:
    ctx = _setup_mock_context()
    ctx["client"].find_resource_by_id_or_name.side_effect = [ctx["disk"], ctx["sd"]]

    with (
        patch("ovirt_mcp.tools.guards.get_config", return_value=_safe_mode_config(True)),
        patch("ovirt_mcp.tools.vm_exports.get_client", return_value=ctx["client"]),
    ):
        res = export_disk_tool("Disk01", storage_domain="ExportDomain", confirm=True)

    assert isinstance(res, DiskOperationResult)
    assert res.success is True
    assert res.action == "export"
    ctx["disk_svc"].export.assert_called_once()
