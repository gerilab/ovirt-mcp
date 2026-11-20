"""Unit tests for enterprise I/O telemetry, per-disk metrics, and storage health monitoring."""

from unittest.mock import MagicMock, patch

from ovirt_mcp.models.disk import DiskIoStats
from ovirt_mcp.models.vm import VmDetail, VmDiskInfo, VmNicInfo, VmNicIoStats
from ovirt_mcp.tools.disks import extract_disk_io_stats
from ovirt_mcp.tools.hosts import get_host_tool
from ovirt_mcp.tools.storage import _build_storage_domain_summary, ovirt_storage_domain_get
from ovirt_mcp.tools.vms import extract_nic_io_stats, extract_vm_runtime_telemetry, get_vm_tool


def _make_stat_mock(name: str, datum: float) -> MagicMock:
    stat = MagicMock()
    stat.name = name
    val = MagicMock()
    val.datum = datum
    stat.values = [val]
    return stat


def test_extract_disk_io_stats_success() -> None:
    """Test extracting real-time DiskIoStats from SDK statistics subcollection."""
    mock_disk_service = MagicMock()
    stats = [
        _make_stat_mock("data.current.read", 10485760.0),  # 10 MB/s
        _make_stat_mock("data.current.write", 5242880.0),  # 5 MB/s
        _make_stat_mock("data.current.read_ops", 2500.0),
        _make_stat_mock("data.current.write_ops", 1200.0),
        _make_stat_mock("disk.read.latency", 0.0035),  # 3.5 ms
        _make_stat_mock("disk.write.latency", 0.0018),  # 1.8 ms
        _make_stat_mock("disk.flush.latency", 0.00005),  # 0.05 ms
    ]
    mock_disk_service.statistics_service().list.return_value = stats

    io_stats = extract_disk_io_stats(mock_disk_service)

    assert io_stats is not None
    assert io_stats.read_bytes_sec == 10485760.0
    assert io_stats.write_bytes_sec == 5242880.0
    assert io_stats.read_mb_sec == 10.0
    assert io_stats.write_mb_sec == 5.0
    assert io_stats.read_iops == 2500.0
    assert io_stats.write_iops == 1200.0
    assert io_stats.read_latency_ms == 3.5
    assert io_stats.write_latency_ms == 1.8
    assert io_stats.flush_latency_ms == 0.05


def test_extract_disk_io_stats_empty_or_failure() -> None:
    """Test graceful handling when statistics are empty or unavailable."""
    mock_disk_service = MagicMock()
    mock_disk_service.statistics_service().list.return_value = []
    assert extract_disk_io_stats(mock_disk_service) is None

    mock_error_service = MagicMock()
    mock_error_service.statistics_service().list.side_effect = Exception("API error")
    assert extract_disk_io_stats(mock_error_service) is None


def test_extract_nic_io_stats_success() -> None:
    """Test extracting real-time VmNicIoStats from NIC statistics subcollection."""
    mock_nic_service = MagicMock()
    stats = [
        _make_stat_mock("data.current.rx", 1048576.0),  # 1 MB/s
        _make_stat_mock("data.current.tx", 2097152.0),  # 2 MB/s
        _make_stat_mock("data.current.rx.bps", 8388608.0),
        _make_stat_mock("data.current.tx.bps", 16777216.0),
        _make_stat_mock("errors.total.rx", 3.0),
        _make_stat_mock("errors.total.tx", 1.0),
        _make_stat_mock("data.total.rx", 50000000.0),
        _make_stat_mock("data.total.tx", 100000000.0),
    ]
    mock_nic_service.statistics_service().list.return_value = stats

    nic_io = extract_nic_io_stats(mock_nic_service)

    assert nic_io is not None
    assert nic_io.rx_bytes_sec == 1048576.0
    assert nic_io.tx_bytes_sec == 2097152.0
    assert nic_io.rx_mb_sec == 1.0
    assert nic_io.tx_mb_sec == 2.0
    assert nic_io.rx_errors == 3
    assert nic_io.tx_errors == 1
    assert nic_io.total_rx_bytes == 50000000
    assert nic_io.total_tx_bytes == 100000000


def test_extract_vm_runtime_telemetry() -> None:
    """Test VM runtime telemetry calculation and disk/NIC aggregation."""
    mock_vm_service = MagicMock()
    vm_stats = [
        _make_stat_mock("cpu.current.guest", 12.5),
        _make_stat_mock("cpu.current.hypervisor", 2.5),
        _make_stat_mock("cpu.current.total", 15.0),
        _make_stat_mock("memory.installed", 16 * 1024**3),
        _make_stat_mock("memory.used", 8 * 1024**3),
        _make_stat_mock("memory.free", 8 * 1024**3),
        _make_stat_mock("memory.buffered", 512 * 1024**2),
        _make_stat_mock("memory.cached", 1024**3),
    ]
    mock_vm_service.statistics_service().list.return_value = vm_stats

    disk1 = VmDiskInfo(
        id="d1",
        name="os-disk",
        size_gb=50.0,
        interface="virtio_scsi",
        io_stats=DiskIoStats(read_mb_sec=2.5, write_mb_sec=1.0, read_iops=100.0, write_iops=50.0),
    )
    disk2 = VmDiskInfo(
        id="d2",
        name="data-disk",
        size_gb=100.0,
        interface="virtio_scsi",
        io_stats=DiskIoStats(read_mb_sec=7.5, write_mb_sec=4.0, read_iops=400.0, write_iops=200.0),
    )

    nic1 = VmNicInfo(
        id="n1",
        name="nic1",
        io_stats=VmNicIoStats(rx_mb_sec=3.0, tx_mb_sec=5.0),
    )

    telem = extract_vm_runtime_telemetry(mock_vm_service, [disk1, disk2], [nic1])

    assert telem is not None
    assert telem.cpu_usage_percent == 15.0
    assert telem.cpu_guest_percent == 12.5
    assert telem.cpu_hypervisor_percent == 2.5
    assert telem.memory_installed_bytes == 16 * 1024**3
    assert telem.memory_used_bytes == 8 * 1024**3
    assert telem.memory_used_percent == 50.0
    assert telem.total_read_mb_sec == 10.0
    assert telem.total_write_mb_sec == 5.0
    assert telem.total_read_iops == 500.0
    assert telem.total_write_iops == 250.0
    assert telem.total_rx_mb_sec == 3.0
    assert telem.total_tx_mb_sec == 5.0


def test_storage_domain_summary_health_and_overcommitment() -> None:
    """Test overcommit_ratio and space_health indicators on StorageDomainSummary."""
    mock_sd = MagicMock()
    mock_sd.id = "sd-1"
    mock_sd.name = "NFS_Data"
    mock_sd.type = "data"
    mock_sd.available = 100 * (1024**3)  # 100 GB free
    mock_sd.used = 100 * (1024**3)  # 100 GB used -> Total 200 GB
    mock_sd.committed = 300 * (1024**3)  # 300 GB committed (1.5x)
    mock_sd.warning_low_space_indicator = 20  # 20%
    mock_sd.critical_space_action_blocker = 10  # 10 GB

    summary = _build_storage_domain_summary(mock_sd, {}, {})

    assert summary.total_gb == 200.0
    assert summary.available_gb == 100.0
    assert summary.used_gb == 100.0
    assert summary.committed_gb == 300.0
    assert summary.overcommit_ratio == 1.5
    assert summary.space_health == "ok"

    # Warning low space test: free space drops to 15% (30 GB out of 200 GB)
    mock_sd.available = 30 * (1024**3)
    mock_sd.used = 170 * (1024**3)
    summary_warn = _build_storage_domain_summary(mock_sd, {}, {})
    assert summary_warn.space_health == "warning_low_space"

    # Critical space test: free space drops to 5 GB (below critical threshold of 10 GB)
    mock_sd.available = 5 * (1024**3)
    mock_sd.used = 195 * (1024**3)
    summary_crit = _build_storage_domain_summary(mock_sd, {}, {})
    assert summary_crit.space_health == "critical_space"


def test_ovirt_storage_domain_get_aggregate_io() -> None:
    """Test ovirt_storage_domain_get computes aggregated I/O and top consumer disks."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_sds_svc = MagicMock()
    mock_sd_svc = MagicMock()
    mock_disks_svc = MagicMock()
    mock_disk_svc1 = MagicMock()
    mock_disk_svc2 = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.storage_domains_service.return_value = mock_sds_svc
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_sys.data_centers_service().list.return_value = []

    mock_sd = MagicMock()
    mock_sd.id = "sd-uuid-1"
    mock_sd.name = "FastData"
    mock_sd.available = 200 * (1024**3)
    mock_sd.used = 100 * (1024**3)
    mock_sd.committed = 300 * (1024**3)
    mock_sd_svc.get.return_value = mock_sd
    mock_sds_svc.storage_domain_service.return_value = mock_sd_svc
    mock_client.find_resource_by_id_or_name.return_value = mock_sd

    # Mock disks in storage domain
    d1 = MagicMock()
    d1.id = "disk-1"
    d1.name = "heavy-db-disk"
    d2 = MagicMock()
    d2.id = "disk-2"
    d2.name = "idle-os-disk"
    mock_sd_svc.disks_service().list.return_value = [d1, d2]
    mock_sd_svc.templates_service().list.return_value = []

    # Mock VMs
    vm1 = MagicMock()
    vm1.name = "database-vm-01"
    mock_sd_svc.vms_service().list.return_value = [vm1]

    # Mock individual disk statistics
    stats_d1 = [
        _make_stat_mock("data.current.read", 20971520.0),  # 20 MB/s
        _make_stat_mock("data.current.write", 10485760.0),  # 10 MB/s
        _make_stat_mock("data.current.read_ops", 4000.0),
        _make_stat_mock("data.current.write_ops", 2000.0),
        _make_stat_mock("disk.read.latency", 0.005),  # 5 ms
        _make_stat_mock("disk.write.latency", 0.002),  # 2 ms
    ]
    mock_disk_svc1.statistics_service().list.return_value = stats_d1
    mock_disk_svc2.statistics_service().list.return_value = []

    def disk_svc_side_effect(did: str) -> MagicMock:
        return mock_disk_svc1 if did == "disk-1" else mock_disk_svc2

    mock_disks_svc.disk_service.side_effect = disk_svc_side_effect

    with patch("ovirt_mcp.tools.storage.get_client", return_value=mock_client):
        detail = ovirt_storage_domain_get("FastData")

    assert detail.name == "FastData"
    assert detail.disks_count == 2
    assert detail.vms_count == 1
    assert detail.vms_list == ["database-vm-01"]
    assert detail.io_stats is not None
    assert detail.io_stats.total_read_mb_sec == 20.0
    assert detail.io_stats.total_write_mb_sec == 10.0
    assert detail.io_stats.total_read_iops == 4000.0
    assert detail.io_stats.total_write_iops == 2000.0
    assert detail.io_stats.avg_read_latency_ms == 5.0
    assert detail.io_stats.avg_write_latency_ms == 2.0
    assert len(detail.top_io_disks) == 1
    assert detail.top_io_disks[0].disk_name == "heavy-db-disk"
    assert detail.top_io_disks[0].read_mb_sec == 20.0


def test_get_host_tool_includes_stats() -> None:
    """Test get_host_tool includes HostStats in HostDetail."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_hosts_svc = MagicMock()
    mock_host_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.hosts_service.return_value = mock_hosts_svc
    mock_hosts_svc.host_service.return_value = mock_host_svc

    mock_host = MagicMock()
    mock_host.id = "host-uuid-1"
    mock_host.name = "olvm01.example.com"
    mock_host.status.value = "up"
    mock_host.cluster.name = "ComputeCluster"
    mock_host.cluster.id = "c-1"
    mock_host.address = "10.0.0.10"
    mock_host.memory = 64 * 1024**3
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    mock_host_svc.nics_service().list.return_value = []
    mock_host_svc.numa_nodes_service().list.return_value = []

    # Mock statistics
    h_stats = [
        _make_stat_mock("cpu.current.idle", 85.0),
        _make_stat_mock("cpu.current.user", 10.0),
        _make_stat_mock("cpu.current.system", 5.0),
        _make_stat_mock("cpu.load.avg.5m", 1.25),
        _make_stat_mock("memory.total", 64.0 * 1024**3),
        _make_stat_mock("memory.used", 32.0 * 1024**3),
        _make_stat_mock("memory.free", 32.0 * 1024**3),
        _make_stat_mock("swap.total", 8.0 * 1024**2),
        _make_stat_mock("swap.used", 0.0),
    ]
    mock_host_svc.statistics_service().list.return_value = h_stats

    with (
        patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client),
        patch("ovirt_mcp.tools.hosts._get_active_vms_on_host", return_value=(2, [])),
    ):
        host_detail = get_host_tool("olvm01.example.com")

    assert host_detail.name == "olvm01.example.com"
    assert host_detail.stats is not None
    assert host_detail.stats.cpu_usage_percent == 15.0  # 100 - 85
    assert host_detail.stats.cpu_load_avg_5m == 1.25
    assert host_detail.stats.memory_used_gb == 32.0


def test_get_vm_tool_with_telemetry() -> None:
    """Test get_vm_tool populates disk io_stats, nic io_stats, and runtime telemetry."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys = MagicMock()
    mock_vms_svc = MagicMock()
    mock_vm_svc = MagicMock()
    mock_disks_svc = MagicMock()
    mock_disk_svc = MagicMock()
    mock_nic_svc = MagicMock()

    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys
    mock_sys.vms_service.return_value = mock_vms_svc
    mock_sys.disks_service.return_value = mock_disks_svc
    mock_sys.storage_domains_service().list.return_value = []
    mock_disks_svc.disk_service.return_value = mock_disk_svc

    mock_vm = MagicMock()
    mock_vm.id = "vm-123"
    mock_vm.name = "web01"
    mock_vm.status.value = "up"
    mock_vm.cpu.topology.sockets = 1
    mock_vm.cpu.topology.cores = 2
    mock_vm.cpu.topology.threads = 1
    mock_vm.cpu.cpu_pinning_policy = None
    mock_vm.auto_pinning_policy = None
    mock_vm.custom_cpu_model = None
    mock_vm.custom_emulated_machine = None
    mock_vm.cpu_shares = None
    mock_vm.memory_policy = None
    mock_vm.memory = 4 * 1024 * 1024 * 1024
    mock_vm.io = None
    mock_vm.virtio_scsi = None
    mock_vm.placement_policy = None
    mock_vm.os = None
    mock_vm.guest_operating_system = None
    mock_vm.guest_time_zone = None
    mock_vm.bios = None
    mock_vm.tpm_enabled = False
    mock_vm.delete_protected = False
    mock_vm.stateless = False
    mock_vm.soundcard_enabled = False
    mock_vm.usb = None
    mock_vm.type = None
    mock_vm.display = None
    mock_vm.high_availability = None
    mock_vm.watchdogs = []
    mock_vm.lease = None
    mock_vm.migration = None
    mock_vm.cluster = None
    mock_vm.host = None
    mock_vm.template = None
    mock_vm.fqdn = None
    mock_vm.description = None
    mock_vm.status_detail = None
    mock_vm.creation_time = None
    mock_vm.start_time = None
    mock_vm.stop_time = None
    mock_vm.stop_reason = None
    mock_vm.next_run_configuration_exists = False
    mock_vm.migration_downtime = None
    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_vms_svc.vm_service.return_value = mock_vm_svc
    mock_client.config.mcp_compact_mode = False

    # Disks
    mock_disk = MagicMock()
    mock_disk.id = "d-123"
    mock_disk.name = "web01-disk"
    mock_disk.provisioned_size = 50 * (1024**3)
    mock_disk.actual_size = 10 * (1024**3)
    mock_disk.format.value = "cow"
    mock_disk.sparse = True
    mock_att = MagicMock()
    mock_att.disk = mock_disk
    mock_att.interface.value = "virtio_scsi"
    mock_att.bootable = False
    mock_att.read_only = False
    mock_vm_svc.disk_attachments_service().list.return_value = [mock_att]
    disk_stats = [
        _make_stat_mock("data.current.read", 1048576.0),
        _make_stat_mock("data.current.write", 2097152.0),
        _make_stat_mock("data.current.read_ops", 120.0),
        _make_stat_mock("data.current.write_ops", 60.0),
        _make_stat_mock("disk.read.latency", 0.002),
        _make_stat_mock("disk.write.latency", 0.001),
        _make_stat_mock("disk.flush.latency", 0.0001),
    ]
    mock_disk_svc.statistics_service().list.return_value = disk_stats

    # NICs
    mock_nic = MagicMock()
    mock_nic.id = "nic-123"
    mock_nic.name = "nic1"
    mock_nic.vnic_profile.name = "ovirtmgmt"
    mock_nic.mac.address = "00:1a:4a:16:01:52"
    mock_nic.interface.value = "virtio"
    mock_nic.linked = True
    mock_vm_svc.nics_service().list.return_value = [mock_nic]
    mock_vm_svc.nics_service().nic_service.return_value = mock_nic_svc
    nic_stats = [
        _make_stat_mock("data.current.rx", 524288.0),
        _make_stat_mock("data.current.tx", 1048576.0),
        _make_stat_mock("errors.total.rx", 0.0),
        _make_stat_mock("errors.total.tx", 0.0),
    ]
    mock_nic_svc.statistics_service().list.return_value = nic_stats

    # VM statistics
    vm_stats = [
        _make_stat_mock("cpu.current.total", 10.0),
        _make_stat_mock("cpu.current.guest", 8.0),
        _make_stat_mock("cpu.current.hypervisor", 2.0),
        _make_stat_mock("memory.installed", 4 * 1024**3),
        _make_stat_mock("memory.used", 2 * 1024**3),
    ]
    mock_vm_svc.statistics_service().list.return_value = vm_stats
    mock_vm_svc.snapshots_service().list.return_value = []
    mock_vm_svc.cdroms_service().list.return_value = []

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        vm_detail = get_vm_tool("web01")

    assert isinstance(vm_detail, VmDetail)
    assert vm_detail.name == "web01"
    assert len(vm_detail.disks) == 1
    assert vm_detail.disks[0].io_stats is not None
    assert vm_detail.disks[0].io_stats.read_mb_sec == 1.0
    assert vm_detail.disks[0].io_stats.write_mb_sec == 2.0
    assert vm_detail.disks[0].io_stats.read_latency_ms == 2.0

    assert len(vm_detail.nics) == 1
    assert vm_detail.nics[0].io_stats is not None
    assert vm_detail.nics[0].io_stats.rx_mb_sec == 0.5
    assert vm_detail.nics[0].io_stats.tx_mb_sec == 1.0

    assert vm_detail.telemetry is not None
    assert vm_detail.telemetry.cpu_usage_percent == 10.0
    assert vm_detail.telemetry.total_read_mb_sec == 1.0
    assert vm_detail.telemetry.total_write_mb_sec == 2.0
    assert vm_detail.telemetry.total_read_iops == 120.0
    assert vm_detail.telemetry.total_write_iops == 60.0
