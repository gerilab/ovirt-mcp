"""Unit tests for Cloud-Init and Sysprep guest initialization in oVirt MCP."""

from unittest.mock import MagicMock, patch

import ovirtsdk4.types as sdk_types

from ovirt_mcp.tools.vms import (
    build_initialization_spec,
    create_vm_tool,
    extract_vm_initialization,
    get_vm_initialization_tool,
    set_vm_initialization_tool,
    start_vm_tool,
)


def test_build_initialization_spec_none() -> None:
    """Empty inputs should return None."""
    assert build_initialization_spec() is None


def test_build_initialization_spec_cloud_init() -> None:
    """Build Cloud-Init specification with hostname, user, script, and SSH keys."""
    spec = build_initialization_spec(
        cloud_init_hostname="web01.example.com",
        cloud_init_user="cloud-admin",
        cloud_init_password="SecretPassword123!",
        cloud_init_ssh_keys="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKey user@example.com",
        cloud_init_script="#cloud-config\npackage_upgrade: true\n",
        cloud_init_dns_servers="192.0.2.1 198.51.100.1",
        cloud_init_dns_search="example.com",
        cloud_init_regenerate_ssh_keys=True,
        cloud_init_timezone="UTC",
    )
    assert spec is not None
    assert spec.host_name == "web01.example.com"
    assert spec.user_name == "cloud-admin"
    assert spec.root_password == "SecretPassword123!"
    assert (
        spec.authorized_ssh_keys
        == "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKey user@example.com"
    )
    assert spec.custom_script == "#cloud-config\npackage_upgrade: true\n"
    assert spec.dns_servers == "192.0.2.1 198.51.100.1"
    assert spec.dns_search == "example.com"
    assert spec.regenerate_ssh_keys is True
    assert spec.timezone == "UTC"


def test_build_initialization_spec_sysprep() -> None:
    """Build Windows Sysprep specification with domain, org, license, and locales."""
    spec = build_initialization_spec(
        cloud_init_hostname="win-srv01",
        sysprep_domain="corp.example.com",
        sysprep_active_directory_ou="OU=Servers,DC=corp,DC=example,DC=com",
        sysprep_admin_password="AdminSecurePassword123!",
        sysprep_user_name="Administrator",
        sysprep_license_key="AAAAA-BBBBB-CCCCC-DDDDD-EEEEE",
        sysprep_org_name="Example Corporation",
        sysprep_input_locale="en-US",
        sysprep_system_locale="en-US",
        sysprep_ui_language="en-US",
        sysprep_user_locale="en-US",
        sysprep_custom_script="[Unattend]\nUnattendMode=FullUnattended\n",
        sysprep_timezone="Eastern Standard Time",
    )
    assert spec is not None
    assert spec.host_name == "win-srv01"
    assert spec.domain == "corp.example.com"
    assert spec.active_directory_ou == "OU=Servers,DC=corp,DC=example,DC=com"
    assert spec.root_password == "AdminSecurePassword123!"
    assert spec.user_name == "Administrator"
    assert spec.windows_license_key == "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"
    assert spec.org_name == "Example Corporation"
    assert spec.input_locale == "en-US"
    assert spec.system_locale == "en-US"
    assert spec.ui_language == "en-US"
    assert spec.user_locale == "en-US"
    assert spec.custom_script == "[Unattend]\nUnattendMode=FullUnattended\n"
    assert spec.timezone == "Eastern Standard Time"


def test_build_initialization_spec_static_nic() -> None:
    """Build network configuration with static IP and gateway."""
    spec = build_initialization_spec(
        cloud_init_hostname="static-host.example.com",
        nic_name="eth0",
        nic_ip_address="192.0.2.50",
        nic_netmask="255.255.255.0",
        nic_gateway="192.0.2.1",
    )
    assert spec is not None
    assert spec.nic_configurations is not None
    assert len(spec.nic_configurations) == 1
    nic = spec.nic_configurations[0]
    assert nic.name == "eth0"
    assert nic.boot_protocol == sdk_types.BootProtocol.STATIC
    assert nic.ip.address == "192.0.2.50"
    assert nic.ip.netmask == "255.255.255.0"
    assert nic.ip.gateway == "192.0.2.1"


def test_extract_vm_initialization_none() -> None:
    """Return None when VM has no initialization."""
    vm = MagicMock()
    vm.initialization = None
    assert extract_vm_initialization(vm) is None


def test_extract_vm_initialization_cloud_init() -> None:
    """Extract Cloud-Init initialization from an SDK VM object."""
    vm = MagicMock()
    init = sdk_types.Initialization(
        host_name="linux-vm.example.com",
        user_name="ci-user",
        custom_script="#cloud-config\ntimezone: UTC\n",
        authorized_ssh_keys="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKey",
        regenerate_ssh_keys=True,
        timezone="UTC",
        dns_servers="192.0.2.1",
        dns_search="example.com",
    )
    vm.initialization = init

    info = extract_vm_initialization(vm)
    assert info is not None
    assert info.type == "cloud_init"
    assert info.host_name == "linux-vm.example.com"
    assert info.user_name == "ci-user"
    assert info.custom_script == "#cloud-config\ntimezone: UTC\n"
    assert info.authorized_ssh_keys == "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKey"
    assert info.regenerate_ssh_keys is True
    assert info.timezone == "UTC"
    assert info.dns_servers == "192.0.2.1"


def test_extract_vm_initialization_sysprep() -> None:
    """Extract Windows Sysprep initialization from an SDK VM object."""
    vm = MagicMock()
    init = sdk_types.Initialization(
        domain="corp.example.com",
        windows_license_key="XXXXX-YYYYY-ZZZZZ-11111-22222",
        org_name="Example Org",
        host_name="win-vm01",
        user_name="Administrator",
        custom_script="[Unattend]\nUnattendMode=FullUnattended\n",
        regenerate_ssh_keys=False,
        timezone="UTC",
        active_directory_ou="OU=Computers,DC=corp,DC=example,DC=com",
        input_locale="en-US",
        system_locale="en-US",
        ui_language="en-US",
        user_locale="en-US",
    )
    vm.initialization = init

    info = extract_vm_initialization(vm)
    assert info is not None
    assert info.type == "sysprep"
    assert info.domain == "corp.example.com"
    assert info.windows_license_key == "XXXXX-YYYYY-ZZZZZ-11111-22222"
    assert info.org_name == "Example Org"
    assert info.host_name == "win-vm01"
    assert info.active_directory_ou == "OU=Computers,DC=corp,DC=example,DC=com"


@patch("ovirt_mcp.tools.vms.get_client")
def test_create_vm_tool_with_cloud_init(mock_get_client: MagicMock) -> None:
    """Verify create_vm_tool passes initialization specification to SDK."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys_svc = MagicMock()
    mock_vms_svc = MagicMock()

    mock_get_client.return_value = mock_client
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys_svc
    mock_sys_svc.vms_service.return_value = mock_vms_svc

    # Cluster resolution
    mock_cluster = MagicMock()
    mock_cluster.id = "cluster-uuid-1"
    mock_cluster.name = "Test-Cluster"
    # Template resolution
    mock_template = MagicMock()
    mock_template.id = "template-uuid-1"
    mock_template.name = "Test-Template"
    mock_client.find_resource_by_id_or_name.side_effect = [mock_cluster, mock_template]

    # VM creation mock
    created_vm = MagicMock()
    created_vm.id = "new-vm-uuid-1"
    created_vm.name = "new-ci-vm"
    created_vm.status = MagicMock(value="down")
    mock_vms_svc.add.return_value = created_vm

    res = create_vm_tool(
        name="new-ci-vm",
        cluster="Test-Cluster",
        template="Test-Template",
        cloud_init_hostname="ci-vm.example.com",
        cloud_init_user="cloud-user",
        cloud_init_script="#cloud-config\nwrite_files:\n  - path: /tmp/test\n",
    )

    assert res.success is True
    assert res.vm_id == "new-vm-uuid-1"
    mock_vms_svc.add.assert_called_once()
    added_vm_spec = mock_vms_svc.add.call_args[0][0]
    assert added_vm_spec.initialization is not None
    assert added_vm_spec.initialization.host_name == "ci-vm.example.com"
    assert added_vm_spec.initialization.user_name == "cloud-user"
    assert (
        added_vm_spec.initialization.custom_script
        == "#cloud-config\nwrite_files:\n  - path: /tmp/test\n"
    )


@patch("ovirt_mcp.tools.vms.get_client")
def test_create_vm_tool_with_sysprep(mock_get_client: MagicMock) -> None:
    """Verify create_vm_tool passes sysprep initialization specification to SDK."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys_svc = MagicMock()
    mock_vms_svc = MagicMock()

    mock_get_client.return_value = mock_client
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys_svc
    mock_sys_svc.vms_service.return_value = mock_vms_svc

    mock_cluster = MagicMock(id="c-1", name="Cluster1")
    mock_template = MagicMock(id="t-1", name="WinTemplate")
    mock_client.find_resource_by_id_or_name.side_effect = [mock_cluster, mock_template]

    created_vm = MagicMock(id="win-vm-1", name="win-vm", status=MagicMock(value="down"))
    mock_vms_svc.add.return_value = created_vm

    res = create_vm_tool(
        name="win-vm",
        cluster="Cluster1",
        template="WinTemplate",
        sysprep_domain="corp.example.com",
        sysprep_admin_password="AdminPassword123!",
        sysprep_license_key="AAAAA-BBBBB-CCCCC-DDDDD-EEEEE",
        sysprep_org_name="ExampleCorp",
    )

    assert res.success is True
    added_vm_spec = mock_vms_svc.add.call_args[0][0]
    assert added_vm_spec.initialization is not None
    assert added_vm_spec.initialization.domain == "corp.example.com"
    assert added_vm_spec.initialization.root_password == "AdminPassword123!"
    assert added_vm_spec.initialization.windows_license_key == "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"
    assert added_vm_spec.initialization.org_name == "ExampleCorp"


@patch("ovirt_mcp.tools.vms.get_client")
def test_set_vm_initialization_tool(mock_get_client: MagicMock) -> None:
    """Test updating existing VM with Cloud-Init initialization."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys_svc = MagicMock()
    mock_vms_svc = MagicMock()
    mock_vm_svc = MagicMock()

    mock_get_client.return_value = mock_client
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys_svc
    mock_sys_svc.vms_service.return_value = mock_vms_svc
    mock_vms_svc.vm_service.return_value = mock_vm_svc

    mock_vm = MagicMock(id="vm-uuid-99", name="target-vm")
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    res = set_vm_initialization_tool(
        name_or_id="target-vm",
        cloud_init_hostname="target.example.com",
        cloud_init_user="admin",
        cloud_init_password="Password123!",
        cloud_init_timezone="UTC",
    )

    assert res.success is True
    assert res.action == "set"
    assert res.initialization_type == "cloud_init"
    assert res.host_name == "target.example.com"
    mock_vm_svc.update.assert_called_once()
    update_arg = mock_vm_svc.update.call_args[0][0]
    assert update_arg.initialization.host_name == "target.example.com"
    assert update_arg.initialization.user_name == "admin"


@patch("ovirt_mcp.tools.vms.get_client")
def test_set_vm_initialization_tool_clear(mock_get_client: MagicMock) -> None:
    """Test clearing VM initialization."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys_svc = MagicMock()
    mock_vms_svc = MagicMock()
    mock_vm_svc = MagicMock()

    mock_get_client.return_value = mock_client
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys_svc
    mock_sys_svc.vms_service.return_value = mock_vms_svc
    mock_vms_svc.vm_service.return_value = mock_vm_svc

    mock_vm = MagicMock(id="vm-uuid-99", name="target-vm")
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    res = set_vm_initialization_tool(
        name_or_id="target-vm",
        clear=True,
        confirm=True,
    )

    assert res.success is True
    assert res.action == "clear"
    mock_vm_svc.update.assert_called_once()
    update_arg = mock_vm_svc.update.call_args[0][0]
    assert update_arg.initialization is not None


@patch("ovirt_mcp.tools.vms.get_client")
def test_set_vm_initialization_tool_dry_run(mock_get_client: MagicMock) -> None:
    """Dry run should not call vm_service.update."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys_svc = MagicMock()
    mock_vms_svc = MagicMock()
    mock_vm_svc = MagicMock()

    mock_get_client.return_value = mock_client
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys_svc
    mock_sys_svc.vms_service.return_value = mock_vms_svc
    mock_vms_svc.vm_service.return_value = mock_vm_svc

    mock_vm = MagicMock(id="vm-uuid-99", name="target-vm")
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    res = set_vm_initialization_tool(
        name_or_id="target-vm",
        cloud_init_hostname="preview.example.com",
        dry_run=True,
    )

    assert res.success is True
    assert res.dry_run is True
    mock_vm_svc.update.assert_not_called()


@patch("ovirt_mcp.tools.vms.get_client")
def test_get_vm_initialization_tool(mock_get_client: MagicMock) -> None:
    """Test retrieving VM initialization."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys_svc = MagicMock()
    mock_vms_svc = MagicMock()

    mock_get_client.return_value = mock_client
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys_svc
    mock_sys_svc.vms_service.return_value = mock_vms_svc

    mock_vm = MagicMock(id="vm-1", name="vm1")
    init = sdk_types.Initialization(
        host_name="test.example.com",
        user_name="testuser",
    )
    mock_vm.initialization = init
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    info = get_vm_initialization_tool("vm1")
    assert info.host_name == "test.example.com"
    assert info.user_name == "testuser"


@patch("ovirt_mcp.tools.vms.get_client")
def test_start_vm_tool_with_run_once_cloud_init(mock_get_client: MagicMock) -> None:
    """Test starting VM with use_cloud_init=True and custom script override."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys_svc = MagicMock()
    mock_vms_svc = MagicMock()
    mock_vm_svc = MagicMock()

    mock_get_client.return_value = mock_client
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys_svc
    mock_sys_svc.vms_service.return_value = mock_vms_svc
    mock_vms_svc.vm_service.return_value = mock_vm_svc

    mock_vm = MagicMock(id="vm-1", name="vm1", status=MagicMock(value="down"))
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    res = start_vm_tool(
        name_or_id="vm1",
        use_cloud_init=True,
        cloud_init_script="#cloud-config\nruncmd: ['touch /tmp/started']\n",
    )

    assert res.success is True
    mock_vm_svc.start.assert_called_once()
    call_kwargs = mock_vm_svc.start.call_args[1]
    assert call_kwargs.get("use_cloud_init") is True
    assert "vm" in call_kwargs
    assert (
        call_kwargs["vm"].initialization.custom_script
        == "#cloud-config\nruncmd: ['touch /tmp/started']\n"
    )


@patch("ovirt_mcp.tools.vms.get_client")
def test_start_vm_tool_with_run_once_sysprep(mock_get_client: MagicMock) -> None:
    """Test starting VM with use_sysprep=True and password override."""
    mock_client = MagicMock()
    mock_conn = MagicMock()
    mock_sys_svc = MagicMock()
    mock_vms_svc = MagicMock()
    mock_vm_svc = MagicMock()

    mock_get_client.return_value = mock_client
    mock_client.get_connection.return_value = mock_conn
    mock_conn.system_service.return_value = mock_sys_svc
    mock_sys_svc.vms_service.return_value = mock_vms_svc
    mock_vms_svc.vm_service.return_value = mock_vm_svc

    mock_vm = MagicMock(id="vm-1", name="win-vm1", status=MagicMock(value="down"))
    mock_client.find_resource_by_id_or_name.return_value = mock_vm

    res = start_vm_tool(
        name_or_id="win-vm1",
        use_sysprep=True,
        sysprep_admin_password="NewAdminPassword123!",
    )

    assert res.success is True
    mock_vm_svc.start.assert_called_once()
    call_kwargs = mock_vm_svc.start.call_args[1]
    assert call_kwargs.get("use_sysprep") is True
    assert "vm" in call_kwargs
    assert call_kwargs["vm"].initialization.root_password == "NewAdminPassword123!"
