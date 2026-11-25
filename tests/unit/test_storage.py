"""Unit tests for Storage Domain management tools."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import OvirtValidationError
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.storage import (
    StorageDomainDetail,
    StorageDomainResult,
    StorageDomainSummary,
)
from ovirt_mcp.tools.storage import (
    ovirt_storage_domain_attach,
    ovirt_storage_domain_create_nfs,
    ovirt_storage_domain_delete,
    ovirt_storage_domain_detach,
    ovirt_storage_domain_get,
    ovirt_storage_domain_list,
    ovirt_storage_domain_maintenance,
)


@pytest.fixture
def mock_client() -> tuple[MagicMock, MagicMock]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys

    mock_sds_svc = MagicMock()
    mock_dcs_svc = MagicMock()
    mock_hosts_svc = MagicMock()
    mock_sys.storage_domains_service.return_value = mock_sds_svc
    mock_sys.data_centers_service.return_value = mock_dcs_svc
    mock_sys.hosts_service.return_value = mock_hosts_svc

    mock_sds_svc.list.return_value = []
    mock_dcs_svc.list.return_value = []
    mock_hosts_svc.list.return_value = []

    return mock_client, mock_sys


def test_storage_domain_list(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    sds_svc = sys_svc.storage_domains_service.return_value
    dcs_svc = sys_svc.data_centers_service.return_value

    mock_sd = MagicMock()
    mock_sd.id = "sd-1"
    mock_sd.name = "DataNFS"
    mock_sd.type = "data"
    mock_sd.storage.type = "nfs"
    mock_sd.storage.address = "192.0.2.20"
    mock_sd.storage.path = "/exports/data"
    mock_sd.available = 100 * (1024**3)
    mock_sd.used = 50 * (1024**3)
    mock_sd.committed = 60 * (1024**3)
    mock_sd.storage_format = "v5"
    sds_svc.list.return_value = [mock_sd]

    # Data Center attachment mock
    mock_dc = MagicMock()
    mock_dc.id = "dc-1"
    mock_dc.name = "DefaultDC"
    dcs_svc.list.return_value = [mock_dc]

    attached_sd = MagicMock()
    attached_sd.id = "sd-1"
    attached_sd.status = "active"
    dcs_svc.data_center_service.return_value.storage_domains_service.return_value.list.return_value = [
        attached_sd
    ]

    with patch("ovirt_mcp.tools.storage.get_client", return_value=client):
        result = ovirt_storage_domain_list()

    assert len(result) == 1
    assert isinstance(result[0], StorageDomainSummary)
    assert result[0].name == "DataNFS"
    assert result[0].available_gb == 100.0
    assert result[0].used_gb == 50.0
    assert result[0].status == "active"
    assert "DefaultDC" in result[0].data_centers


def test_storage_domain_get(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    sds_svc = sys_svc.storage_domains_service.return_value

    mock_sd = MagicMock()
    mock_sd.id = "sd-1"
    mock_sd.name = "DataNFS"
    mock_sd.type = "data"
    mock_sd.storage.type = "nfs"
    mock_sd.available = 100 * (1024**3)
    mock_sd.used = 50 * (1024**3)
    mock_sd.supports_discard = True
    client.find_resource_by_id_or_name.return_value = mock_sd

    sd_svc = MagicMock()
    sds_svc.storage_domain_service.return_value = sd_svc
    sd_svc.get.return_value = mock_sd
    sd_svc.disks_service.return_value.list.return_value = [MagicMock(), MagicMock()]
    sd_svc.templates_service.return_value.list.return_value = []
    sd_svc.vms_service.return_value.list.return_value = [MagicMock()]

    with patch("ovirt_mcp.tools.storage.get_client", return_value=client):
        detail = ovirt_storage_domain_get("DataNFS")

    assert isinstance(detail, StorageDomainDetail)
    assert detail.name == "DataNFS"
    assert detail.disks_count == 2
    assert detail.vms_count == 1
    assert detail.supports_discard is True


def test_storage_domain_get_iscsi_with_lun_serials(
    mock_client: tuple[MagicMock, MagicMock],
) -> None:
    client, sys_svc = mock_client
    sds_svc = sys_svc.storage_domains_service.return_value

    mock_sd = MagicMock()
    mock_sd.id = "sd-iscsi-1"
    mock_sd.name = "SanStorage01"
    mock_sd.type = "data"
    mock_sd.storage.type = "iscsi"
    mock_sd.available = 500 * (1024**3)
    mock_sd.used = 200 * (1024**3)
    mock_sd.storage.address = "10.0.0.50"
    mock_sd.storage.target = "iqn.2000-01.com.example:storage.target01"
    mock_sd.storage.port = 3260

    # LUN mock
    mock_lu = MagicMock()
    mock_lu.id = "1IET_00010001"
    mock_lu.serial = "SN-LUN-998877"
    mock_lu.vendor_id = "SYNOLOGY"
    mock_lu.product_id = "Enterprise-SAN"
    mock_lu.size = 700 * (1024**3)
    mock_lu.target = "iqn.2000-01.com.example:storage.target01"
    mock_lu.address = "10.0.0.50"
    mock_lu.port = 3260
    mock_lu.portal = "10.0.0.50:3260,1"
    mock_lu.paths = 4
    mock_lu.volume_group_id = "vg-uuid-100"
    mock_lu.status = "used"

    mock_sd.storage.logical_units = [mock_lu]
    client.find_resource_by_id_or_name.return_value = mock_sd

    sd_svc = MagicMock()
    sds_svc.storage_domain_service.return_value = sd_svc
    sd_svc.get.return_value = mock_sd
    sd_svc.disks_service.return_value.list.return_value = []
    sd_svc.templates_service.return_value.list.return_value = []
    sd_svc.vms_service.return_value.list.return_value = []

    with patch("ovirt_mcp.tools.storage.get_client", return_value=client):
        detail = ovirt_storage_domain_get("SanStorage01")

    assert isinstance(detail, StorageDomainDetail)
    assert detail.name == "SanStorage01"
    assert detail.storage_type == "iscsi"
    assert "SN-LUN-998877" in detail.lun_serials
    assert detail.lun_count == 1
    assert len(detail.logical_units) == 1

    lu_info = detail.logical_units[0]
    assert lu_info.id == "1IET_00010001"
    assert lu_info.serial == "SN-LUN-998877"
    assert lu_info.vendor_id == "SYNOLOGY"
    assert lu_info.product_id == "Enterprise-SAN"
    assert lu_info.size_gb == 700.0
    assert lu_info.paths == 4
    assert lu_info.portal == "10.0.0.50:3260,1"


def test_storage_domain_get_nas_connections(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    sds_svc = sys_svc.storage_domains_service.return_value

    mock_sd = MagicMock()
    mock_sd.id = "sd-nfs-1"
    mock_sd.name = "NasStorage01"
    mock_sd.type = "data"
    mock_sd.storage.type = "nfs"
    mock_sd.storage.address = "10.0.0.60"
    mock_sd.storage.path = "/volume1/olvm_data"
    mock_sd.storage.nfs_version = "v4_2"
    mock_sd.storage.mount_options = "rw,sync,no_subtree_check"
    mock_sd.storage.logical_units = None

    client.find_resource_by_id_or_name.return_value = mock_sd

    sd_svc = MagicMock()
    sds_svc.storage_domain_service.return_value = sd_svc
    sd_svc.get.return_value = mock_sd
    sd_svc.disks_service.return_value.list.return_value = []
    sd_svc.templates_service.return_value.list.return_value = []
    sd_svc.vms_service.return_value.list.return_value = []

    # Mock storage connections subcollection
    mock_conn = MagicMock()
    mock_conn.id = "conn-uuid-1"
    mock_conn.address = "10.0.0.60"
    mock_conn.path = "/volume1/olvm_data"
    mock_conn.type = "nfs"
    mock_conn.nfs_version = "v4_2"
    mock_conn.mount_options = "rw,sync,no_subtree_check"
    sd_svc.storage_connections_service.return_value.list.return_value = [mock_conn]

    with patch("ovirt_mcp.tools.storage.get_client", return_value=client):
        detail = ovirt_storage_domain_get("NasStorage01")

    assert isinstance(detail, StorageDomainDetail)
    assert detail.name == "NasStorage01"
    assert detail.address == "10.0.0.60"
    assert detail.path == "/volume1/olvm_data"
    assert detail.nfs_version == "v4_2"
    assert detail.mount_options == "rw,sync,no_subtree_check"
    assert len(detail.storage_connections) == 1
    assert detail.storage_connections[0].id == "conn-uuid-1"
    assert detail.storage_connections[0].path == "/volume1/olvm_data"


def test_storage_domain_create_nfs_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    sds_svc = sys_svc.storage_domains_service.return_value
    sds_svc.list.return_value = []

    mock_host = MagicMock()
    mock_host.id = "h-1"
    mock_host.name = "olvmhost001"
    client.find_resource_by_id_or_name.return_value = mock_host

    created_sd = MagicMock()
    created_sd.id = "sd-new-123"
    created_sd.name = "BackupNFS"
    sds_svc.add.return_value = created_sd

    with patch("ovirt_mcp.tools.storage.get_client", return_value=client):
        res = ovirt_storage_domain_create_nfs(
            name="BackupNFS",
            host_name_or_id="olvmhost001",
            address="192.0.2.20",
            path="/exports/backup",
        )

    assert isinstance(res, StorageDomainResult)
    assert res.success is True
    assert res.storage_domain_name == "BackupNFS"
    assert res.action == "create_nfs"
    sds_svc.add.assert_called_once()


def test_storage_domain_create_nfs_duplicate_raises(
    mock_client: tuple[MagicMock, MagicMock],
) -> None:
    client, sys_svc = mock_client
    sds_svc = sys_svc.storage_domains_service.return_value

    existing = MagicMock()
    existing.id = "sd-1"
    existing.name = "ExistingNFS"
    sds_svc.list.return_value = [existing]

    with (
        patch("ovirt_mcp.tools.storage.get_client", return_value=client),
        pytest.raises(OvirtValidationError, match="already exists"),
    ):
        ovirt_storage_domain_create_nfs(
            name="ExistingNFS",
            host_name_or_id="olvmhost001",
            address="192.0.2.20",
            path="/path",
        )


def test_storage_domain_attach_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    dcs_svc = sys_svc.data_centers_service.return_value

    mock_sd = MagicMock()
    mock_sd.id = "sd-1"
    mock_sd.name = "DataNFS"

    mock_dc = MagicMock()
    mock_dc.id = "dc-1"
    mock_dc.name = "DefaultDC"

    client.find_resource_by_id_or_name.side_effect = [mock_sd, mock_dc]
    att_svc = dcs_svc.data_center_service.return_value.storage_domains_service.return_value
    att_svc.list.return_value = []

    with patch("ovirt_mcp.tools.storage.get_client", return_value=client):
        res = ovirt_storage_domain_attach("DataNFS", "DefaultDC")

    assert res.success is True
    assert res.action == "attach"
    att_svc.add.assert_called_once()


def test_storage_domain_maintenance_and_detach(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    dcs_svc = sys_svc.data_centers_service.return_value

    mock_sd = MagicMock()
    mock_sd.id = "sd-1"
    mock_sd.name = "DataNFS"

    mock_dc = MagicMock()
    mock_dc.id = "dc-1"
    mock_dc.name = "DefaultDC"

    client.find_resource_by_id_or_name.side_effect = [mock_sd, mock_dc, mock_sd, mock_dc]

    single_dc_sd = MagicMock()
    dcs_svc.data_center_service.return_value.storage_domains_service.return_value.storage_domain_service.return_value = single_dc_sd
    single_dc_sd.get.return_value.status = "maintenance"

    with patch("ovirt_mcp.tools.storage.get_client", return_value=client):
        m_res = ovirt_storage_domain_maintenance("DataNFS", "DefaultDC")
        assert m_res.action == "maintenance"
        single_dc_sd.deactivate.assert_called_once()

        d_res = ovirt_storage_domain_detach("DataNFS", "DefaultDC")
        assert d_res.action == "detach"
        single_dc_sd.remove.assert_called_once()


def test_storage_domain_detach_blocked_if_active(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    dcs_svc = sys_svc.data_centers_service.return_value

    mock_sd = MagicMock()
    mock_sd.id = "sd-1"
    mock_sd.name = "DataNFS"

    mock_dc = MagicMock()
    mock_dc.id = "dc-1"
    mock_dc.name = "DefaultDC"

    client.find_resource_by_id_or_name.side_effect = [mock_sd, mock_dc]

    single_dc_sd = MagicMock()
    dcs_svc.data_center_service.return_value.storage_domains_service.return_value.storage_domain_service.return_value = single_dc_sd
    single_dc_sd.get.return_value.status = "active"

    with (
        patch("ovirt_mcp.tools.storage.get_client", return_value=client),
        pytest.raises(OvirtValidationError, match="currently 'active'"),
    ):
        ovirt_storage_domain_detach("DataNFS", "DefaultDC")


def test_storage_domain_delete_blocked_if_attached(
    mock_client: tuple[MagicMock, MagicMock],
) -> None:
    client, sys_svc = mock_client
    dcs_svc = sys_svc.data_centers_service.return_value

    mock_sd = MagicMock()
    mock_sd.id = "sd-1"
    mock_sd.name = "DataNFS"
    client.find_resource_by_id_or_name.return_value = mock_sd

    mock_dc = MagicMock()
    mock_dc.name = "DefaultDC"
    dcs_svc.list.return_value = [mock_dc]

    attached_sd = MagicMock()
    attached_sd.id = "sd-1"
    dcs_svc.data_center_service.return_value.storage_domains_service.return_value.list.return_value = [
        attached_sd
    ]

    with (
        patch("ovirt_mcp.tools.storage.get_client", return_value=client),
        patch("ovirt_mcp.tools.guards.get_config", return_value=OvirtConfig(mcp_safe_mode=False)),
        pytest.raises(OvirtValidationError, match="currently attached to Data Center"),
    ):
        ovirt_storage_domain_delete("DataNFS", confirm=True)


def test_storage_domain_delete_success(mock_client: tuple[MagicMock, MagicMock]) -> None:
    client, sys_svc = mock_client
    sds_svc = sys_svc.storage_domains_service.return_value
    dcs_svc = sys_svc.data_centers_service.return_value
    hosts_svc = sys_svc.hosts_service.return_value

    mock_sd = MagicMock()
    mock_sd.id = "sd-1"
    mock_sd.name = "UnattachedNFS"
    client.find_resource_by_id_or_name.return_value = mock_sd
    dcs_svc.list.return_value = []

    mock_spm = MagicMock()
    mock_spm.name = "olvmhost001"
    mock_spm.spm.status = "spm"
    hosts_svc.list.return_value = [mock_spm]

    sd_svc = MagicMock()
    sds_svc.storage_domain_service.return_value = sd_svc

    with (
        patch("ovirt_mcp.tools.storage.get_client", return_value=client),
        patch("ovirt_mcp.tools.guards.get_config", return_value=OvirtConfig(mcp_safe_mode=False)),
    ):
        res = ovirt_storage_domain_delete("UnattachedNFS", confirm=True)

    assert res.success is True
    assert res.action == "delete"
    sd_svc.remove.assert_called_once()
