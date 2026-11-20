"""Unit tests for virtual machine tools."""

from unittest.mock import MagicMock, patch

from ovirt_mcp.models.vm import VmCompactDetail, VmDetail
from ovirt_mcp.tools.vms import extract_vm_summary, get_vm_tool, list_vms_tool


def test_extract_vm_summary() -> None:
    """Test extracting VmSummary from a mock oVirt SDK VM."""
    mock_vm = MagicMock()
    mock_vm.id = "1111-2222-3333-4444"
    mock_vm.name = "web-prod-01"

    mock_status = MagicMock()
    mock_status.value = "up"
    mock_vm.status = mock_status

    mock_cluster = MagicMock()
    mock_cluster.name = "Production-Cluster"
    mock_vm.cluster = mock_cluster

    mock_host = MagicMock()
    mock_host.name = "node-01.corp"
    mock_vm.host = mock_host

    mock_vm.memory = 8 * 1024 * 1024 * 1024  # 8 GB in bytes

    mock_topo = MagicMock()
    mock_topo.sockets = 2
    mock_topo.cores = 4
    mock_topo.threads = 1
    mock_cpu = MagicMock()
    mock_cpu.topology = mock_topo
    mock_vm.cpu = mock_cpu

    mock_ip = MagicMock()
    mock_ip.address = "10.0.0.50"
    mock_dev = MagicMock()
    mock_dev.ips = [mock_ip]
    mock_vm.guest_reported_devices = [mock_dev]

    mock_vm.fqdn = "web-prod-01.corp.internal"
    mock_vm.os.type = "rhel_8x64"
    mock_vm.high_availability.enabled = True
    mock_vm.description = "Production Web Server"

    summary = extract_vm_summary(mock_vm)

    assert summary.id == "1111-2222-3333-4444"
    assert summary.name == "web-prod-01"
    assert summary.status == "up"
    assert summary.cluster_name == "Production-Cluster"
    assert summary.host_name == "node-01.corp"
    assert summary.memory_mb == 8192
    assert summary.cpu_cores == 8
    assert summary.ip_addresses == ["10.0.0.50"]
    assert summary.fqdn == "web-prod-01.corp.internal"
    assert summary.os_type == "rhel_8x64"
    assert summary.ha_enabled is True
    assert summary.description == "Production Web Server"


def test_list_vms_tool_with_filters() -> None:
    """Test list_vms_tool constructs search queries correctly."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()

    mock_vms_service.list.return_value = []
    mock_system.vms_service.return_value = mock_vms_service
    mock_system.clusters_service.return_value.list.return_value = []
    mock_system.hosts_service.return_value.list.return_value = []
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        results = list_vms_tool(cluster="Default", status="up", max_results=25)
        assert results == []
        mock_vms_service.list.assert_called_once_with(
            search='cluster="Default" and status="up"',
            max=25,
            follow="reported_devices",
        )


def test_get_vm_tool() -> None:
    """Test get_vm_tool retrieves full details including cpu, memory, io, affinity, disks, and nics."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "vm-uuid-1234"
    mock_vm.name = "db-server"
    mock_vm.status.value = "up"
    mock_vm.status_detail = None
    mock_vm.cluster.id = "cluster-uuid-1"
    mock_vm.cluster.name = "DbCluster"
    mock_vm.host.name = "node01"
    mock_vm.template.name = "rhel8-template"
    mock_vm.description = "Main DB"

    # CPU
    mock_vm.cpu.topology.sockets = 2
    mock_vm.cpu.topology.cores = 4
    mock_vm.cpu.topology.threads = 1
    mock_vm.cpu_shares = 1024
    mock_vm.cpu.cpu_pinning_policy.value = "manual"
    mock_vm.auto_pinning_policy.value = "disabled"
    mock_vm.custom_cpu_model = "Haswell-noTSX"
    mock_vm.custom_emulated_machine = "pc-q35"

    # Memory
    mock_vm.memory = 16 * 1024 * 1024 * 1024
    mock_vm.memory_policy.guaranteed = 8 * 1024 * 1024 * 1024
    mock_vm.memory_policy.max = 32 * 1024 * 1024 * 1024
    mock_vm.memory_policy.ballooning = True
    mock_vm.memory_policy.over_commit.percent = 150

    # I/O and SCSI
    mock_vm.io.threads = 2
    mock_vm.virtio_scsi = MagicMock()
    mock_vm.virtio_scsi_multi_queues = 4
    mock_vm.virtio_scsi_multi_queues_enabled = True
    mock_vm.multi_queues_enabled = True

    # Affinity and Placement
    mock_ag = MagicMock()
    mock_ag.name = "db-anti-affinity"
    mock_v_ref = MagicMock()
    mock_v_ref.id = "vm-uuid-1234"
    mock_ag.vms = [mock_v_ref]
    mock_system.clusters_service.return_value.cluster_service.return_value.affinity_groups_service.return_value.list.return_value = [
        mock_ag
    ]

    mock_lbl = MagicMock()
    mock_lbl.name = "database-nodes"
    mock_vm_service.affinity_labels_service.return_value.list.return_value = [mock_lbl]

    mock_tag = MagicMock()
    mock_tag.name = "production"
    mock_vm_service.tags_service.return_value.list.return_value = [mock_tag]

    mock_vm.placement_policy.affinity.value = "migratable"
    mock_ph = MagicMock()
    mock_ph.name = "node01"
    mock_vm.placement_policy.hosts = [mock_ph]

    # OS & Guest Agent
    mock_vm.os.type = "rhel_8x64"
    mock_vm.guest_operating_system.distribution = "Red Hat Enterprise Linux"
    mock_vm.guest_operating_system.kernel.version = "4.18.0-425.el8.x86_64"
    mock_vm.guest_operating_system.architecture = "x86_64"
    mock_vm.guest_time_zone.name = "Europe/Budapest"
    mock_vm.fqdn = "db-server.prod.corp"

    # Hardware & Security
    mock_vm.bios.type.value = "q35_ovmf"
    mock_vm.tpm_enabled = True
    mock_vm.delete_protected = True
    mock_vm.stateless = False
    mock_vm.soundcard_enabled = False
    mock_vm.usb.enabled = True
    mock_vm.type.value = "server"
    mock_vm.display.type.value = "vnc"
    mock_cd = MagicMock()
    mock_cd.file.id = "RHEL-8.10-x86_64-dvd.iso"
    mock_vm_service.cdroms_service.return_value.list.return_value = [mock_cd]

    # HA
    mock_vm.high_availability.enabled = True
    mock_vm.high_availability.priority = 100
    mock_vm.watchdogs = []
    mock_vm.lease = None

    # Migration
    mock_vm.migration.auto_converge.value = "inherit"
    mock_vm.migration.compressed.value = "inherit"
    mock_vm.migration.encrypted.value = "inherit"
    mock_vm.migration.policy = None
    mock_vm.migration.parallel_migrations_policy.value = "inherit"
    mock_vm.migration.custom_parallel_migrations = None
    mock_vm.migration_downtime = 500

    # Lifecycle
    mock_vm.creation_time = "2026-01-01T00:00:00Z"
    mock_vm.start_time = "2026-11-18T10:00:00Z"
    mock_vm.stop_time = None
    mock_vm.stop_reason = None
    mock_vm.next_run_configuration_exists = False
    mock_vm.migration_downtime = 500

    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.config.mcp_compact_mode = False

    # Disks
    mock_disk = MagicMock()
    mock_disk.id = "disk-uuid-1"
    mock_disk.alias = "db-data"
    mock_disk.provisioned_size = 100 * (1024**3)
    mock_disk.actual_size = 25 * (1024**3)
    mock_disk.format.value = "cow"
    mock_disk.sparse = True
    mock_att = MagicMock()
    mock_att.id = "att-1"
    mock_att.disk = mock_disk
    mock_att.interface.value = "virtio_scsi"
    mock_att.bootable = True
    mock_att.read_only = False
    mock_vm_service.disk_attachments_service.return_value.list.return_value = [mock_att]

    # NICs
    mock_nic = MagicMock()
    mock_nic.id = "nic-1"
    mock_nic.name = "nic1"
    mock_nic.mac.address = "00:1a:4a:16:01:52"
    mock_nic.interface.value = "virtio"
    mock_nic.vnic_profile.name = "ovirtmgmt"
    mock_nic.linked = True
    mock_vm_service.nics_service.return_value.list.return_value = [mock_nic]

    # Snapshots
    mock_vm_service.snapshots_service.return_value.list.return_value = [MagicMock(), MagicMock()]

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        detail = get_vm_tool("db-server")
        assert isinstance(detail, VmDetail)
        assert detail.id == "vm-uuid-1234"
        assert detail.name == "db-server"
        assert detail.status == "up"

        # CPU verification
        assert detail.cpu.total_cores == 8
        assert detail.cpu.sockets == 2
        assert detail.cpu.cores_per_socket == 4
        assert detail.cpu.pinning_policy == "manual"
        assert detail.cpu.auto_pinning_policy == "disabled"
        assert detail.cpu.custom_cpu_model == "Haswell-noTSX"
        assert detail.cpu.custom_emulated_machine == "pc-q35"

        # Memory verification
        assert detail.memory.allocated_mb == 16384
        assert detail.memory.guaranteed_mb == 8192
        assert detail.memory.max_memory_mb == 32768
        assert detail.memory.ballooning_enabled is True
        assert detail.memory.over_commit_percent == 150

        # I/O and SCSI verification
        assert detail.io_scsi.io_threads == 2
        assert detail.io_scsi.virtio_scsi_enabled is True
        assert detail.io_scsi.virtio_scsi_multi_queues == 4
        assert detail.io_scsi.virtio_scsi_multi_queues_enabled is True

        # Affinity verification
        assert detail.affinity_and_placement.affinity_groups == ["db-anti-affinity"]
        assert detail.affinity_and_placement.affinity_labels == ["database-nodes"]
        assert detail.affinity_and_placement.tags == ["production"]
        assert detail.affinity_and_placement.pinned_hosts == ["node01"]

        # Hardware & Security verification
        assert detail.hardware.bios_type == "q35_ovmf"
        assert detail.hardware.tpm_enabled is True
        assert detail.hardware.delete_protected is True
        assert detail.hardware.cdrom_iso == "RHEL-8.10-x86_64-dvd.iso"
        assert detail.hardware.display_type == "vnc"

        # Migration verification
        assert detail.migration.auto_converge == "inherit"
        assert detail.migration.compressed == "inherit"
        assert detail.migration.downtime_ms == 500

        # Disks verification
        assert len(detail.disks) == 1
        assert detail.disks[0].name == "db-data"
        assert detail.disks[0].size_gb == 100.0
        assert detail.disks[0].actual_size_gb == 25.0
        assert detail.disks[0].format == "cow"
        assert detail.disks[0].sparse is True

        # NICs verification
        assert len(detail.nics) == 1
        assert detail.nics[0].network_name == "ovirtmgmt"
        assert detail.nics[0].linked is True
        assert detail.snapshots_count == 2


def test_get_vm_tool_compact() -> None:
    """Test get_vm_tool returns VmCompactDetail when compact=True."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_vms_service = MagicMock()
    mock_vm_service = MagicMock()

    mock_vm = MagicMock()
    mock_vm.id = "vm-uuid-999"
    mock_vm.name = "light-web"
    mock_vm.status.value = "up"
    mock_vm.cluster.name = "WebCluster"
    mock_vm.host.name = "node02"
    mock_vm.memory = 4 * 1024 * 1024 * 1024
    mock_vm.cpu.topology.sockets = 1
    mock_vm.cpu.topology.cores = 2
    mock_vm.cpu.topology.threads = 1
    mock_vm.os.type = "rhel_9x64"
    mock_vm.high_availability.enabled = False
    mock_vm.description = "Lightweight node"
    mock_vm.fqdn = "light-web.local"
    mock_vm.guest_reported_devices = []

    mock_att = MagicMock()
    mock_att.disk.alias = "os-disk"
    mock_att.disk.provisioned_size = 20 * (1024**3)
    mock_vm_service.disk_attachments_service.return_value.list.return_value = [mock_att]
    mock_vm_service.nics_service.return_value.list.return_value = [MagicMock()]
    mock_vm_service.snapshots_service.return_value.list.return_value = []

    mock_client.find_resource_by_id_or_name.return_value = mock_vm
    mock_vms_service.vm_service.return_value = mock_vm_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.config.mcp_compact_mode = False

    with patch("ovirt_mcp.tools.vms.get_client", return_value=mock_client):
        result = get_vm_tool("light-web", compact=True)
        assert isinstance(result, VmCompactDetail)
        assert result.id == "vm-uuid-999"
        assert result.name == "light-web"
        assert result.cpu_cores == 2
        assert result.memory_mb == 4096
        assert result.disks_summary == ["os-disk (20.0 GB)"]
        assert result.nics_count == 1
        assert result.snapshots_count == 0


def test_extract_vm_summary_with_sdk_reported_devices() -> None:
    """Test extracting IP addresses when oVirt SDK populates reported_devices."""
    mock_vm = MagicMock()
    mock_vm.id = "test-uuid"
    mock_vm.name = "test-vm"
    mock_vm.status.value = "up"
    mock_vm.cluster.name = "Default"
    mock_vm.host.name = "host1"
    mock_vm.memory = 2 * 1024 * 1024 * 1024
    mock_vm.cpu.topology.sockets = 1
    mock_vm.cpu.topology.cores = 2
    mock_vm.cpu.topology.threads = 1
    mock_vm.os.type = "ol_8"
    mock_vm.high_availability.enabled = False
    mock_vm.description = "Test VM"
    mock_vm.fqdn = "test-vm.local"

    mock_dev1 = MagicMock()
    mock_ip1 = MagicMock()
    mock_ip1.address = "10.0.0.55"
    mock_dev1.ips = [mock_ip1]

    mock_dev2 = MagicMock()
    mock_ip2 = MagicMock()
    mock_ip2.address = "fe80::1"
    mock_dev2.ips = [mock_ip2]

    mock_vm.reported_devices = [mock_dev1, mock_dev2]
    mock_vm.guest_reported_devices = None

    summary = extract_vm_summary(mock_vm)
    assert summary.ip_addresses == ["10.0.0.55", "fe80::1"]
