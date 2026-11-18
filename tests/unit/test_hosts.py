"""Unit tests for Hypervisor Host management tools."""

from unittest.mock import MagicMock, patch

import pytest

from ovirt_mcp.client.exceptions import (
    OvirtPermissionError,
    OvirtValidationError,
)
from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.models.host import (
    HostDetail,
    HostDeviceInfo,
    HostEvent,
    HostLifecycleResult,
    HostNicInfo,
    HostNumaNodeInfo,
    HostStats,
    HostSummary,
    HostUpgradeCheckResult,
    HostUpgradeResult,
)
from ovirt_mcp.tools.hosts import (
    activate_host_tool,
    get_host_stats_tool,
    get_host_tool,
    list_host_devices_tool,
    list_host_events_tool,
    list_host_nics_tool,
    list_host_numa_tool,
    list_host_storage_tool,
    list_hosts_tool,
    maintenance_host_tool,
    restart_host_tool,
    upgrade_check_host_tool,
    upgrade_host_tool,
)


def _setup_mock_host(
    host_id: str = "host-uuid-1",
    host_name: str = "olvmhost002.example.com",
    status_str: str = "up",
    power_mgmt_enabled: bool = False,
    is_vmware: bool = True,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_system = MagicMock()
    mock_hosts_service = MagicMock()
    mock_host_service = MagicMock()
    mock_vms_service = MagicMock()

    mock_host = MagicMock()
    mock_host.id = host_id
    mock_host.name = host_name
    mock_status = MagicMock()
    mock_status.value = status_str
    mock_host.status = mock_status

    mock_cluster = MagicMock()
    mock_cluster.name = "DefaultCluster"
    mock_cluster.id = "cluster-uuid-1"
    mock_host.cluster = mock_cluster
    mock_host.address = "192.0.2.12"
    mock_host.update_available = True

    hw_info = MagicMock()
    hw_info.manufacturer = "VMware, Inc." if is_vmware else "Dell Inc."
    hw_info.product_name = "VMware20,1" if is_vmware else "PowerEdge R740"
    hw_info.version = "None"
    hw_info.serial_number = "VMware-56 4d"
    hw_info.uuid = "uuid-hw"
    mock_host.hardware_information = hw_info

    pm = MagicMock()
    pm.enabled = power_mgmt_enabled
    pm.type.value = "ipmilan"
    pm.address = "192.0.2.112"
    pm.username = "root"
    pm.automatic_pm_enabled = False
    mock_host.power_management = pm

    spm = MagicMock()
    spm.status.value = "none"
    mock_host.spm = spm

    cpu = MagicMock()
    cpu.name = "AMD Ryzen 5 3600 6-Core Processor"
    cpu.topology.cores = 6
    cpu.topology.sockets = 1
    cpu.topology.threads = 2
    mock_host.cpu = cpu

    mock_host.memory = 34359738368  # 32 GB
    mock_host.max_scheduling_memory = 32212254720

    mock_hosts_service.host_service.return_value = mock_host_service
    mock_hosts_service.list.return_value = [mock_host]
    mock_vms_service.list.return_value = []

    mock_system.hosts_service.return_value = mock_hosts_service
    mock_system.vms_service.return_value = mock_vms_service
    mock_conn.system_service.return_value = mock_system
    mock_client.get_connection.return_value = mock_conn
    mock_client.find_resource_by_id_or_name.return_value = mock_host

    return mock_client, mock_host_service, mock_host


# ── LIST & GET HOSTS TESTS ─────────────────────────────────────────────────────


def test_list_hosts_success() -> None:
    mock_client, _, _ = _setup_mock_host()

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        hosts = list_hosts_tool()

    assert len(hosts) == 1
    h = hosts[0]
    assert isinstance(h, HostSummary)
    assert h.name == "olvmhost002.example.com"
    assert h.status == "up"
    assert h.is_nested is True
    assert h.total_memory_gb == 32.0
    assert h.active_vms_count == 0
    assert h.update_available is True


def test_get_host_detail_success() -> None:
    mock_client, mock_host_service, _ = _setup_mock_host()
    mock_host_service.nics_service().list.return_value = [MagicMock(), MagicMock()]
    mock_host_service.numa_nodes_service().list.return_value = [MagicMock()]

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        detail = get_host_tool("olvmhost002.example.com")

    assert isinstance(detail, HostDetail)
    assert detail.name == "olvmhost002.example.com"
    assert detail.is_nested is True
    assert detail.nics_count == 2
    assert detail.numa_nodes_count == 1
    assert detail.hardware.manufacturer == "VMware, Inc."
    assert detail.power_management.enabled is False
    assert detail.update_available is True


# ── HOST STATS TESTS ──────────────────────────────────────────────────────────


def test_get_host_stats_success() -> None:
    mock_client, mock_host_service, _ = _setup_mock_host()

    def make_stat(name: str, val: float) -> MagicMock:
        s = MagicMock()
        s.name = name
        v = MagicMock()
        v.datum = val
        s.values = [v]
        return s

    mock_host_service.statistics_service().list.return_value = [
        make_stat("cpu.current.user", 5.0),
        make_stat("cpu.current.system", 3.0),
        make_stat("cpu.current.idle", 92.0),
        make_stat("cpu.load.avg.5m", 0.45),
        make_stat("memory.total", 34359738368.0),
        make_stat("memory.used", 8589934592.0),
        make_stat("memory.free", 25769803776.0),
        make_stat("swap.total", 0.0),
        make_stat("swap.used", 0.0),
        make_stat("boot.time", 1700000000.0),
    ]

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        stats = get_host_stats_tool("olvmhost002.example.com")

    assert isinstance(stats, HostStats)
    assert stats.cpu_usage_percent == 8.0  # 100 - 92
    assert stats.cpu_user_percent == 5.0
    assert stats.cpu_system_percent == 3.0
    assert stats.memory_total_gb == 32.0
    assert stats.memory_used_gb == 8.0
    assert stats.memory_used_percent == 25.0
    assert stats.boot_time is not None


# ── HOST MAINTENANCE TESTS ────────────────────────────────────────────────────


def test_maintenance_host_safe_mode_unconfirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        maintenance_host_tool("olvmhost002.example.com", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_maintenance_host_already_in_maintenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, _ = _setup_mock_host(status_str="maintenance")

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = maintenance_host_tool("olvmhost002.example.com", confirm=True)

    assert isinstance(res, HostLifecycleResult)
    assert res.success is True
    assert "already in maintenance" in res.message


def test_maintenance_host_pinned_vms_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, _ = _setup_mock_host(status_str="up")

    # Simulate a pinned VM on this host
    mock_vm = MagicMock()
    mock_vm.name = "pinned-db-vm"
    mock_host_ref = MagicMock()
    mock_host_ref.id = "host-uuid-1"
    mock_vm.placement_policy.hosts = [mock_host_ref]
    mock_vm.placement_policy.affinity.value = "pinned"

    mock_client.get_connection().system_service().vms_service().list.return_value = [mock_vm]

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            maintenance_host_tool("olvmhost002.example.com", stop_pinned_vms=False, confirm=True)
        assert "pinned to this host" in str(exc_info.value)
        assert "pinned-db-vm" in str(exc_info.value)


def test_maintenance_host_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_host_service, _ = _setup_mock_host(status_str="up")

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = maintenance_host_tool("olvmhost002.example.com", confirm=True, wait=False)

    mock_host_service.deactivate.assert_called_once()
    assert res.success is True
    assert res.action == "maintenance"


# ── HOST ACTIVATE TESTS ───────────────────────────────────────────────────────


def test_activate_host_already_up() -> None:
    mock_client, _, _ = _setup_mock_host(status_str="up")

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = activate_host_tool("olvmhost002.example.com")

    assert res.success is True
    assert res.action == "activate"
    assert "already active" in res.message


def test_activate_host_success() -> None:
    mock_client, mock_host_service, _ = _setup_mock_host(status_str="maintenance")

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = activate_host_tool("olvmhost002.example.com", wait=False)

    mock_host_service.activate.assert_called_once()
    assert res.success is True
    assert res.action == "activate"


# ── HOST RESTART & ENTERPRISE PRE-CONDITION GUARDS TESTS ──────────────────────


def test_restart_host_safe_mode_unconfirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        restart_host_tool("olvmhost002.example.com", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_restart_host_read_only_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=True, mcp_safe_mode=False),
    )
    with pytest.raises(OvirtPermissionError) as exc_info:
        restart_host_tool("olvmhost002.example.com", confirm=True)
    assert "read-only mode" in str(exc_info.value)


def test_restart_host_blocked_when_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enterprise Guard: Host MUST NOT be rebooted while active ('up')."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, _ = _setup_mock_host(status_str="up")

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            restart_host_tool("olvmhost002.example.com", confirm=True)
        assert "currently active ('up')" in str(exc_info.value)
        assert "ovirt_host_maintenance" in str(exc_info.value)


def test_restart_host_blocked_when_preparing_for_maintenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enterprise Guard: Host MUST NOT be rebooted while VMs are actively migrating."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, _ = _setup_mock_host(status_str="preparing_for_maintenance")

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            restart_host_tool("olvmhost002.example.com", confirm=True)
        assert "preparing_for_maintenance" in str(exc_info.value)
        assert "migrations are actively in progress" in str(exc_info.value)


def test_restart_host_blocked_when_vms_running(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enterprise Guard: Host in maintenance MUST NOT be rebooted if active VMs > 0."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, _, _ = _setup_mock_host(status_str="maintenance")

    # Simulate an active VM still running
    mock_running_vm = MagicMock()
    mock_running_vm.name = "stubborn-vm"
    mock_client.get_connection().system_service().vms_service().list.return_value = [
        mock_running_vm
    ]

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            restart_host_tool("olvmhost002.example.com", confirm=True)
        assert "still running on this host" in str(exc_info.value)
        assert "stubborn-vm" in str(exc_info.value)


def test_restart_host_blocked_when_power_management_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enterprise Guard: Diagnostics error if power management / IPMI is disabled."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    # Host is in maintenance, 0 VMs, BUT power management is disabled (nested VMware)
    mock_client, _, _ = _setup_mock_host(
        status_str="maintenance", power_mgmt_enabled=False, is_vmware=True
    )

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        with pytest.raises(OvirtValidationError) as exc_info:
            restart_host_tool("olvmhost002.example.com", confirm=True)
        assert "Power management (fencing / IPMI) is not enabled" in str(exc_info.value)
        assert "nested virtualized: True" in str(exc_info.value)


def test_restart_host_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """When in maintenance, 0 VMs, and power management enabled, restart succeeds."""
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_host_service, _ = _setup_mock_host(
        status_str="maintenance", power_mgmt_enabled=True, is_vmware=False
    )

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = restart_host_tool("olvmhost002.example.com", confirm=True, wait=False)

    mock_host_service.fence.assert_called_once()
    assert res.success is True
    assert res.action == "restart"


# ── HOST UPGRADE TESTS ────────────────────────────────────────────────────────


def test_upgrade_check_host_success() -> None:
    mock_client, mock_host_service, _ = _setup_mock_host(status_str="up")

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = upgrade_check_host_tool("olvmhost002.example.com")

    mock_host_service.upgrade_check.assert_called_once()
    assert isinstance(res, HostUpgradeCheckResult)
    assert res.success is True
    assert res.host_name == "olvmhost002.example.com"
    assert res.update_available is True
    assert "updates are available" in res.message


def test_upgrade_check_host_invalid_status_rejected() -> None:
    mock_client, _, _ = _setup_mock_host(status_str="installing")

    with (
        patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError) as exc_info,
    ):
        upgrade_check_host_tool("olvmhost002.example.com")

    assert "Valid host statuses for upgrade check are 'up' or 'non_operational'" in str(
        exc_info.value
    )


def test_upgrade_host_safe_mode_unconfirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    with pytest.raises(OvirtValidationError) as exc_info:
        upgrade_host_tool("olvmhost002.example.com", confirm=False)
    assert "confirm=True" in str(exc_info.value)


def test_upgrade_host_not_in_maintenance_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=False),
    )
    mock_client, _, _ = _setup_mock_host(status_str="up")

    with (
        patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client),
        pytest.raises(OvirtValidationError) as exc_info,
    ):
        upgrade_host_tool("olvmhost002.example.com", confirm=True)

    assert "requires the hypervisor host to be in 'maintenance' mode" in str(exc_info.value)


def test_upgrade_host_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ovirt_mcp.tools.guards.get_config",
        lambda: OvirtConfig(mcp_read_only=False, mcp_safe_mode=True),
    )
    mock_client, mock_host_service, _ = _setup_mock_host(status_str="maintenance")

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        res = upgrade_host_tool("olvmhost002.example.com", reboot=True, confirm=True, async_=True)

    mock_host_service.upgrade.assert_called_once_with(
        reboot=True,
        async_=True,
        timeout=60,
    )
    assert isinstance(res, HostUpgradeResult)
    assert res.success is True
    assert res.action == "upgrade"
    assert res.reboot_requested is True
    assert "upgrade initiated successfully" in res.message


# ── NICS, NUMA, DEVICES, EVENTS TESTS ─────────────────────────────────────────


def test_list_host_nics_success() -> None:
    mock_client, mock_host_service, _ = _setup_mock_host()

    mock_nic = MagicMock()
    mock_nic.id = "nic-1"
    mock_nic.name = "eth0"
    mock_nic.mac.address = "00:50:56:91:69:08"
    mock_nic.speed = 10000000000  # 10 Gbps
    mock_nic.status.value = "up"
    mock_nic.network = None
    mock_nic.bridged = False
    mock_nic.ip.address = "192.0.2.12"
    mock_nic.ips = []
    mock_nic.bonding = None

    mock_host_service.nics_service().list.return_value = [mock_nic]

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        nics = list_host_nics_tool("olvmhost002.example.com")

    assert len(nics) == 1
    n = nics[0]
    assert isinstance(n, HostNicInfo)
    assert n.name == "eth0"
    assert n.speed_mbps == 10000
    assert n.mac_address == "00:50:56:91:69:08"
    assert "192.0.2.12" in n.ip_addresses


def test_list_host_numa_success() -> None:
    mock_client, mock_host_service, _ = _setup_mock_host()

    mock_node = MagicMock()
    mock_node.index = 0
    mock_node.memory = 21205
    c0 = MagicMock()
    c0.index = 0
    c1 = MagicMock()
    c1.index = 1
    mock_node.cpu.cores = [c0, c1]

    mock_host_service.numa_nodes_service().list.return_value = [mock_node]

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        nodes = list_host_numa_tool("olvmhost002.example.com")

    assert len(nodes) == 1
    assert isinstance(nodes[0], HostNumaNodeInfo)
    assert nodes[0].index == 0
    assert nodes[0].memory_mb == 21205
    assert nodes[0].cpu_cores == [0, 1]


def test_list_host_devices_success() -> None:
    mock_client, mock_host_service, _ = _setup_mock_host()

    mock_dev = MagicMock()
    mock_dev.id = "pci_0000_00_16_3"
    mock_dev.name = "pci_0000_00_16_3"
    mock_dev.product.name = "PCI Express Root Port"
    mock_dev.vendor.name = "VMware"
    mock_dev.driver = "pcieport"
    mock_dev.iommu_group = None

    mock_host_service.devices_service().list.return_value = [mock_dev]

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        devs = list_host_devices_tool("olvmhost002.example.com")

    assert len(devs) == 1
    assert isinstance(devs[0], HostDeviceInfo)
    assert devs[0].name == "pci_0000_00_16_3"
    assert devs[0].vendor == "VMware"


def test_list_host_storage_success() -> None:
    mock_client, mock_host_service, _ = _setup_mock_host()

    mock_storage = MagicMock()
    mock_storage.id = "storage-1"
    mock_storage.name = "Data"
    mock_storage.type.value = "nfs"
    mock_storage.address = "nas.example.com"
    mock_storage.target = None

    mock_host_service.storage_service().list.return_value = [mock_storage]

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        storage = list_host_storage_tool("olvmhost002.example.com")

    assert len(storage) == 1
    assert storage[0]["name"] == "Data"
    assert storage[0]["type"] == "nfs"


def test_list_host_events_success() -> None:
    mock_client, _, _ = _setup_mock_host()

    mock_event = MagicMock()
    mock_event.id = "event-101"
    mock_event.code = 12
    mock_event.severity.value = "normal"
    mock_event.description = "Status of host olvmhost002.example.com was set to Up."
    mock_event.time = "2026-11-18 13:34:27.850000+01:00"

    mock_client.get_connection().system_service().events_service().list.return_value = [mock_event]

    with patch("ovirt_mcp.tools.hosts.get_client", return_value=mock_client):
        events = list_host_events_tool("olvmhost002.example.com", max_events=10)

    assert len(events) == 1
    assert isinstance(events[0], HostEvent)
    assert events[0].id == "event-101"
    assert events[0].severity == "normal"
    assert "was set to Up" in events[0].description
