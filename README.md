# ovirt-mcp: Enterprise Virtualization Manager for AI Agents

Modern, production-grade Model Context Protocol (MCP) server for **Oracle Linux Virtualization Manager (OLVM)** and **oVirt** hypervisor engines. 

`ovirt-mcp` connects LLMs (Claude, GPT, Llama, Mistral, Ollama) directly to your enterprise virtualization infrastructure with token-optimized responses, deep hardware inspection, audit trails, and multi-layered safety controls.

---

## Table of Contents

1. [Features](#features)
2. [Prerequisites & System Packages](#prerequisites--system-packages)
3. [Step-by-Step Installation Guide](#step-by-step-installation-guide)
4. [Configuration (`.env`) Reference](#configuration-env-reference)
   - [Authentication & AAA Profiles](#authentication--aaa-profiles-crucial)
   - [Service Account Best Practices](#service-account-best-practices)
   - [TLS & SSL Certificate Management](#tls--ssl-certificate-management)
5. [Operational Modes](#operational-modes)
   - [Compact vs. Detailed Mode (Token Optimization)](#compact-vs-detailed-mode-token-optimization)
   - [Safe Mode & Mutation Confirmation](#safe-mode--mutation-confirmation)
   - [Read-Only Enforcement](#read-only-enforcement)
   - [Hierarchical Naming Convention](#hierarchical-naming-convention)
6. [Tool Reference](#tool-reference)
   - [`ovirt_test_connection`](#1-ovirt_test_connection)
   - [`ovirt_vm_list`](#2-ovirt_vm_list)
   - [`ovirt_vm_get`](#3-ovirt_vm_get)
   - [`ovirt_vm_events`](#4-ovirt_vm_events)
   - [`ovirt_vm_start`](#5-ovirt_vm_start)
   - [`ovirt_vm_stop`](#6-ovirt_vm_stop)
   - [`ovirt_vm_shutdown`](#7-ovirt_vm_shutdown)
   - [`ovirt_vm_reboot`](#8-ovirt_vm_reboot)
   - [`ovirt_vm_create`](#9-ovirt_vm_create)
   - [`ovirt_vm_delete`](#10-ovirt_vm_delete)
   - [`ovirt_vm_migrate`](#11-ovirt_vm_migrate)
   - [`ovirt_vm_pin`](#12-ovirt_vm_pin)
   - [`ovirt_vm_unpin`](#13-ovirt_vm_unpin)
   - [`ovirt_vm_snapshot_list`](#14-ovirt_vm_snapshot_list)
   - [`ovirt_vm_snapshot_create`](#15-ovirt_vm_snapshot_create)
   - [`ovirt_vm_snapshot_restore`](#16-ovirt_vm_snapshot_restore)
   - [`ovirt_vm_snapshot_preview`](#17-ovirt_vm_snapshot_preview)
   - [`ovirt_vm_snapshot_commit`](#18-ovirt_vm_snapshot_commit)
   - [`ovirt_vm_snapshot_undo`](#19-ovirt_vm_snapshot_undo)
   - [`ovirt_vm_snapshot_delete`](#20-ovirt_vm_snapshot_delete)
   - [`ovirt_vm_cdrom_list`](#21-ovirt_vm_cdrom_list)
   - [`ovirt_vm_iso_attach`](#22-ovirt_vm_iso_attach)
   - [`ovirt_vm_iso_eject`](#23-ovirt_vm_iso_eject)
   - [`ovirt_storage_iso_list`](#24-ovirt_storage_iso_list)
   - [`ovirt_disk_list`](#25-ovirt_disk_list)
   - [`ovirt_disk_attach`](#26-ovirt_disk_attach)
   - [`ovirt_disk_detach`](#27-ovirt_disk_detach)
   - [`ovirt_disk_create`](#28-ovirt_disk_create)
   - [`ovirt_disk_resize`](#29-ovirt_disk_resize)
   - [`ovirt_vm_nic_list`](#30-ovirt_vm_nic_list)
   - [`ovirt_vm_nic_add`](#31-ovirt_vm_nic_add)
   - [`ovirt_vm_nic_remove`](#32-ovirt_vm_nic_remove)
   - [`ovirt_network_profile_list`](#33-ovirt_network_profile_list)
   - [`ovirt_vm_update`](#34-ovirt_vm_update)
   - [`ovirt_vm_graphics_consoles`](#35-ovirt_vm_graphics_consoles)
   - [`ovirt_vm_ticket`](#36-ovirt_vm_ticket)
   - [`ovirt_host_list`](#37-ovirt_host_list)
   - [`ovirt_host_get`](#38-ovirt_host_get)
   - [`ovirt_host_stats`](#39-ovirt_host_stats)
   - [`ovirt_host_maintenance`](#40-ovirt_host_maintenance)
   - [`ovirt_host_activate`](#41-ovirt_host_activate)
   - [`ovirt_host_restart`](#42-ovirt_host_restart)
   - [`ovirt_host_nic_list`](#43-ovirt_host_nic_list)
   - [`ovirt_host_numa_list`](#44-ovirt_host_numa_list)
   - [`ovirt_host_device_list`](#45-ovirt_host_device_list)
   - [`ovirt_host_storage_list`](#46-ovirt_host_storage_list)
   - [`ovirt_host_events`](#47-ovirt_host_events)
   - [`ovirt_affinity_label_list`](#48-ovirt_affinity_label_list)
   - [`ovirt_affinity_label_create`](#49-ovirt_affinity_label_create)
   - [`ovirt_affinity_label_delete`](#50-ovirt_affinity_label_delete)
   - [`ovirt_host_label_list`](#51-ovirt_host_label_list)
   - [`ovirt_host_label_assign`](#52-ovirt_host_label_assign)
   - [`ovirt_host_label_unassign`](#53-ovirt_host_label_unassign)
   - [`ovirt_vm_label_list`](#54-ovirt_vm_label_list)
   - [`ovirt_vm_label_assign`](#55-ovirt_vm_label_assign)
   - [`ovirt_vm_label_unassign`](#56-ovirt_vm_label_unassign)
   - [`ovirt_cluster_affinity_group_list`](#57-ovirt_cluster_affinity_group_list)
   - [`ovirt_cluster_affinity_group_get`](#58-ovirt_cluster_affinity_group_get)
   - [`ovirt_cluster_affinity_group_create`](#59-ovirt_cluster_affinity_group_create)
   - [`ovirt_cluster_affinity_group_update`](#60-ovirt_cluster_affinity_group_update)
   - [`ovirt_cluster_affinity_group_delete`](#61-ovirt_cluster_affinity_group_delete)
   - [`ovirt_host_network_attachment_list`](#62-ovirt_host_network_attachment_list)
   - [`ovirt_host_iscsi_discover`](#63-ovirt_host_iscsi_discover)
   - [`ovirt_host_iscsi_login`](#64-ovirt_host_iscsi_login)
   - [`ovirt_host_network_sync`](#65-ovirt_host_network_sync)
   - [`ovirt_storage_domain_list`](#66-ovirt_storage_domain_list)
   - [`ovirt_storage_domain_get`](#67-ovirt_storage_domain_get)
   - [`ovirt_storage_domain_create_nfs`](#68-ovirt_storage_domain_create_nfs)
   - [`ovirt_storage_domain_attach`](#69-ovirt_storage_domain_attach)
   - [`ovirt_storage_domain_activate`](#70-ovirt_storage_domain_activate)
   - [`ovirt_storage_domain_maintenance`](#71-ovirt_storage_domain_maintenance)
   - [`ovirt_storage_domain_detach`](#72-ovirt_storage_domain_detach)
   - [`ovirt_storage_domain_delete`](#73-ovirt_storage_domain_delete)
   - [`ovirt_disk_move`](#74-ovirt_disk_move)
   - [`ovirt_disk_copy`](#75-ovirt_disk_copy)
   - [`ovirt_disk_sparsify`](#76-ovirt_disk_sparsify)
   - [`ovirt_template_list`](#77-ovirt_template_list)
   - [`ovirt_template_get`](#78-ovirt_template_get)
   - [`ovirt_template_create_from_vm`](#79-ovirt_template_create_from_vm)
   - [`ovirt_template_delete`](#80-ovirt_template_delete)
   - [`ovirt_datacenter_list`](#81-ovirt_datacenter_list)
   - [`ovirt_datacenter_get`](#82-ovirt_datacenter_get)
   - [`ovirt_quota_list`](#83-ovirt_quota_list)
   - [`ovirt_quota_get`](#84-ovirt_quota_get)
   - [`ovirt_quota_create`](#85-ovirt_quota_create)
   - [`ovirt_quota_delete`](#86-ovirt_quota_delete)
   - [`ovirt_network_list`](#87-ovirt_network_list)
   - [`ovirt_network_create`](#88-ovirt_network_create)
   - [`ovirt_network_delete`](#89-ovirt_network_delete)
   - [`ovirt_tag_list`](#90-ovirt_tag_list)
   - [`ovirt_tag_create`](#91-ovirt_tag_create)
   - [`ovirt_tag_delete`](#92-ovirt_tag_delete)
   - [`ovirt_vm_tag_assign`](#93-ovirt_vm_tag_assign)
   - [`ovirt_vm_tag_unassign`](#94-ovirt_vm_tag_unassign)
   - [`ovirt_host_tag_assign`](#95-ovirt_host_tag_assign)
   - [`ovirt_host_tag_unassign`](#96-ovirt_host_tag_unassign)
   - [`ovirt_host_bond_create`](#97-ovirt_host_bond_create)
   - [`ovirt_host_bond_delete`](#98-ovirt_host_bond_delete)
   - [`ovirt_user_tag_list`](#99-ovirt_user_tag_list)
   - [`ovirt_user_tag_assign`](#100-ovirt_user_tag_assign)
   - [`ovirt_user_tag_unassign`](#101-ovirt_user_tag_unassign)
   - [`ovirt_host_upgrade_check`](#102-ovirt_host_upgrade_check)
   - [`ovirt_host_upgrade`](#103-ovirt_host_upgrade)
   - [`ovirt_system_events`](#104-ovirt_system_events)
   - [`ovirt_user_list`](#105-ovirt_user_list)
   - [`ovirt_user_get`](#106-ovirt_user_get)
   - [`ovirt_user_add`](#107-ovirt_user_add)
   - [`ovirt_user_delete`](#108-ovirt_user_delete)
   - [`ovirt_role_list`](#109-ovirt_role_list)
   - [`ovirt_permission_list`](#110-ovirt_permission_list)
   - [`ovirt_permission_add`](#111-ovirt_permission_add)
   - [`ovirt_permission_remove`](#112-ovirt_permission_remove)
7. [Connecting to AI MCP Clients](#connecting-to-ai-mcp-clients)
8. [Testing & Quality Verification](#testing--quality-verification)
9. [Troubleshooting & FAQ](#troubleshooting--faq)

---

## Features

- **Fast Inventory (`ovirt_vm_list`):** Query VMs across clusters with RAM, vCPU, IP addresses, cluster, host, and HA status in milliseconds.
- **Deep Hardware & Policy Inspection (`ovirt_vm_get`):** Access detailed CPU topology, memory ballooning ceilings, NUMA/IO threads, VirtIO-SCSI multi-queue, affinity groups, affinity labels, BIOS/TPM settings, thin-provisioned disk sizes (actual vs. provisioned), and vNIC bindings.
- **Dual Response Modes (Compact vs. Detailed):**
  - **Compact Mode:** ~90 tokens per VM (up to **86% token savings**), ideal for local and small context window models (Ollama, Mistral 7B, Llama 3 8B).
  - **Detailed Mode:** Comprehensive enterprise topology (~650 tokens per VM) for complex engineering tasks with frontier LLMs.
- **Audit Log Inspection (`ovirt_vm_events`):** Filter and analyze engine lifecycle events, warnings, failure reasons, and admin actions.
- **Multi-Layer Enterprise Security:**
  - `MCP_READ_ONLY=true`: Hard block against mutating actions.
  - `MCP_SAFE_MODE=true`: Requires explicit `confirm=True` for destructive actions.
  - Recommended least-privilege service account integration.
- **Automated TLS Management:** Automatic engine PKI CA download and certificate caching.

---

## Prerequisites & System Packages

`ovirt-mcp` is built on Python and the official `ovirt-engine-sdk-python` library, which requires native C headers for `libcurl` and `libxml2`.

### Supported Python Versions
- **Python 3.10, 3.11, or 3.12** (Python 3.12 recommended).

### Required OS Packages

Before creating your Python virtual environment, install the required development headers:

#### Debian / Ubuntu / Proxmox
```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev libcurl4-openssl-dev libxml2-dev gcc build-essential
```

#### Oracle Linux / RHEL / Rocky / AlmaLinux / CentOS Stream
```bash
sudo dnf install -y python3-devel libcurl-devel libxml2-devel gcc
```

---

## Step-by-Step Installation Guide

### Step 1: Clone the Repository

```bash
git clone https://github.com/gerilab/ovirt-mcp.git
cd ovirt-mcp
```

### Step 2: Create and Activate Virtual Environment

Always use an isolated virtual environment to prevent package version conflicts:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Verify that Python and pip are up to date:
```bash
pip install --upgrade pip
```

### Step 3: Install ovirt-mcp and Dependencies

#### For Standard Production Deployment:
```bash
pip install -e .
```

#### For Development and Testing (includes pytest, ruff, mypy):
```bash
pip install -e ".[dev]"
```

---

## Configuration (`.env`) Reference

Create your local `.env` configuration file from the template:

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` with your preferred editor:

```bash
# ── oVirt / OLVM Engine Connection ──────────────────────────────────────────
OVIRT_URL=https://olvm-engine.example.com/ovirt-engine/api
OVIRT_USERNAME=admin@internal
OVIRT_PASSWORD=YourSecurePasswordHere

# ── TLS / SSL Certificate Security ──────────────────────────────────────────
# Set to true for lab or test environments using self-signed certificates
OVIRT_INSECURE=false

# Path to CA certificate (leave blank to auto-download from the engine PKI endpoint)
OVIRT_CA_FILE=

# ── Connection Resiliency ───────────────────────────────────────────────────
OVIRT_TIMEOUT=30
OVIRT_MAX_RETRIES=3

# ── Logging & Security Policies ─────────────────────────────────────────────
MCP_LOG_LEVEL=INFO
MCP_SAFE_MODE=true
MCP_READ_ONLY=false

# ── Response Optimization (Token Economics) ──────────────────────────────────
# When true, ovirt_vm_get returns compact summaries by default (~86% fewer tokens)
MCP_COMPACT_MODE=false
```

### Configuration Options Breakdown

| Parameter | Type | Default | Description |
|---|---|---|---|
| `OVIRT_URL` | string | *required* | Full REST API URL to your engine (must end with `/ovirt-engine/api`). |
| `OVIRT_USERNAME` | string | *required* | Engine username including profile suffix (see AAA Profiles below). |
| `OVIRT_PASSWORD` | string | *required* | Engine account password. |
| `OVIRT_INSECURE` | bool | `false` | When `true`, disables SSL certificate validation (lab / self-signed only). |
| `OVIRT_CA_FILE` | path | `None` | Path to PEM CA certificate. If omitted, engine CA is downloaded automatically. |
| `OVIRT_TIMEOUT` | int | `30` | Network request timeout in seconds. |
| `OVIRT_MAX_RETRIES` | int | `3` | Connection retry count with exponential backoff. |
| `MCP_SAFE_MODE` | bool | `true` | When `true`, destructive actions (stop, reboot, delete) require `confirm=True`. |
| `MCP_READ_ONLY` | bool | `false` | When `true`, all state-modifying actions are strictly prohibited. |
| `MCP_COMPACT_MODE`| bool | `false` | Default format for `ovirt_vm_get`: `true` for small LLMs, `false` for deep analysis. |

---

### Authentication & AAA Profiles (Crucial)

oVirt and OLVM use an internal authentication provider that requires the profile name as part of the username.

- **Default Administrator Account:** In OLVM and oVirt 4.5+, the internal superuser account is typically:
  ```text
  admin@internal
  ```
  *(User: `admin@ovirt`, Profile: `internal`)*. Passing only `admin@ovirt` or `admin@internal` will produce `No valid profile found in credentials` or `Invalid user credentials`.
- **LDAP / Active Directory Accounts:** Formatted as `username@domain.com` matching the external domain name configured in the engine.

---

### Service Account Best Practices

> [!IMPORTANT]
> For production environments, **do not use full administrative superuser credentials**. Enterprise best practice is provisioning a dedicated, restricted service account for the AI Agent:
>
> 1. **Option A: Programmatically via MCP Tools:**
>    - Register the service user:
>      `ovirt_user_add(user_name="mcp-service", domain="internal-authz")`
>    - Grant least-privilege role (e.g. `PowerUserRole` or `ReadOnlyAdmin`):
>      `ovirt_permission_add(user_name_or_id="mcp-service@internal-authz", role_name_or_id="PowerUserRole", target_type="cluster", target_name_or_id="DefaultCluster")`
> 2. **Option B: Via Administration Web Portal:**
>    - In the oVirt/OLVM Administration Portal, navigate to **Administration** &rarr; **Configure** &rarr; **Roles**.
>    - For read-only monitoring: Assign `ReadOnlyAdmin` role to `mcp-service@internal-authz`.
>    - For VM operations (start/stop/reboot): Assign `UserVmManager` or `UserVmRunTimePermissions` scoped to the designated Cluster or Data Center.
> 3. Set `OVIRT_USERNAME=mcp-service@internal-authz` and its password in your `.env`.

---

### TLS & SSL Certificate Management

By default, `ovirt-mcp` automatically downloads the engine root CA certificate from:
```text
https://<engine-host>/ovirt-engine/services/pki-resource?resource=ca-certificate&format=X509-PEM-CA
```
The downloaded CA is safely cached in your local environment, ensuring secure TLS verification without manual certificate handling.
- For air-gapped systems: specify `OVIRT_CA_FILE=/path/to/ca.pem`.
- For quick local lab experiments: set `OVIRT_INSECURE=true`.

---

## Operational Modes

### Compact vs. Detailed Mode (Token Optimization)

Different LLMs have different context window sizes and token costs. `ovirt-mcp` provides dual output modes to optimize token consumption:

| Mode | Typical Size | Token Estimate | Intended Models / Use Cases |
|---|---|---|---|
| **Compact Mode** (`compact=True`) | ~360 bytes | **~90 tokens** | Ollama, Mistral 7B, Llama 3 8B, fast triage, inventory checks |
| **Detailed Mode** (`compact=False`) | ~2,600 bytes | **~650 tokens** | Claude 3.5 Sonnet, GPT-4o, hardware troubleshooting, capacity planning |

- **Server-wide default:** Set `MCP_COMPACT_MODE=true` in `.env` to make all `ovirt_vm_get` calls lightweight by default.
- **Per-query override:** The calling agent or user can pass `compact=True` or `compact=False` dynamically to any `ovirt_vm_get` call.

### Safe Mode & Mutation Confirmation

To prevent accidental hypervisor outages from hallucinatory or unintended agent actions:
1. When `MCP_SAFE_MODE=true` (the default), mutating operations require an explicit `confirm=True` parameter.
2. If `confirm=True` is not provided, the server returns an explicit confirmation request with safety details before taking action.

### Read-Only Enforcement

When `MCP_READ_ONLY=true` is set:
- Any action that attempts to modify engine state (stopping VMs, reboots, disk manipulation, etc.) is rejected immediately with `SecurityError: Operation blocked: Server is in READ-ONLY mode`.

### Hierarchical Naming Convention

To ensure clarity for both AI Agents and human operators, all tools adhere to a strict domain-namespaced naming convention:

```text
ovirt_<domain>_[<subresource>_]<action>
```

- **`ovirt_vm_*`**: All operations affecting virtual machines (lifecycle, snapshots, disks, media/ISO, migration, guest agent).
  - e.g. `ovirt_vm_list`, `ovirt_vm_start`, `ovirt_vm_stop`, `ovirt_vm_snapshot_create`, `ovirt_vm_disk_attach`, `ovirt_vm_migrate`.
- **`ovirt_host_*`**: Hypervisor host operations (`list`, `get`, `activate`, `maintenance`, `restart`, `stats`, `upgrade_check`, `upgrade`, `nic_list`, `numa_list`, `device_list`, `storage_list`, `events`).
- **`ovirt_cluster_*`**: Cluster topology, compatibility versions, and CPU profiles.
- **`ovirt_storage_*`**: Storage domains and capacity management.
- **`ovirt_disk_*`**: Standalone floating disks and volume operations.
- **`ovirt_network_*`**: Virtual networks and vNIC profiles.
- **`ovirt_user_*`**: User account registration, lookup, and deletion (`list`, `get`, `add`, `delete`).
- **`ovirt_role_*`**: Authorization roles and privilege inspection (`list`).
- **`ovirt_permission_*`**: Discrete permission grants and revocation across targets (`list`, `add`, `remove`).

---

## Tool Reference

### 1. `ovirt_test_connection`

Validates connectivity to the oVirt / OLVM engine, verifies API credentials, and reports platform version metadata.

- **Inputs:** None
- **Outputs (`SystemStatus`):**
  - `status`: Connection state (`connected`).
  - `product_name`: e.g. `"Oracle Linux Virtualization Manager"` or `"oVirt Engine"`.
  - `version`: Engine version string (e.g. `"4.5.5-1.66.el8"`).
  - `url`: Connected endpoint URL.
  - `username`: Connected user identity.

**Example Output:**
```json
{
  "status": "connected",
  "product_name": "Oracle Linux Virtualization Manager",
  "version": "4.5.5-1.66.el8",
  "url": "https://olvm-engine.example.com/ovirt-engine/api",
  "username": "admin@internal"
}
```

---

### 2. `ovirt_vm_list`

Lists virtual machines with fast status, cluster, host, vCPU, RAM, and reported network addresses.

- **Inputs:**
  - `search` *(string, optional)*: oVirt engine search filter (e.g., `"status=up"`, `"name=prod*"`, `"cluster=DefaultCluster"`).
- **Outputs:** `list[VmSummary]`
  - `id`: Unique UUID of the VM.
  - `name`: VM display name.
  - `status`: Execution state (`up`, `down`, `powering_up`, `paused`, etc.).
  - `cluster_name`: Host cluster name.
  - `host_name`: Current running hypervisor host name (or `None` if stopped).
  - `memory_mb`: Allocated RAM in megabytes.
  - `cpu_cores`: Total vCPU count.
  - `ip_addresses`: List of IPv4 and IPv6 addresses reported by the guest agent.
  - `fqdn`: Fully qualified domain name reported by guest agent.
  - `ha_enabled`: High-availability status boolean.

**Example Output:**
```json
[
  {
    "id": "571ae214-9b52-431e-bbc8-a09b601c1cd3",
    "name": "testvm001",
    "status": "down",
    "cluster_name": "DefaultCluster",
    "host_name": null,
    "memory_mb": 18432,
    "cpu_cores": 8,
    "ip_addresses": [],
    "fqdn": null,
    "ha_enabled": false
  }
]
```

---

### 3. `ovirt_vm_get`

Deep inspection of a single virtual machine by name or UUID. Supports both Compact and Detailed modes.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `compact` *(bool, optional)*: When `true`, returns `VmCompactDetail` (~90 tokens); when `false`, returns comprehensive `VmDetail` (~650 tokens). If omitted, uses the server's `MCP_COMPACT_MODE` setting.

#### Compact Mode Output (`VmCompactDetail`):
```json
{
  "id": "571ae214-9b52-431e-bbc8-a09b601c1cd3",
  "name": "testvm001",
  "status": "down",
  "cluster_name": "DefaultCluster",
  "host_name": null,
  "memory_mb": 18432,
  "cpu_cores": 8,
  "ip_addresses": [],
  "fqdn": null,
  "os_type": "rhel_8x64",
  "ha_enabled": false,
  "disks_summary": [
    "OracleEL8.10-data-disk (100.0 GB)",
    "OracleEL8.10-os-disk (40.0 GB)"
  ],
  "nics_count": 1,
  "snapshots_count": 1,
  "description": "Disaster Recovery Node"
}
```

#### Detailed Mode Output (`VmDetail`):
Provides full enterprise virtualization parameters:
- `cpu`: Sockets, cores per socket, threads per core, CPU pinning policy, auto pinning policy, CPU shares.
- `memory`: Allocated RAM, guaranteed RAM, maximum balloon ceiling, ballooning state.
- `io_scsi`: Dedicated I/O threads, VirtIO-SCSI controller state, multi-queue configuration.
- `affinity_and_placement`: Placement policy (`migratable`, `pinned`), assigned affinity groups, affinity labels, tags.
- `hardware`: BIOS type (`i440fx_sea_bios`, `q35_secure_boot`), machine type, display (`vnc`, `spice`), TPM device state, delete protection status.
- `disks`: List of disks with thin-provisioning metadata (provisioned GB vs. actual storage consumption GB), interface type (`virtio`, `virtio_scsi`), disk format (`cow`, `raw`), bootable flag, storage domain name.
- `nics`: List of virtual network interfaces with interface type, MAC address, network profile, link state, and plugged state.
- `snapshots_count`: Number of active snapshots.
- `lifecycle`: Creation timestamp, last start/stop timestamp, stop reason, migration downtime.

---

### 4. `ovirt_vm_events`

Retrieves and filters recent audit log events for a specific virtual machine.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `max_events` *(int, optional, default: 20)*: Maximum number of events to return.
  - `min_severity` *(string, optional, default: "normal")*: Minimum severity filter (`"normal"`, `"warning"`, `"error"`, `"alert"`).
- **Outputs:** `list[VmEvent]`
  - `id`: Event entry ID.
  - `code`: Engine event numerical code.
  - `description`: Event message text (includes initiating user, host, and error messages).
  - `severity`: `"normal"`, `"warning"`, `"error"`, or `"alert"`.
  - `time`: Timestamp with timezone.

**Example Output:**
```json
[
  {
    "id": "184912",
    "code": 61,
    "description": "VM testvm001 is down. Exit message: Admin shut down from the engine",
    "severity": "normal",
    "time": "2026-08-31 23:55:36.883000+02:00"
  },
  {
    "id": "184910",
    "code": 73,
    "description": "VM shutdown initiated by admin@internal on VM testvm001 (Host: olvmhost003.example.com).",
    "severity": "normal",
    "time": "2026-08-31 23:53:31.289000+02:00"
  }
]
```

---

### 5. `ovirt_vm_start`

Powers on a virtual machine by display name or UUID. Idempotent: if the VM is already `up`, it reports success immediately without redundant hypervisor calls.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `pause` *(bool, optional, default: false)*: If `true`, boots the VM into paused state.
  - `wait` *(bool, optional, default: false)*: If `true`, waits synchronously until the VM reaches the `up` state before returning.
  - `timeout_seconds` *(int, optional, default: 60)*: Maximum time to wait if `wait=true`.
- **Outputs (`VmLifecycleResult`):**
  - `success`: Boolean indicating if operation succeeded or was accepted.
  - `action`: `"start"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `previous_status`: Status prior to invocation (e.g. `"down"`).
  - `current_status`: Status after invocation (e.g. `"powering_up"` or `"up"`).
  - `message`: Human-readable summary.

**Example Output:**
```json
{
  "success": true,
  "action": "start",
  "vm_id": "2a6c96b7-4da0-422f-8e7c-aa1fd5448144",
  "vm_name": "testvm002",
  "previous_status": "down",
  "current_status": "powering_up",
  "message": "VM 'testvm002' start initiated successfully (status: powering_up)."
}
```

---

### 6. `ovirt_vm_stop`

Stops or shuts down a virtual machine. Supports both clean guest-initiated shutdown and hard power-off. **Safe-Mode protected**: In Safe Mode (`MCP_SAFE_MODE=true`), requires explicit `confirm=True`. Idempotent: if already `down`, reports success immediately.

> [!IMPORTANT]
> **Boot Readiness Guard:** Graceful shutdown (`graceful=True`) cannot execute if the virtual machine is currently booting (`powering_up`, `wait_for_launch`, or `reboot_in_progress`). At this boot stage, the guest operating system kernel and guest agent (`qemu-guest-agent` / vtools) have not finished initializing, making ACPI/vtools signals ineffective. `ovirt_vm_stop` validates boot readiness and will raise an error instructing the caller to wait until the VM is `up`, or specify `graceful=False` for an immediate hard power-off.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `graceful` *(bool, optional, default: true)*:
    - **`true` (Default):** Initiates a clean, orderly shutdown of the operating system inside the guest through the **oVirt / QEMU Guest Agent (vtools)** and ACPI. Services terminate properly and filesystem caches flush to disk.
    - **`false`:** Executes an immediate hard power-off (pulling the virtual plug / force kill). Use only when the guest OS is hung or unresponsive.
  - `force` *(bool, optional, default: false)*: If `true`, forces stop even if a backup is active.
  - `confirm` *(bool, optional, default: false)*: Explicit confirmation required when `MCP_SAFE_MODE=true`.
  - `wait` *(bool, optional, default: false)*: If `true`, blocks synchronously until the VM reaches `down` state.
  - `timeout_seconds` *(int, optional, default: 60)*: Maximum wait duration.
- **Outputs (`VmLifecycleResult`):**
  - `success`: Boolean indicating if shutdown/stop succeeded.
  - `action`: `"shutdown"` or `"stop"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `previous_status`: Status prior to stop.
  - `current_status`: Status after initiation (`"powering_down"` or `"down"`).
  - `graceful`: `true` if initiated via guest agent (vtools) / ACPI; `false` if hard power-off.
  - `message`: Human-readable summary.

**Example Output (Graceful Stop via vtools):**
```json
{
  "success": true,
  "action": "shutdown",
  "vm_id": "2a6c96b7-4da0-422f-8e7c-aa1fd5448144",
  "vm_name": "testvm002",
  "previous_status": "up",
  "current_status": "powering_down",
  "graceful": true,
  "message": "VM 'testvm002' graceful shutdown initiated via guest agent (vtools) / ACPI (status: powering_down)."
}
```

---

### 7. `ovirt_vm_shutdown`

Dedicated tool for initiating a clean, graceful shutdown of the operating system inside the guest VM via **guest tools (vtools / QEMU guest agent)** and ACPI. This is an alias for `ovirt_vm_stop(graceful=True)`.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `force` *(bool, optional, default: false)*: Force shutdown even if backup is active.
  - `confirm` *(bool, optional, default: false)*: Explicit confirmation required when `MCP_SAFE_MODE=true`.
  - `wait` *(bool, optional, default: false)*: Blocks synchronously until `down` state.
  - `timeout_seconds` *(int, optional, default: 60)*: Maximum wait duration.

---

### 8. `ovirt_vm_reboot`

Reboots a running virtual machine. **Safe-Mode protected**: requires explicit `confirm=True`. Rejects reboots if the VM is currently down with a helpful recommendation to use `ovirt_vm_start`.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `force` *(bool, optional, default: false)*: Force reboot even if a backup is active.
  - `confirm` *(bool, optional, default: false)*: Explicit confirmation required when `MCP_SAFE_MODE=true`.
  - `wait` *(bool, optional, default: false)*: If `true`, blocks until VM completes restart cycle and returns to `up` state.
  - `timeout_seconds` *(int, optional, default: 60)*: Maximum wait duration.
- **Outputs (`VmLifecycleResult`):**
  - `success`: Boolean indicating if reboot was initiated.
  - `action`: `"reboot"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `previous_status`: Status prior to reboot.
  - `current_status`: `"rebooting"` or `"up"`.
  - `message`: Human-readable summary.

---

### 9. `ovirt_vm_create`

Provisions a new virtual machine in oVirt / OLVM. Supports creation from the standard `Blank` template or existing OS templates, along with CPU, RAM, primary disk provisioning, and vNIC profiles.

- **Inputs:**
  - `name` *(string, required)*: Unique name for the virtual machine.
  - `cluster` *(string, required)*: Cluster name or UUID.
  - `template` *(string, optional, default: "Blank")*: Base template name or UUID.
  - `memory_mb` *(int, optional, default: 2048)*: RAM allocation in megabytes.
  - `cpu_cores` *(int, optional, default: 1)*: vCPU cores per socket.
  - `cpu_sockets` *(int, optional, default: 1)*: CPU sockets count.
  - `description` *(string, optional)*: Comment or metadata for the VM.
  - `os_type` *(string, optional)*: Operating system identifier (e.g. `rhel_8x64`, `other_linux`).
  - `disk_size_gb` *(int, optional)*: Size in GB for initial primary disk.
  - `storage_domain` *(string, optional)*: Target storage domain for disk.
  - `network_profile` *(string, optional)*: Name or UUID of vNIC profile (e.g. `ovirtmgmt`).
  - `wait` *(bool, optional, default: false)*: When `true`, blocks until VM reaches unlocked `down` status.
  - `timeout_seconds` *(int, optional, default: 120)*: Maximum wait duration.
- **Outputs (`VmCreateResult`):**
  - `success`: Boolean indicating if VM was created.
  - `vm_id`: UUID of the newly provisioned VM.
  - `vm_name`: Name of the VM.
  - `cluster_name`: Target cluster name.
  - `template_name`: Base template name.
  - `status`: Power/provisioning status (e.g. `"down"` or `"image_locked"`).
  - `memory_mb`: Allocated RAM.
  - `cpu_cores`: Total vCPUs.
  - `message`: Summary of created virtual machine.

**Example Output:**
```json
{
  "success": true,
  "vm_id": "5365d7a8-ff64-4dc7-b2c9-d97633b55565",
  "vm_name": "testvm001",
  "cluster_name": "DefaultCluster",
  "template_name": "Blank",
  "status": "down",
  "memory_mb": 1024,
  "cpu_cores": 1,
  "message": "Virtual machine 'testvm001' created successfully in cluster 'DefaultCluster' from template 'Blank'."
}
```

---

### 10. `ovirt_vm_delete`

Permanently deletes a virtual machine from the oVirt / OLVM engine. **Safe-Mode protected**: In Safe Mode (`MCP_SAFE_MODE=true`), requires explicit `confirm=True`. Prevents accidental deletion of running VMs unless `force=True` is explicitly specified.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `detach_only` *(bool, optional, default: false)*: When `true`, virtual disks are preserved in storage domains and only detached from the VM. When `false`, disks are permanently erased.
  - `force` *(bool, optional, default: false)*: When `true`, force-powers off a running VM before deletion and ignores disk locks.
  - `confirm` *(bool, optional, default: false)*: Explicit confirmation required when `MCP_SAFE_MODE=true`.
  - `wait` *(bool, optional, default: false)*: When `true`, blocks until the VM is confirmed removed from hypervisor inventory.
  - `timeout_seconds` *(int, optional, default: 60)*: Maximum wait duration.
- **Outputs (`VmDeleteResult`):**
  - `success`: Boolean indicating if deletion was successful.
  - `vm_id`: UUID of deleted virtual machine.
  - `vm_name`: Name of deleted virtual machine.
  - `disks_detached_only`: Whether disks were preserved.
  - `message`: Outcome description.

**Example Output:**
```json
{
  "success": true,
  "vm_id": "5365d7a8-ff64-4dc7-b2c9-d97633b55565",
  "vm_name": "testvm001",
  "disks_detached_only": false,
  "message": "Virtual machine 'testvm001' deleted successfully. Attached disks were deleted."
}
```

---

### 11. `ovirt_vm_migrate`

Live-migrates an actively running virtual machine to another hypervisor host with zero downtime.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `target_host` *(string, optional)*: Destination hypervisor host name or UUID. If omitted, the engine automatically selects the optimal host based on cluster load-balancing policies.
  - `force` *(bool, optional, default: false)*: Force migration even if the VM is marked as non-migratable.
  - `wait` *(bool, optional, default: false)*: When `true`, blocks until migration completes and the VM is confirmed running on the destination host.
  - `timeout_seconds` *(int, optional, default: 120)*: Maximum wait duration.
- **Outputs (`VmMigrateResult`):**
  - `success`: Boolean indicating if migration succeeded.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `source_host`: Source host before migration.
  - `target_host`: Target host after migration.
  - `status`: VM status after action (`"up"` or `"migrating"`).
  - `message`: Outcome description.

---

### 12. `ovirt_vm_pin`

Pins a virtual machine to run exclusively on a specific hypervisor host. Disables automatic cluster live migration and locks placement to the designated host.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `host` *(string, required)*: Target physical host name or UUID.
- **Outputs (`VmPinResult`):**
  - `success`: Boolean indicating success.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `affinity`: `"pinned"`.
  - `pinned_hosts`: List of pinned host names.
  - `message`: Outcome description.

---

### 13. `ovirt_vm_unpin`

Unpins a previously pinned virtual machine, restoring normal dynamic live migration and cluster load-balancing across all hosts. Reversible counterpart to `ovirt_vm_pin`.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
- **Outputs (`VmPinResult`):**
  - `success`: Boolean indicating success.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `affinity`: `"migratable"`.
  - `pinned_hosts`: Empty list `[]`.
  - `message`: Outcome description.

---

### 14. `ovirt_vm_snapshot_list`

Lists all point-in-time snapshots of a virtual machine, including snapshot UUID, description, status (`ok`, `locked`, `in_preview`), snapshot type (`regular`, `active`), creation timestamp, and RAM persist state.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
- **Outputs:** `list[VmSnapshotInfo]`
  - `id`: UUID of the snapshot.
  - `description`: Snapshot description or label.
  - `snapshot_status`: Snapshot state (`ok`, `locked`, etc.).
  - `snapshot_type`: `regular` (restore point) or `active` (live state container).
  - `date`: ISO timestamp of creation.
  - `persist_memorystate`: Whether RAM state was captured.

**Example Output:**
```json
[
  {
    "id": "e42cfb8a-8c31-4191-8846-fcad77b5dcb0",
    "description": "Pre-upgrade backup",
    "snapshot_status": "ok",
    "snapshot_type": "regular",
    "date": "2026-11-18 14:30:00+00:00",
    "persist_memorystate": false
  }
]
```

---

### 15. `ovirt_vm_snapshot_create`

Creates a point-in-time snapshot of a virtual machine. Supports live snapshots on running VMs as well as offline snapshots on stopped VMs.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `description` *(string, required)*: Informative description or label for the snapshot.
  - `persist_memory` *(bool, optional, default: false)*: When `true`, saves running guest RAM state along with disk state.
  - `wait` *(bool, optional, default: false)*: When `true`, blocks synchronously until snapshot creation completes and reaches `ok` status.
  - `timeout_seconds` *(int, optional, default: 180)*: Maximum wait duration.
- **Outputs (`VmSnapshotResult`):**
  - `success`: Boolean indicating if snapshot creation was initiated.
  - `action`: `"create"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `snapshot_id`: UUID of the created snapshot.
  - `message`: Outcome description.

---

### 16. `ovirt_vm_snapshot_restore`

Restores (reverts) a virtual machine to a previous snapshot state. **Destructive action**: Requires explicit `confirm=True` in Safe Mode (`MCP_SAFE_MODE=true`). The virtual machine **must be stopped (`down`)** before restoring.

- **Dual Restore Paradigms**:
  1. **Disk-only restore (`restore_memory=False`)**: Restores disks to the crash-consistent snapshot point. The VM remains in `down` status until explicitly powered on.
  2. **RAM + Disk restore (`restore_memory=True`)**: Restores both disk state and running guest memory (RAM). Requires that the snapshot was created with `persist_memory=True`. A strict pre-flight guard checks that the snapshot contains memory state before executing.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `snapshot_id` *(string, required)*: UUID of the snapshot to restore.
  - `restore_memory` *(bool, optional, default: false)*: If `true`, restores the saved guest RAM memory state (requires snapshot created with `persist_memory=True`).
  - `confirm` *(bool, optional, default: false)*: Confirmation required in Safe Mode.
  - `wait` *(bool, optional, default: false)*: When `true`, blocks until restore finishes.
  - `timeout_seconds` *(int, optional, default: 180)*: Maximum wait duration.
- **Outputs (`VmSnapshotResult`):**
  - `success`: Boolean indicating if restore succeeded.
  - `action`: `"restore"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `snapshot_id`: Restored snapshot UUID.
  - `restore_memory`: Whether RAM state was restored.
  - `message`: Outcome description.

---

### 17. `ovirt_vm_snapshot_preview`

Switches the virtual machine into preview mode on top of a historical snapshot without permanently overwriting the current state.

In oVirt/OLVM, previewing mounts temporary copy-on-write overlays on top of the snapshot disks. You can power on the VM, inspect services, and run validation scripts. If the results are unsatisfactory, use `ovirt_vm_snapshot_undo` to cleanly discard the preview without residue. If the results are confirmed, use `ovirt_vm_snapshot_commit` to make the snapshot permanently active.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `snapshot_id` *(string, required)*: UUID of the snapshot to preview.
  - `restore_memory` *(bool, optional, default: false)*: If `true`, boots the VM directly from the saved RAM state.
  - `confirm` *(bool, optional, default: false)*: Confirmation required in Safe Mode.
  - `wait` *(bool, optional, default: false)*: When `true`, blocks until snapshot status reaches `in_preview`.
  - `timeout_seconds` *(int, optional, default: 180)*: Maximum wait duration.
- **Outputs (`VmSnapshotResult`):**
  - `success`: Boolean indicating preview initiated.
  - `action`: `"preview"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `snapshot_id`: UUID of previewed snapshot.
  - `restore_memory`: Whether RAM state was restored.
  - `message`: Outcome description.

---

### 18. `ovirt_vm_snapshot_commit`

Permanently commits an active snapshot preview, making the previewed state the VM's permanent operational baseline.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `confirm` *(bool, optional, default: false)*: Confirmation required in Safe Mode.
  - `wait` *(bool, optional, default: false)*: When `true`, blocks until preview delta consolidation completes.
  - `timeout_seconds` *(int, optional, default: 180)*: Maximum wait duration.
- **Outputs (`VmSnapshotResult`):**
  - `success`: Boolean indicating commit success.
  - `action`: `"commit"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `message`: Outcome description.

---

### 19. `ovirt_vm_snapshot_undo`

Undoes the active snapshot preview and restores the VM to its exact state before preview was initiated. Reversible counterpart to `ovirt_vm_snapshot_preview`. Discards all preview temporary disks without affecting historical snapshot data.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `confirm` *(bool, optional, default: false)*: Confirmation required in Safe Mode.
  - `wait` *(bool, optional, default: false)*: When `true`, blocks until preview teardown completes and VM unlocks.
  - `timeout_seconds` *(int, optional, default: 180)*: Maximum wait duration.
- **Outputs (`VmSnapshotResult`):**
  - `success`: Boolean indicating undo success.
  - `action`: `"undo"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `message`: Outcome description.

---

### 20. `ovirt_vm_snapshot_delete`

Deletes a snapshot and consolidates its delta disk changes back into the parent disk image. **Destructive action**: Requires explicit `confirm=True` in Safe Mode (`MCP_SAFE_MODE=true`). Reversible counterpart ensuring no unneeded snapshots linger in storage domains.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `snapshot_id` *(string, required)*: UUID of the snapshot to delete.
  - `confirm` *(bool, optional, default: false)*: Confirmation required in Safe Mode.
  - `wait` *(bool, optional, default: false)*: When `true`, blocks until snapshot removal and consolidation complete.
  - `timeout_seconds` *(int, optional, default: 180)*: Maximum wait duration.
- **Outputs (`VmSnapshotResult`):**
  - `success`: Boolean indicating success.
  - `action`: `"delete"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `snapshot_id`: Deleted snapshot UUID.
  - `message`: Outcome description.

---

### 21. `ovirt_vm_cdrom_list`

Lists virtual CD-ROM drives configured on a virtual machine, reporting device UUIDs, attached ISO image file names, and whether each drive is empty.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
- **Outputs:** `list[VmCdromInfo]`
  - `id`: UUID of the CD-ROM device.
  - `file_id`: Name of the attached ISO file, or `null` if empty.
  - `is_empty`: Boolean indicating whether media is inserted.

**Example Output:**
```json
[
  {
    "id": "00000000-0000-0000-0000-000000000000",
    "file_id": null,
    "is_empty": true
  }
]
```

---

### 22. `ovirt_vm_iso_attach`

Attaches (mounts) an ISO file from an ISO storage domain into the virtual machine's CD-ROM drive. When the VM is running and `current` is omitted, media is automatically hot-plugged into the active guest and saved to persistent VM configuration.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `iso_file` *(string, required)*: ISO filename (must exist in an active ISO storage domain).
  - `cdrom_id` *(string, optional)*: Specific CD-ROM device UUID (defaults to primary drive).
  - `current` *(bool, optional)*: If `true`, applies only to running guest (hot-swap); if `false`, applies only persistently; if omitted, automatically applies to both when running.
- **Outputs (`VmCdromResult`):**
  - `success`: Boolean indicating success.
  - `action`: `"attach"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `cdrom_id`: Device UUID.
  - `iso_file`: Attached ISO filename.
  - `current`: Whether live guest media was hot-plugged.
  - `message`: Outcome description.

---

### 23. `ovirt_vm_iso_eject`

Ejects / unmounts any mounted ISO media from the virtual machine's CD-ROM drive. Reversible counterpart to `ovirt_vm_iso_attach`. Supports live hot-eject on running VMs.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `cdrom_id` *(string, optional)*: Specific CD-ROM device UUID (defaults to primary drive).
  - `current` *(bool, optional)*: If `true`, applies only to running guest; if `false`, applies persistently; if omitted, applies to both when running.
- **Outputs (`VmCdromResult`):**
  - `success`: Boolean indicating success.
  - `action`: `"eject"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `cdrom_id`: Device UUID.
  - `iso_file`: `null`.
  - `current`: Whether live eject was performed.
  - `message`: Outcome description.

---

### 24. `ovirt_storage_iso_list`

Lists all available ISO image installation files stored across active ISO storage domains. Enables AI agents and administrators to discover available OS installation media before attaching.

- **Inputs:**
  - `storage_domain` *(string, optional)*: Filter by specific storage domain name or UUID.
- **Outputs:** `list[IsoFileInfo]`
  - `id`: File ID or filename.
  - `name`: ISO filename.
  - `storage_domain_id`: ISO storage domain UUID.
  - `storage_domain_name`: ISO storage domain display name.

**Example Output:**
```json
[
  {
    "id": "OracleLinux-R8-U10-x86_64-dvd.iso",
    "name": "OracleLinux-R8-U10-x86_64-dvd.iso",
    "storage_domain_id": "de66dbc8-c5df-48ee-993e-387a9283f7e3",
    "storage_domain_name": "ISO"
  }
]
```

---

### 25. `ovirt_disk_list`

Lists virtual disks in the virtualization environment across storage domains, including floating unattached disks and disks attached to virtual machines. Supports filtering by storage domain, custom search expressions, or listing disks attached to a specific virtual machine via `vm_name_or_id`.

- **Inputs:**
  - `storage_domain` *(string, optional)*: Filter by specific storage domain name or UUID.
  - `search` *(string, optional)*: Engine search query filter (e.g. `name=data*`).
  - `vm_name_or_id` *(string, optional)*: Filter disks attached to a specific virtual machine.
- **Outputs:** `list[DiskDetail]`
  - `id`: Disk UUID.
  - `name`: Disk name or alias.
  - `status`: State (`ok`, `locked`, etc.).
  - `provisioned_size_gb`: Allocated logical capacity.
  - `actual_size_gb`: Storage space physically consumed.
  - `disk_format`: `"cow"` or `"raw"`.
  - `content_type`: `"data"`, `"iso"`, or `"ovf_store"`.
  - `storage_domain_name`: Hosting storage domain.

---

### 26. `ovirt_disk_attach`

Attaches an existing floating virtual disk to a virtual machine. Configurable interface (`virtio`, `virtio_scsi`, `sata`, `ide`), bootable flag, active state, and read-only mode.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `disk_id` *(string, required)*: UUID of the existing floating disk.
  - `interface` *(string, optional, default: "virtio")*: Controller bus interface.
  - `bootable` *(bool, optional, default: false)*: Whether disk is boot device.
  - `active` *(bool, optional, default: true)*: Whether disk is active/plugged.
  - `read_only` *(bool, optional, default: false)*: Whether to mount read-only.
- **Outputs (`VmDiskAttachmentResult`):**
  - `success`: Boolean indicating success.
  - `action`: `"attach"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `disk_id`: Attached disk UUID.
  - `interface`: Interface type used.
  - `message`: Outcome description.

---

### 27. `ovirt_disk_detach`

Detaches a virtual disk from a virtual machine **without deleting the underlying storage image** (`detach_only=True`). Reversible counterpart to `ovirt_disk_attach`. **Destructive action**: Requires explicit `confirm=True` in Safe Mode (`MCP_SAFE_MODE=true`).

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `disk_id` *(string, required)*: UUID of the disk to detach.
  - `confirm` *(bool, optional, default: false)*: Safe-mode confirmation flag.
  - `wait` *(bool, optional, default: false)*: Blocks until confirmed detached.
  - `timeout_seconds` *(int, optional, default: 60)*: Maximum wait duration.
- **Outputs (`VmDiskAttachmentResult`):**
  - `success`: Boolean indicating success.
  - `action`: `"detach"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `disk_id`: Detached disk UUID.
  - `message`: Outcome description.

---

### 28. `ovirt_disk_create`

Creates a new virtual disk. If `vm_name_or_id` is provided, attaches the disk directly to that VM; if omitted, creates a floating virtual disk on the specified storage domain. Supports thin-provisioned COW or RAW formats, target storage domains, interface selection, and synchronous wait until disk images are fully allocated.

- **Inputs:**
  - `size_gb` *(int, required)*: Provisioned disk capacity in gigabytes.
  - `storage_domain` *(string, required)*: Target storage domain name or UUID.
  - `disk_name` *(string, optional)*: Custom alias for disk.
  - `disk_format` *(string, optional, default: "cow")*: Format (`"cow"` or `"raw"`).
  - `vm_name_or_id` *(string, optional)*: Attach directly to this VM (optional).
  - `interface` *(string, optional, default: "virtio")*: Interface type (`"virtio"` or `"virtio_scsi"`).
  - `bootable` *(bool, optional, default: false)*: Mark as bootable.
  - `active` *(bool, optional, default: true)*: Activate immediately.
  - `wait` *(bool, optional, default: false)*: Block until disk is unlocked and ready.
  - `timeout_seconds` *(int, optional, default: 120)*: Maximum wait duration.
- **Outputs (`DiskCreateResult | VmDiskAttachmentResult`):**
  - `success`: Boolean indicating success.
  - `action`: `"create"`.
  - `disk_id`: Newly created disk UUID.
  - `message`: Outcome description.

---

### 29. `ovirt_disk_resize`

Expands the provisioned capacity of a virtual disk to a larger size in gigabytes. **Safe-Mode protected**: requires `confirm=True`. Note: In virtualization hypervisors, disk shrinking is strictly prohibited to protect against filesystem truncation and data loss.

- **Inputs:**
  - `disk_id` *(string, required)*: UUID of the virtual disk to resize.
  - `size_gb` *(int, required)*: New total provisioned capacity in GB (must be strictly larger than current size).
  - `confirm` *(bool, optional, default: false)*: Safe-mode confirmation flag.
- **Outputs (`DiskResizeResult`):**
  - `success`: Boolean indicating success.
  - `disk_id`: Resized disk UUID.
  - `old_size_gb`: Size prior to expansion.
  - `new_size_gb`: Expanded size in GB.
  - `message`: Outcome description.

---

### 30. `ovirt_vm_nic_list`

Lists all virtual network interface cards (vNICs) attached to a virtual machine, reporting interface name, device UUID, assigned MAC address, interface model (`virtio`, `e1000`), plugged state, linked state, and associated vNIC profile.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
- **Outputs:** `list[VmNicDetail]`

---

### 31. `ovirt_vm_nic_add`

Adds a new virtual network interface card (vNIC) to a virtual machine, attaching it to a specific vNIC profile on a logical network.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `name` *(string, required)*: Name for new vNIC (e.g. `'nic2'`).
  - `profile` *(string, required)*: Name or UUID of vNIC profile (e.g. `'ovirtmgmt'`).
  - `interface` *(string, optional, default: "virtio")*: Controller model (`"virtio"`, `"e1000"`).
  - `plugged` *(bool, optional, default: true)*: Whether NIC is plugged into slot.
  - `linked` *(bool, optional, default: true)*: Whether network cable is linked.
- **Outputs (`VmNicResult`):**
  - `success`: Boolean indicating success.
  - `action`: `"add"`.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `nic_id`: Device UUID.
  - `nic_name`: Interface name.
  - `mac_address`: Generated MAC address.
  - `message`: Outcome description.

---

### 32. `ovirt_vm_nic_remove`

Removes a virtual network interface card (vNIC) from a virtual machine. Reversible counterpart to `ovirt_vm_nic_add`. **Destructive action**: Requires explicit `confirm=True` in Safe Mode (`MCP_SAFE_MODE=true`).

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `nic_name_or_id` *(string, required)*: Name or UUID of vNIC to remove.
  - `confirm` *(bool, optional, default: false)*: Safe-mode confirmation flag.
- **Outputs (`VmNicResult`):**
  - `success`: Boolean indicating success.
  - `action`: `"remove"`.
  - `vm_id`: VM UUID.
  - `nic_id`: Removed vNIC UUID.
  - `nic_name`: Removed vNIC name.
  - `message`: Outcome description.

---

### 33. `ovirt_network_profile_list`

Lists available virtual network interface profiles (vNIC profiles) across logical networks in the environment.

- **Inputs:**
  - `network` *(string, optional)*: Filter by specific logical network name or UUID.
- **Outputs:** `list[VnicProfileInfo]`
  - `id`: Profile UUID.
  - `name`: Profile name.
  - `network_name`: Parent logical network name.
  - `network_id`: Parent logical network UUID.
  - `pass_through`: Whether SR-IOV passthrough is enabled.
  - `port_mirroring`: Whether port mirroring is active.

---

### 34. `ovirt_vm_update`

Updates virtual machine compute resources (RAM memory in MB, CPU cores/sockets/threads), description, or High Availability failover status. Modifying hardware CPU or memory is Safe-Mode guarded and requires explicit `confirm=True`.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `memory_mb` *(int, optional)*: New RAM allocation in megabytes.
  - `cpu_cores` *(int, optional)*: CPU cores per socket.
  - `cpu_sockets` *(int, optional)*: CPU sockets count.
  - `cpu_threads` *(int, optional)*: Threads per CPU core.
  - `description` *(string, optional)*: Updated description text.
  - `ha_enabled` *(bool, optional)*: Enable or disable High Availability.
  - `confirm` *(bool, optional, default: false)*: Safe-mode confirmation flag.
- **Outputs (`VmUpdateResult`):**
  - `success`: Boolean indicating success.
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `memory_mb`: Confirmed RAM size in MB.
  - `cpu_cores`: Confirmed vCPU cores.
  - `ha_enabled`: Confirmed HA flag.
  - `message`: Outcome description.

---

### 35. `ovirt_vm_graphics_consoles`

Lists available graphical display consoles (VNC / SPICE) configured for a virtual machine, reporting protocol, display ports, and console device identifiers.

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
- **Outputs:** `list[VmGraphicsConsoleInfo]`
  - `id`: Console device UUID.
  - `protocol`: `"vnc"` or `"spice"`.
  - `port`: Cleartext display port.
  - `tls_port`: Encrypted TLS display port.

---

### 36. `ovirt_vm_ticket`

Generates a temporary, single-use authentication password/ticket to connect to a running virtual machine's graphical console (VNC / SPICE). The virtual machine must be running (`status='up'`).

- **Inputs:**
  - `name_or_id` *(string, required)*: VM display name or UUID.
  - `expiry_seconds` *(int, optional, default: 120)*: Validity window in seconds.
- **Outputs (`VmConsoleTicket`):**
  - `vm_id`: VM UUID.
  - `vm_name`: VM display name.
  - `ticket_value`: Temporary connection password.
  - `expiry_seconds`: Ticket validity duration.
  - `message`: Instructions for connecting.

---

### 37. `ovirt_host_list`

Lists all hypervisor hosts in the virtualization environment across clusters. Reports operational status, cluster name, management IP address, physical CPU topology, total RAM in GB, active VMs count, SPM (Storage Pool Manager) status, and nested virtualization detection.

- **Inputs:**
  - `cluster` *(string, optional)*: Filter hosts by cluster name or UUID.
  - `status` *(string, optional)*: Filter by status (e.g. `'up'`, `'maintenance'`, `'down'`).
- **Outputs:** `list[HostSummary]`
  - `id`: Hypervisor host UUID.
  - `name`: FQDN / display name.
  - `status`: Host state (`up`, `maintenance`, `down`, `non_operational`).
  - `cluster_name`: Parent cluster name.
  - `address`: Management network IP address / hostname.
  - `active_vms_count`: Number of virtual machines currently running on this host.
  - `spm_status`: Storage Pool Manager role (`spm`, `contending`, `none`).
  - `is_nested`: Boolean indicating whether hypervisor is nested inside VMware, KVM, etc.
  - `cpu_model`: Host CPU model detected by engine.
  - `cpu_cores`: Physical core count.
  - `cpu_sockets`: Physical socket count.
  - `total_memory_gb`: Total physical RAM in gigabytes.
  - `update_available`: Boolean indicating whether OS or package updates are available for the host.

**Example Output:**
```json
[
  {
    "id": "bd72f2ef-9472-4b94-b961-08cfd40dbc31",
    "name": "olvmhost002.example.com",
    "status": "up",
    "cluster_name": "DefaultCluster",
    "cluster_id": "b873d6c8-d13e-42f6-980a-fe8d4a01fdc3",
    "address": "192.0.2.12",
    "active_vms_count": 0,
    "spm_status": "none",
    "is_nested": true,
    "cpu_model": "AMD Ryzen 5 3600 6-Core Processor",
    "cpu_cores": 1,
    "cpu_sockets": 10,
    "total_memory_gb": 20.71,
    "update_available": true
  }
]
```

---

### 38. `ovirt_host_get`

Retrieves comprehensive hardware, BIOS, OS distribution, kernel, VDSM/libvirt versions, power management (fencing) configuration, and hardware device counts for a single hypervisor host.

- **Inputs:**
  - `name_or_id` *(string, required)*: Host display name or UUID.
- **Outputs (`HostDetail`):**
  - `id`: Host UUID.
  - `name`: Host display name.
  - `status`: Operational status.
  - `cluster_name`: Cluster name.
  - `address`: IP address.
  - `ssh_port`: SSH daemon port.
  - `hardware`: Manufacturer, product model, chassis serial number, UUID.
  - `os`: OS distribution, release, kernel version, KVM, libvirt, and VDSM node versions.
  - `power_management`: Out-of-band IPMI / fencing configuration (`enabled`, `pm_type`, `address`).
  - `nics_count`: Physical network interface count.
  - `numa_nodes_count`: NUMA topology node count.
  - `update_available`: Boolean indicating whether OS or package updates are available.

---

### 39. `ovirt_host_stats`

Retrieves real-time telemetry metrics and system load statistics for a hypervisor host, including active CPU utilization percentage, user/system/idle breakdown, 5-minute system load average, memory allocated/used/free/percentage, swap usage, active VM count, and system boot time.

- **Inputs:**
  - `name_or_id` *(string, required)*: Host display name or UUID.
- **Outputs (`HostStats`):**
  - `host_id`: Host UUID.
  - `host_name`: Host display name.
  - `cpu_usage_percent`: Total CPU active utilization (0-100%).
  - `cpu_user_percent`: User space CPU consumption %.
  - `cpu_system_percent`: Kernel space CPU consumption %.
  - `cpu_idle_percent`: CPU idle %.
  - `cpu_load_avg_5m`: 5-minute system load average.
  - `memory_total_gb`: Total RAM in GB.
  - `memory_used_gb`: Consumed RAM in GB.
  - `memory_free_gb`: Available RAM in GB.
  - `memory_used_percent`: Memory utilization %.
  - `swap_used_mb`: Active swap memory in MB.
  - `boot_time`: Formatted system boot timestamp.

---

### 40. `ovirt_host_maintenance`

Places a hypervisor host into maintenance mode (`deactivate`). Initiates an orderly, non-disruptive evacuation of all running virtual machines, live-migrating them to other active hosts in the cluster.

> [!IMPORTANT]
> **Enterprise Pre-condition & Safety Guards:**
> 1. **Pinned VM Guard:** If any virtual machine is pinned exclusively to this host (`affinity="pinned"` or non-migratable), oVirt cannot live-migrate it. `ovirt_host_maintenance` inspects running workloads and automatically rejects the operation with a list of affected pinned VMs unless `stop_pinned_vms=True` is explicitly specified.
> 2. **SPM Role Awareness:** If the host is currently the Storage Pool Manager (`spm_status="spm"`), the tool logs a notice that SPM role re-election and data center storage lease migration will occur.
> 3. **Non-binary State Polling:** Live migration of workloads across multi-gigabyte VM memory spaces takes time. When `wait=True` is set, the tool blocks synchronously, tracking the transitional `preparing_for_maintenance` state until host status is confirmed `maintenance` AND active VM count reaches 0.

- **Inputs:**
  - `name_or_id` *(string, required)*: Host display name or UUID.
  - `stop_pinned_vms` *(bool, optional, default: false)*: Allow engine to stop/shut down non-migratable pinned VMs.
  - `confirm` *(bool, optional, default: false)*: Safe-mode confirmation flag.
  - `wait` *(bool, optional, default: false)*: Block until maintenance mode is achieved and VMs count is 0.
  - `timeout_seconds` *(int, optional, default: 300)*: Maximum wait duration.
- **Outputs (`HostLifecycleResult`):**
  - `success`: Boolean indicating success.
  - `action`: `"maintenance"`.
  - `host_id`: Host UUID.
  - `host_name`: Host display name.
  - `previous_status`: Status prior to command.
  - `current_status`: `"maintenance"`.
  - `active_vms_count`: Confirmed remaining VMs (0 upon completion).
  - `message`: Outcome description.

---

### 41. `ovirt_host_activate`

Activates a hypervisor host from maintenance mode back to active `up` status. Reversible counterpart to `ovirt_host_maintenance`, restoring the hypervisor's ability to host workloads and participate in cluster load-balancing.

- **Inputs:**
  - `name_or_id` *(string, required)*: Host display name or UUID.
  - `wait` *(bool, optional, default: false)*: Block until host reaches active `up` status.
  - `timeout_seconds` *(int, optional, default: 180)*: Maximum wait duration.
- **Outputs (`HostLifecycleResult`):**
  - `success`: Boolean indicating success.
  - `action`: `"activate"`.
  - `host_id`: Host UUID.
  - `host_name`: Host display name.
  - `previous_status`: Status prior to activation.
  - `current_status`: `"up"`.
  - `message`: Outcome description.

---

### 42. `ovirt_host_restart`

Reboots a hypervisor host via out-of-band power management fencing.

> [!CAUTION]
> **Strict Enterprise Safety Gate ("Guard-Before-Act"):**
> To prevent hypervisor crashes and catastrophic service outages:
> 1. **Maintenance Status Gate:** The host **MUST be in `maintenance` status**. If the host is currently active (`up`), `preparing_for_maintenance`, or in any other transitional state, reboot is **strictly rejected**.
> 2. **Zero VMs Gate:** Running virtual machine count **MUST be exactly 0**.
> 3. **Power Management / Fencing Gate:** Verifies that physical IPMI / fencing agents are configured and enabled. In nested virtualization (e.g. VMware ESXi / KVM nested nodes) or lab setups without physical IPMI, the tool detects this upfront and reports an explicit diagnostic error rather than triggering an unrecoverable failure.

- **Inputs:**
  - `name_or_id` *(string, required)*: Host display name or UUID.
  - `confirm` *(bool, optional, default: false)*: Confirmation required when `MCP_SAFE_MODE=true`.
  - `wait` *(bool, optional, default: false)*: Block until host completes reboot cycle.
  - `timeout_seconds` *(int, optional, default: 300)*: Maximum wait duration.
- **Outputs (`HostLifecycleResult`):**
  - `success`: Boolean indicating reboot initiated.
  - `action`: `"restart"`.
  - `host_id`: Host UUID.
  - `host_name`: Host display name.
  - `previous_status`: Previous status (`"maintenance"`).
  - `current_status`: New status (`"reboot"` or `"maintenance"`).
  - `message`: Outcome description.

---

### 43. `ovirt_host_nic_list`

Lists physical network interfaces (pNICs) on a hypervisor host, including device name, MAC address, link speed in Mbps, link status (`up`/`down`), configured IPv4/IPv6 addresses, attached logical networks, and bonding slave memberships.

- **Inputs:**
  - `name_or_id` *(string, required)*: Host display name or UUID.
- **Outputs:** `list[HostNicInfo]`

---

### 44. `ovirt_host_numa_list`

Lists Non-Uniform Memory Access (NUMA) node topology for a hypervisor host, reporting node index, RAM memory allocated to each NUMA node in MB, and assigned physical CPU core IDs.

- **Inputs:**
  - `name_or_id` *(string, required)*: Host display name or UUID.
- **Outputs:** `list[HostNumaNodeInfo]`

---

### 45. `ovirt_host_device_list`

Lists hardware and PCI bus devices configured on a hypervisor host (SR-IOV virtual functions, GPU passthrough devices, Fibre Channel HBAs, network adapters).

- **Inputs:**
  - `name_or_id` *(string, required)*: Host display name or UUID.
  - `max_devices` *(int, optional, default: 50)*: Maximum devices to return.
- **Outputs:** `list[HostDeviceInfo]`
  - `id`: PCI device address identifier.
  - `name`: Device name.
  - `product`: Hardware product description.
  - `vendor`: Hardware vendor name.
  - `driver`: Active kernel driver module.
  - `iommu_group`: IOMMU group index for PCI passthrough.

---

### 46. `ovirt_host_storage_list`

Lists storage domains and SAN/block storage server connections accessible to a hypervisor host.

- **Inputs:**
  - `name_or_id` *(string, required)*: Host display name or UUID.
- **Outputs:** `list[dict]` containing storage domain ID, name, storage type, and target addresses.

---

### 47. `ovirt_host_events`

Retrieves host-specific audit history, hardware alerts, SPM role elections, and operational events.

- **Inputs:**
  - `name_or_id` *(string, required)*: Host display name or UUID.
  - `max_events` *(int, optional, default: 25)*: Maximum number of events to return.
  - `severity` *(string, optional)*: Filter by severity (`'normal'`, `'warning'`, `'error'`, `'alert'`).
- **Outputs:** `list[HostEvent]`
  - `id`: Event ID.
  - `code`: oVirt event code integer.
  - `severity`: Event severity level.
  - `description`: Event message.
  - `timestamp`: Event timestamp.

---

### 48. `ovirt_affinity_label_list`

Lists all global Affinity Labels registered in the oVirt/OLVM engine, including the hypervisor hosts and virtual machines assigned to each label.

- **Inputs:** None.
- **Outputs:** `list[AffinityLabelInfo]`
  - `id`: UUID of the label.
  - `name`: Human-readable label name.
  - `hosts`: List of hypervisor host names currently bearing this label.
  - `vms`: List of virtual machine names currently bearing this label.

---

### 49. `ovirt_affinity_label_create`

Creates a new global Affinity Label in oVirt/OLVM.

- **Inputs:**
  - `name` *(string, required)*: Unique label name (e.g. `database-nodes`, `pci-passthrough-hosts`).
- **Outputs:** `AffinityLabelResult`
  - `success`: Whether creation succeeded.
  - `label_id`: UUID of the created label.
  - `label_name`: Name of the label.
  - `message`: Outcome description.

---

### 50. `ovirt_affinity_label_delete`

Deletes an Affinity Label. Protected by safe-mode confirmation (`confirm=True`). If the label is currently attached to hosts or VMs, oVirt requires detaching it first. Setting `detach_first=True` safely unassigns the label from all entities before deletion.

- **Inputs:**
  - `name_or_id` *(string, required)*: Label name or UUID.
  - `confirm` *(bool, optional, default: False)*: Confirmation flag required in safe-mode.
  - `detach_first` *(bool, optional, default: False)*: Automatically unassign from all hosts and VMs before deleting to avoid HTTP 409 conflicts.
- **Outputs:** `AffinityLabelResult`

---

### 51. `ovirt_host_label_list`

Lists all Affinity Labels assigned to a specific hypervisor host.

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Host name or UUID.
- **Outputs:** `list[str]` of affinity label names.

---

### 52. `ovirt_host_label_assign`

Assigns an Affinity Label to a hypervisor host.

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Host name or UUID.
  - `label_name_or_id` *(string, required)*: Affinity label name or UUID.
- **Outputs:** `EntityLabelResult`
  - `success`: Whether assignment succeeded.
  - `entity_name`: Name of the host.
  - `label_name`: Name of the assigned label.
  - `current_labels`: Complete list of labels currently on this host.

---

### 53. `ovirt_host_label_unassign`

Unassigns an Affinity Label from a hypervisor host (symmetric, reversible counterpart of `ovirt_host_label_assign`).

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Host name or UUID.
  - `label_name_or_id` *(string, required)*: Affinity label name or UUID to remove.
- **Outputs:** `EntityLabelResult`

---

### 54. `ovirt_vm_label_list`

Lists all Affinity Labels assigned to a virtual machine.

- **Inputs:**
  - `vm_name_or_id` *(string, required)*: VM name or UUID.
- **Outputs:** `list[str]` of affinity label names.

---

### 55. `ovirt_vm_label_assign`

Assigns an Affinity Label to a virtual machine.

- **Inputs:**
  - `vm_name_or_id` *(string, required)*: VM name or UUID.
  - `label_name_or_id` *(string, required)*: Affinity label name or UUID.
- **Outputs:** `EntityLabelResult`

---

### 56. `ovirt_vm_label_unassign`

Unassigns an Affinity Label from a virtual machine (symmetric, reversible counterpart of `ovirt_vm_label_assign`).

- **Inputs:**
  - `vm_name_or_id` *(string, required)*: VM name or UUID.
  - `label_name_or_id` *(string, required)*: Affinity label name or UUID to remove.
- **Outputs:** `EntityLabelResult`

---

### 57. `ovirt_cluster_affinity_group_list`

Lists all Affinity Groups defined within a cluster, including rules (positive/negative, enforcing), member VMs, member Hosts, and label associations.

- **Inputs:**
  - `cluster_name_or_id` *(string, required)*: Cluster name or UUID.
- **Outputs:** `list[AffinityGroupInfo]`
  - `id`: UUID of the affinity group.
  - `name`: Group name.
  - `cluster_name`: Name of the cluster.
  - `vms_rule`: `AffinityRuleConfig` (`enabled`, `positive`, `enforcing`).
  - `hosts_rule`: `AffinityRuleConfig` (`enabled`, `positive`, `enforcing`).
  - `vms`: Member VM names or IDs.
  - `hosts`: Member Host names or IDs.
  - `vm_labels`: Member VM label names.
  - `host_labels`: Member Host label names.

---

### 58. `ovirt_cluster_affinity_group_get`

Retrieves detailed configuration and member lists of a specific Affinity Group in a cluster.

- **Inputs:**
  - `cluster_name_or_id` *(string, required)*: Cluster name or UUID.
  - `group_name_or_id` *(string, required)*: Affinity group name or UUID.
- **Outputs:** `AffinityGroupInfo`

---

### 59. `ovirt_cluster_affinity_group_create`

Creates a new Affinity Group in a cluster with fine-grained VM-to-VM and VM-to-Host rules.

- **Inputs:**
  - `cluster_name_or_id` *(string, required)*: Cluster name or UUID.
  - `name` *(string, required)*: Unique name for the group.
  - `description` *(string, optional)*: Purpose description.
  - `priority` *(float, optional)*: Scheduling priority (e.g. `1.0` - `5.0`).
  - `vm_positive` *(bool, optional, default: True)*: Positive VM affinity (`True`, run together) or anti-affinity (`False`, run on separate hypervisors).
  - `vm_enforcing` *(bool, optional, default: False)*: Mandatory hard rule (`True`) vs. soft preference (`False`).
  - `vm_enabled` *(bool, optional, default: True)*: Enable/disable the VM rule.
  - `host_positive` *(bool, optional, default: True)*: Positive Host affinity (`True`, run on specified hosts) or negative (`False`, forbidden on specified hosts).
  - `host_enforcing` *(bool, optional, default: False)*: Mandatory host enforcement (`True`) vs soft preference (`False`).
  - `host_enabled` *(bool, optional, default: True)*: Enable/disable the Host rule.
  - `vms` *(list[str], optional)*: List of member VM names or UUIDs.
  - `hosts` *(list[str], optional)*: List of member Host names or UUIDs.
  - `vm_labels` *(list[str], optional)*: List of member VM Affinity Label names or UUIDs.
  - `host_labels` *(list[str], optional)*: List of member Host Affinity Label names or UUIDs.
- **Outputs:** `AffinityGroupResult`

---

### 60. `ovirt_cluster_affinity_group_update`

Updates rules, settings, or member lists of an existing Affinity Group.

- **Inputs:**
  - `cluster_name_or_id` *(string, required)*: Cluster name or UUID.
  - `group_name_or_id` *(string, required)*: Affinity group name or UUID.
  - `name` *(string, optional)*: Rename group.
  - `description` *(string, optional)*: Update description.
  - `priority` *(float, optional)*: Update priority.
  - `vm_positive` *(bool, optional)*: Update VM positive/anti-affinity rule.
  - `vm_enforcing` *(bool, optional)*: Update VM enforcement.
  - `host_positive` *(bool, optional)*: Update Host affinity rule.
  - `host_enforcing` *(bool, optional)*: Update Host enforcement.
  - `vms` *(list[str], optional)*: Replace complete list of member VMs.
  - `hosts` *(list[str], optional)*: Replace complete list of member Hosts.
  - `vm_labels` *(list[str], optional)*: Replace complete list of member VM labels.
  - `host_labels` *(list[str], optional)*: Replace complete list of member Host labels.
- **Outputs:** `AffinityGroupResult`

---

### 61. `ovirt_cluster_affinity_group_delete`

Deletes an Affinity Group from a cluster. Protected by safe-mode confirmation (`confirm=True`).

- **Inputs:**
  - `cluster_name_or_id` *(string, required)*: Cluster name or UUID.
  - `group_name_or_id` *(string, required)*: Affinity group name or UUID.
  - `confirm` *(bool, optional, default: False)*: Confirmation flag required in safe-mode.
- **Outputs:** `AffinityGroupResult`

---

### 62. `ovirt_host_network_attachment_list`

Lists all logical network attachments on a hypervisor host, resolving which oVirt network (e.g. `ovirtmgmt`) is attached to which physical NIC or bond (e.g. `eth0`), along with IPv4 assignment method, address, netmask, gateway, and in-sync status.

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Host name or UUID.
- **Outputs:** `list[HostNetworkAttachmentInfo]`
  - `id`: UUID of the attachment.
  - `network_name`: Logical network name.
  - `host_nic_name`: Physical NIC or bond name.
  - `boot_protocol`: `static`, `dhcp`, or `none`.
  - `ip_address`: Assigned IPv4 address.
  - `in_sync`: Boolean indicating whether host network settings match engine definitions.

---

### 63. `ovirt_host_iscsi_discover`

Discovers available iSCSI targets on a storage portal from the designated hypervisor host via OS kernel discovery.

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Host name or UUID.
  - `address` *(string, required)*: IP address or hostname of the iSCSI portal (e.g. `192.0.2.10`).
  - `port` *(int, optional, default: 3260)*: iSCSI portal port.
  - `username` *(string, optional)*: CHAP username.
  - `password` *(string, optional)*: CHAP password.
- **Outputs:** `HostIscsiDiscoverResult`
  - `targets`: List of discovered target IQN strings.
  - `count`: Total count of targets found.

---

### 64. `ovirt_host_iscsi_login`

Logs in to an iSCSI target portal from a hypervisor host, discovering LUN block devices (`/dev/mapper/...`).

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Host name or UUID.
  - `address` *(string, required)*: iSCSI portal IP or hostname.
  - `target` *(string, required)*: Target IQN to log in to.
  - `port` *(int, optional, default: 3260)*: Portal port.
  - `username` *(string, optional)*: CHAP username.
  - `password` *(string, optional)*: CHAP password.
- **Outputs:** `HostIscsiLoginResult`

---

### 65. `ovirt_host_network_sync`

Synchronizes out-of-sync network attachments on a hypervisor host with engine definitions, featuring automatic connectivity rollback protection (`check_connectivity=True`).

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Host name or UUID.
  - `network_attachment_id` *(string, optional)*: Specific attachment ID to synchronize. If omitted, synchronizes all out-of-sync attachments on the host.
- **Outputs:** `HostNetworkSetupResult`

---

### 66. `ovirt_storage_domain_list`

Lists all Storage Domains in oVirt / OLVM with capacity telemetry, storage protocols, format versions, and attached Data Centers.

- **Inputs:** None.
- **Outputs:** `list[StorageDomainSummary]`
  - `id`: UUID of the storage domain.
  - `name`: Domain name.
  - `type`: Domain role (`data`, `iso`, `export`, `image`).
  - `storage_type`: Protocol (`nfs`, `iscsi`, `fcp`, `glance`, `local`).
  - `status`: `active`, `maintenance`, `unattached`, or `inactive`.
  - `available_gb`: Free space in GB.
  - `used_gb`: Used space in GB.
  - `total_gb`: Total space in GB.
  - `usage_percent`: Utilization percentage.
  - `data_centers`: List of attached Data Center names.

---

### 67. `ovirt_storage_domain_get`

Retrieves deep telemetry, thresholds, and stored object counts (disks, templates, VMs) for a Storage Domain.

- **Inputs:**
  - `name_or_id` *(string, required)*: Storage domain name or UUID.
- **Outputs:** `StorageDomainDetail`
  - `disks_count`: Number of virtual disks stored.
  - `templates_count`: Number of VM templates stored.
  - `vms_count`: Number of VMs stored.
  - `supports_discard`: Boolean indicating TRIM / discard support.
  - `warning_low_space_indicator`: Low space threshold percentage.
  - `critical_space_action_blocker`: Critical blocking space threshold in GB.

---

### 68. `ovirt_storage_domain_create_nfs`

Creates a new NFS Storage Domain initialized via a designated hypervisor host.

- **Inputs:**
  - `name` *(string, required)*: Unique name for the storage domain.
  - `host_name_or_id` *(string, required)*: Hypervisor host responsible for initializing metadata.
  - `address` *(string, required)*: NFS server IP or hostname (e.g. `192.0.2.20`).
  - `path` *(string, required)*: NFS export path (e.g. `/exports/data`).
  - `domain_type` *(string, optional, default: 'data')*: `data`, `iso`, or `export`.
  - `nfs_version` *(string, optional, default: 'auto')*: `auto`, `v3`, `v4`, `v4_1`, `v4_2`.
  - `description` *(string, optional)*: Description.
- **Outputs:** `StorageDomainResult`

---

### 69. `ovirt_storage_domain_attach`

Attaches a Storage Domain to a Data Center.

- **Inputs:**
  - `storage_domain_name_or_id` *(string, required)*: Storage domain name or UUID.
  - `data_center_name_or_id` *(string, required)*: Target Data Center name or UUID.
- **Outputs:** `StorageDomainResult`

---

### 70. `ovirt_storage_domain_activate`

Activates an attached Storage Domain in a Data Center.

- **Inputs:**
  - `storage_domain_name_or_id` *(string, required)*: Storage domain name or UUID.
  - `data_center_name_or_id` *(string, required)*: Data Center name or UUID.
- **Outputs:** `StorageDomainResult`

---

### 71. `ovirt_storage_domain_maintenance`

Moves an attached Storage Domain to maintenance mode in a Data Center (deactivate), preparing it for safe detachment.

- **Inputs:**
  - `storage_domain_name_or_id` *(string, required)*: Storage domain name or UUID.
  - `data_center_name_or_id` *(string, required)*: Data Center name or UUID.
- **Outputs:** `StorageDomainResult`

---

### 72. `ovirt_storage_domain_detach`

Detaches a Storage Domain from a Data Center (symmetric, reversible counterpart of `ovirt_storage_domain_attach`). Domain must first be in maintenance mode.

- **Inputs:**
  - `storage_domain_name_or_id` *(string, required)*: Storage domain name or UUID.
  - `data_center_name_or_id` *(string, required)*: Data Center name or UUID.
- **Outputs:** `StorageDomainResult`

---

### 73. `ovirt_storage_domain_delete`

Deletes or unregisters a Storage Domain from oVirt / OLVM. Protected by safe-mode confirmation (`confirm=True`). If the domain is currently attached to an active Data Center, deletion is blocked by pre-flight guards to protect data integrity.

- **Inputs:**
  - `name_or_id` *(string, required)*: Storage domain name or UUID.
  - `host_name_or_id` *(string, optional)*: Hypervisor host executing the deletion/format.
  - `format` *(bool, optional, default: False)*: Whether to wipe/format storage metadata.
  - `confirm` *(bool, optional, default: False)*: Confirmation flag required in safe-mode.
- **Outputs:** `StorageDomainResult`

---

### 74. `ovirt_disk_move`

Moves a virtual disk to a different Storage Domain (Storage vMotion / offline disk migration). Safely migrates the underlying disk image between active storage domains.

- **Inputs:**
  - `disk_name_or_id` *(string, required)*: Name or UUID of the virtual disk to migrate.
  - `storage_domain_name_or_id` *(string, required)*: Target Storage Domain name or UUID.
  - `wait` *(bool, optional, default: True)*: Whether to synchronously block until migration completes.
  - `timeout` *(int, optional, default: 300)*: Maximum time in seconds to wait for migration.
- **Outputs:** `DiskOperationResult`

---

### 75. `ovirt_disk_copy`

Clones / copies a virtual disk to a target Storage Domain. Allows creating an independent copy with an optional new disk alias.

- **Inputs:**
  - `disk_name_or_id` *(string, required)*: Name or UUID of the virtual disk to clone.
  - `storage_domain_name_or_id` *(string, required)*: Target Storage Domain name or UUID.
  - `new_alias` *(string, optional)*: Optional new display name / alias for the copied disk.
  - `wait` *(bool, optional, default: True)*: Whether to synchronously block until copy completes.
  - `timeout` *(int, optional, default: 300)*: Maximum time in seconds to wait for copy.
- **Outputs:** `DiskOperationResult`

---

### 76. `ovirt_disk_sparsify`

Reclaims zeroed free space from a raw-formatted virtual disk (sparsification / hole punching). Compacts the disk image on the underlying storage domain.

- **Inputs:**
  - `disk_name_or_id` *(string, required)*: Name or UUID of the virtual disk to sparsify.
  - `wait` *(bool, optional, default: True)*: Whether to wait for sparsification to complete.
  - `timeout` *(int, optional, default: 300)*: Maximum wait time in seconds.
- **Outputs:** `DiskOperationResult`

---

### 77. `ovirt_template_list`

Lists all virtual machine templates and golden images in the virtualization environment, including the system Blank template, custom images, hardware specs (vCPU, RAM), and versioning.

- **Inputs:**
  - `search` *(string, optional)*: Filter query (e.g. `name=gold*`, `status=ok`).
- **Outputs:** `list[TemplateSummary]`

---

### 78. `ovirt_template_get`

Retrieves deep technical configuration and hardware profile of an oVirt / OLVM template, including attached disk references, NIC count, CPU topology, memory, and OS type.

- **Inputs:**
  - `name_or_id` *(string, required)*: Template name or UUID.
- **Outputs:** `TemplateDetail`

---

### 79. `ovirt_template_create_from_vm`

Creates a new reusable template / golden image from an existing virtual machine. The source virtual machine must be powered off (`down`) to snapshot disk images.

- **Inputs:**
  - `vm_name_or_id` *(string, required)*: Name or UUID of the source virtual machine.
  - `template_name` *(string, required)*: Name for the new template.
  - `description` *(string, optional)*: Optional descriptive text.
  - `wait` *(bool, optional, default: True)*: Whether to synchronously block until template provisioning finishes.
  - `timeout` *(int, optional, default: 300)*: Maximum wait time in seconds.
- **Outputs:** `TemplateResult`

---

### 80. `ovirt_template_delete`

Deletes an oVirt / OLVM template from the environment. Protected by safe-mode confirmation (`confirm=True`). The system Blank template is permanently protected from deletion by pre-flight guards.

- **Inputs:**
  - `name_or_id` *(string, required)*: Template name or UUID.
  - `confirm` *(bool, optional, default: False)*: Confirmation flag required in safe-mode.
  - `wait` *(bool, optional, default: True)*: Whether to synchronously block until removal completes.
  - `timeout` *(int, optional, default: 180)*: Maximum wait time in seconds.
- **Outputs:** `TemplateResult`

---

### 81. `ovirt_datacenter_list`

Lists all Data Centers in the virtualization environment, including status (`up`, `uninitialized`), storage type (`shared`, `local`), compatibility version, and quota mode.

- **Inputs:**
  - `search` *(string, optional)*: Filter query (e.g. `status=up`, `name=Home*`).
- **Outputs:** `list[DataCenterSummary]`

---

### 82. `ovirt_datacenter_get`

Retrieves complete technical specification of a Data Center, including attached clusters, attached Storage Domains, and defined logical networks.

- **Inputs:**
  - `name_or_id` *(string, required)*: Data Center name or UUID.
- **Outputs:** `DataCenterDetail`

---

### 83. `ovirt_quota_list`

Lists resource quotas defined across Data Centers or filtered by a specific Data Center.

- **Inputs:**
  - `data_center` *(string, optional)*: Data Center name or UUID filter.
- **Outputs:** `list[QuotaSummary]`

---

### 84. `ovirt_quota_get`

Retrieves detailed compute and storage limitations defined by a quota, including vCPU limits, memory limits, and storage domain space ceilings.

- **Inputs:**
  - `name_or_id` *(string, required)*: Quota name or UUID.
  - `data_center` *(string, optional)*: Data Center name or UUID scoping the search.
- **Outputs:** `QuotaDetail`

---

### 85. `ovirt_quota_create`

Creates a new resource quota under a designated Data Center.

- **Inputs:**
  - `name` *(string, required)*: Name for the new quota.
  - `data_center` *(string, required)*: Name or UUID of the parent Data Center.
  - `description` *(string, optional)*: Optional descriptive notes.
- **Outputs:** `QuotaResult`

---

### 86. `ovirt_quota_delete`

Deletes a resource quota from a Data Center. Protected by safe-mode confirmation (`confirm=True`). The system Default quota is protected by pre-flight guards.

- **Inputs:**
  - `name_or_id` *(string, required)*: Quota name or UUID.
  - `data_center` *(string, required)*: Name or UUID of the parent Data Center.
  - `confirm` *(bool, optional, default: False)*: Confirmation flag required in safe-mode.
- **Outputs:** `QuotaResult`

---

### 87. `ovirt_network_list`

Lists logical networks across Data Centers or filtered by Data Center, including 802.1Q VLAN encapsulation tag, MTU, and status.

- **Inputs:**
  - `data_center` *(string, optional)*: Data Center name or UUID filter.
- **Outputs:** `list[LogicalNetworkSummary]`

---

### 88. `ovirt_network_create`

Creates a new logical network in a Data Center with optional VLAN tagging and custom MTU (e.g. jumbo frames).

- **Inputs:**
  - `name` *(string, required)*: Name for the logical network.
  - `data_center` *(string, required)*: Name or UUID of the parent Data Center.
  - `vlan_id` *(int, optional)*: Optional 802.1Q VLAN encapsulation tag (1-4094).
  - `mtu` *(int, optional)*: Optional MTU payload size (e.g. 1500, 9000).
  - `description` *(string, optional)*: Optional descriptive notes.
- **Outputs:** `LogicalNetworkResult`

---

### 89. `ovirt_network_delete`

Deletes a logical network from a Data Center. Protected by safe-mode confirmation (`confirm=True`). The default management network `ovirtmgmt` is permanently protected from deletion.

- **Inputs:**
  - `name_or_id` *(string, required)*: Network name or UUID.
  - `data_center` *(string, optional)*: Data Center name or UUID scoping the search.
  - `confirm` *(bool, optional, default: False)*: Confirmation flag required in safe-mode.
- **Outputs:** `LogicalNetworkResult`

---

### 90. `ovirt_tag_list`

Lists hierarchical inventory tags in the oVirt / OLVM virtualization environment, including tag UUID, display name, description, and parent link.

- **Inputs:**
  - `search` *(string, optional)*: Optional search query.
- **Outputs:** `list[TagSummary]`

---

### 91. `ovirt_tag_create`

Creates a new inventory tag in oVirt / OLVM with optional parent hierarchical nesting.

- **Inputs:**
  - `name` *(string, required)*: Name for the new tag.
  - `description` *(string, optional)*: Optional descriptive text.
  - `parent` *(string, optional)*: Optional parent tag name or UUID for hierarchical nesting.
- **Outputs:** `TagResult`

---

### 92. `ovirt_tag_delete`

Deletes an inventory tag from oVirt / OLVM. Protected by safe-mode confirmation (`confirm=True`). The system root tag is protected from removal.

- **Inputs:**
  - `name_or_id` *(string, required)*: Tag name or UUID.
  - `confirm` *(bool, optional, default: False)*: Confirmation flag required in safe-mode.
- **Outputs:** `TagResult`

---

### 93. `ovirt_vm_tag_assign`

Assigns an inventory tag to a virtual machine.

- **Inputs:**
  - `vm_name_or_id` *(string, required)*: Virtual machine name or UUID.
  - `tag_name_or_id` *(string, required)*: Tag name or UUID.
- **Outputs:** `TagAssignmentResult`

---

### 94. `ovirt_vm_tag_unassign`

Unassigns an inventory tag from a virtual machine.

- **Inputs:**
  - `vm_name_or_id` *(string, required)*: Virtual machine name or UUID.
  - `tag_name_or_id` *(string, required)*: Tag name or UUID.
- **Outputs:** `TagAssignmentResult`

---

### 95. `ovirt_host_tag_assign`

Assigns an inventory tag to a hypervisor host.

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Hypervisor host name or UUID.
  - `tag_name_or_id` *(string, required)*: Tag name or UUID.
- **Outputs:** `TagAssignmentResult`

---

### 96. `ovirt_host_tag_unassign`

Unassigns an inventory tag from a hypervisor host.

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Hypervisor host name or UUID.
  - `tag_name_or_id` *(string, required)*: Tag name or UUID.
- **Outputs:** `TagAssignmentResult`

---

### 97. `ovirt_host_bond_create`

Creates a bonded network interface on a hypervisor host combining 2 or more physical interfaces. Supports active-backup, 802.3ad (LACP), balance-rr, and custom bond modes.

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Hypervisor host name or UUID.
  - `bond_name` *(string, required)*: Name for the bond device (e.g. `bond0`).
  - `slaves` *(list[string], required)*: Physical NIC slave names (e.g. `['eth1', 'eth2']`).
  - `mode` *(string, optional, default: 'active-backup')*: Bonding mode policy.
- **Outputs:** `HostBondResult`

---

### 98. `ovirt_host_bond_delete`

Deletes a network bond interface from a hypervisor host, releasing slave interfaces back to standalone mode. Protected by safe-mode confirmation (`confirm=True`).

- **Inputs:**
  - `host_name_or_id` *(string, required)*: Hypervisor host name or UUID.
  - `bond_name` *(string, required)*: Name of the bond to dismantle.
  - `confirm` *(bool, optional, default: False)*: Confirmation flag required in safe-mode.
- **Outputs:** `HostBondResult`

---

### 99. `ovirt_user_tag_list`

Lists inventory tags assigned to an oVirt / OLVM user.

- **Inputs:**
  - `user_name_or_id` *(string, required)*: Username or UUID of the user.
- **Outputs:** `list[TagSummary]`

---

### 100. `ovirt_user_tag_assign`

Assigns an inventory tag to an oVirt / OLVM user.

- **Inputs:**
  - `user_name_or_id` *(string, required)*: Username or UUID of the user.
  - `tag_name_or_id` *(string, required)*: Name or UUID of the inventory tag to assign.
- **Outputs:** `TagAssignmentResult`

---

### 101. `ovirt_user_tag_unassign`

Unassigns an inventory tag from an oVirt / OLVM user.

- **Inputs:**
  - `user_name_or_id` *(string, required)*: Username or UUID of the user.
  - `tag_name_or_id` *(string, required)*: Name or UUID of the inventory tag to unassign.
- **Outputs:** `TagAssignmentResult`

---

### 102. `ovirt_host_upgrade_check`

Checks if operating system or package updates are available for a hypervisor host. Triggers the oVirt / OLVM engine to query host package repositories via Ansible runner and updates the host's `update_available` flag.

> [!NOTE]
> Valid host statuses for upgrade check are `up` or `non_operational`. If called on a host in an unsupported state, the tool performs a pre-validation guard to guide the operator.

- **Inputs:**
  - `name_or_id` *(string, required)*: Display name or UUID of the hypervisor host.
- **Outputs (`HostUpgradeCheckResult`):**
  - `success`: Whether the check was initiated successfully.
  - `host_id`: Hypervisor host UUID.
  - `host_name`: Hypervisor host name.
  - `status`: Current host status (`up`, `non_operational`).
  - `update_available`: Boolean indicating whether updates are available.
  - `message`: Diagnostic outcome message.

---

### 103. `ovirt_host_upgrade`

Upgrades operating system packages and VDSM on a hypervisor host using the oVirt / OLVM host upgrade Ansible automation playbook.

> [!CAUTION]
> **Enterprise Safety Matrix ("Guard-Before-Act"):**
> 1. **Maintenance Gate:** The host **MUST be in `maintenance` status** before starting an upgrade. If the host is `up`, the operation is strictly rejected to ensure all running virtual machines have been migrated off the host first using `ovirt_host_maintenance`.
> 2. **Safe Mode Gate:** Modifying action in Safe Mode: requires `confirm=True` when `MCP_SAFE_MODE=true`.

- **Inputs:**
  - `name_or_id` *(string, required)*: Display name or UUID of the hypervisor host.
  - `reboot` *(bool, optional, default: True)*: Whether to automatically reboot the hypervisor after the upgrade completes.
  - `confirm` *(bool, optional, default: False)*: Confirmation flag required in safe mode (`MCP_SAFE_MODE=true`).
  - `async_` *(bool, optional, default: True)*: Whether to execute the upgrade playbook asynchronously via the engine runner.
  - `timeout_minutes` *(int, optional, default: 60)*: Maximum duration in minutes for the upgrade playbook execution.
- **Outputs (`HostUpgradeResult`):**
  - `success`: Whether the upgrade was initiated successfully.
  - `action`: `"upgrade"`.
  - `host_id`: Hypervisor host UUID.
  - `host_name`: Hypervisor host name.
  - `status`: Current host status (`"maintenance"`).
  - `reboot_requested`: Whether automatic post-upgrade reboot is requested.
  - `message`: Detailed execution status.

---

### 104. `ovirt_system_events`

Retrieves global audit log events, errors, warnings, alerts, and operational messages across the entire virtualization environment (hosts, VMs, storage domains, clusters). Supports filtering by severity level (`'alert'`, `'error'`, `'warning'`, `'normal'`), custom search queries, and pagination with `max_events` and `from_event_id`.

- **Inputs:**
  - `max_events` *(int, optional, default: 50)*: Maximum number of events to return (1 to 500).
  - `severity` *(string, optional)*: Filter by severity level (`'normal'`, `'warning'`, `'error'`, `'alert'`).
  - `search` *(string, optional)*: Custom oVirt search expression (e.g. `'type = ...'`, keywords, or entity filters).
  - `from_event_id` *(int, optional)*: Sequence event ID to fetch events starting after this event.
- **Outputs:** `list[SystemEvent]`
  - `id`: Unique event sequence ID.
  - `code`: Internal numeric event code.
  - `severity`: Severity level (`normal`, `warning`, `error`, `alert`).
  - `time`: Timestamp when the event occurred in ISO format.
  - `description`: Human-readable audit message or diagnostic explanation.
  - `vm_name`: Affected virtual machine name, if applicable.
  - `host_name`: Affected hypervisor host name, if applicable.
  - `cluster_name`: Affected cluster name, if applicable.
  - `storage_domain_name`: Affected storage domain name, if applicable.
  - `user_name`: Username who initiated or triggered the action, if applicable.
  - `correlation_id`: Operation tracking correlation identifier.

**Example Output:**
```json
[
  {
    "id": "3904",
    "code": 30,
    "severity": "normal",
    "time": "2026-11-19 10:34:10.135000+00:00",
    "description": "User admin@internal logged in from 192.0.2.20.",
    "vm_name": null,
    "host_name": null,
    "cluster_name": null,
    "storage_domain_name": null,
    "user_name": "admin@internal",
    "correlation_id": null
  },
  {
    "id": "3903",
    "code": 9920,
    "severity": "alert",
    "time": "2026-11-19 07:04:40.561000+00:00",
    "description": "There is no full backup available, please run engine-backup to prevent data loss.",
    "vm_name": null,
    "host_name": null,
    "cluster_name": null,
    "storage_domain_name": null,
    "user_name": null,
    "correlation_id": null
  }
]
```

---

### 105. `ovirt_user_list`

Lists user accounts registered in oVirt / OLVM across all authorization domains (e.g. `internal-authz`, Active Directory, LDAP, Keycloak). Supports filtering via standard oVirt search query expressions and pagination limits.

- **Inputs:**
  - `search` *(string, optional)*: oVirt search query expression (e.g. `'usrname = admin*'`).
  - `max_results` *(int, optional, default: 100)*: Maximum number of users to retrieve.
- **Outputs:** `list[UserSummary]`
  - `id`: Unique UUID of the user.
  - `name`: Display name or username.
  - `user_name`: Full username including realm / domain (e.g. `'admin@internal-authz'`).
  - `principal`: Principal username without realm (e.g. `'admin'`).
  - `domain_name`: Authorization domain name (e.g. `'internal-authz'`).
  - `email`: User email address, if configured.
  - `department`: Department name, if configured.
  - `logged_in`: Whether the user is currently authenticated and active.

**Example Output:**
```json
[
  {
    "id": "05ff7a22-d131-11f0-a587-00505691ee8b",
    "name": "admin",
    "user_name": "admin@internal-authz",
    "principal": "admin",
    "domain_name": "internal-authz",
    "email": "admin@example.com",
    "department": null,
    "logged_in": true
  }
]
```

---

### 106. `ovirt_user_get`

Retrieves comprehensive account information for a specific user, including assigned authorization roles and total discrete permission grants count.

- **Inputs:**
  - `name_or_id` *(string, required)*: Username (e.g. `'admin@internal-authz'`) or user UUID.
- **Outputs:** `UserDetail` (inherits from `UserSummary`)
  - `roles`: List of authorization role names assigned to this user (e.g. `['SuperUser', 'UserProfileEditor']`).
  - `permissions_count`: Total number of discrete permission grants for this user.

**Example Output:**
```json
{
  "id": "05ff7a22-d131-11f0-a587-00505691ee8b",
  "name": "admin",
  "user_name": "admin@internal-authz",
  "principal": "admin",
  "domain_name": "internal-authz",
  "email": "admin@example.com",
  "department": null,
  "logged_in": true,
  "roles": ["SuperUser", "UserProfileEditor"],
  "permissions_count": 19
}
```

---

### 107. `ovirt_user_add`

Imports and registers a user from an external or internal authorization provider / directory service (e.g. `internal-authz`, LDAP, Active Directory, Keycloak) into the virtualization engine.

> **Enterprise Best Practice:** Use this tool to provision dedicated, least-privilege MCP service accounts (e.g. `'mcp-service@internal-authz'`) rather than operating under unrestricted root administrator credentials.

- **Inputs:**
  - `user_name` *(string, required)*: Username in the authorization directory (e.g. `'mcp-service'` or `'mcp-service@internal-authz'`).
  - `domain` *(string, required)*: Authorization domain or realm name (e.g. `'internal-authz'`).
  - `principal` *(string, optional)*: Principal username without realm for Active Directory / UPN compatibility.
- **Outputs:** `UserResult`
  - `success`: `true` if imported successfully.
  - `action`: `"add"`.
  - `user_id`: UUID assigned to the registered user.
  - `user_name`: Full normalized username.
  - `message`: Outcome description.

**Example Output:**
```json
{
  "success": true,
  "action": "add",
  "user_id": "7a3e8110-3841-4cfa-9311-53e34b12aa01",
  "user_name": "mcp-service@internal-authz",
  "message": "User 'mcp-service@internal-authz' successfully registered into oVirt from domain 'internal-authz'."
}
```

---

### 108. `ovirt_user_delete`

De-registers and removes a user account from the oVirt / OLVM virtualization engine.

> **Safety & Lockout Guards:**
> 1. **Safe Mode Enforcement:** Requires `confirm=True` when `MCP_SAFE_MODE=true`.
> 2. **Lockout Protection:** Deleting primary administrator accounts (`admin@*`) is strictly blocked to prevent operator lockout from the virtualization management engine.

- **Inputs:**
  - `name_or_id` *(string, required)*: Username or UUID of the user account to remove.
  - `confirm` *(bool, optional, default: false)*: Explicit confirmation required in Safe Mode.
- **Outputs:** `UserResult`
  - `success`: `true` if removed.
  - `action`: `"delete"`.
  - `user_id`: UUID of the deleted user.
  - `user_name`: Full username.
  - `message`: Outcome description.

**Example Output:**
```json
{
  "success": true,
  "action": "delete",
  "user_id": "7a3e8110-3841-4cfa-9311-53e34b12aa01",
  "user_name": "temp-user@internal-authz",
  "message": "User 'temp-user@internal-authz' successfully removed from oVirt engine."
}
```

---

### 109. `ovirt_role_list`

Lists authorization roles defined in the system (e.g. `SuperUser`, `DataCenterAdmin`, `ClusterAdmin`, `UserRole`, `PowerUserRole`). Allows filtering for administrative roles only or standard user roles only.

- **Inputs:**
  - `administrative` *(bool, optional)*: When `true`, returns only administrative roles; when `false`, returns only user roles; when omitted, returns all roles.
- **Outputs:** `list[RoleSummary]`
  - `id`: Role UUID.
  - `name`: Role name.
  - `description`: Human-readable summary of permissions.
  - `administrative`: `true` if administrative privilege.
  - `mutable`: Whether role permits can be modified in engine.

**Example Output:**
```json
[
  {
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "SuperUser",
    "description": "Roles management administrator",
    "administrative": true,
    "mutable": false
  },
  {
    "id": "00000000-0000-0000-0001-000000000001",
    "name": "UserRole",
    "description": "User Role",
    "administrative": false,
    "mutable": false
  }
]
```

---

### 110. `ovirt_permission_list`

Lists authorization permission grants across the virtualization environment. Supports filtering by specific target user or role to inspect the current privilege topology.

- **Inputs:**
  - `user_name_or_id` *(string, optional)*: Filter permissions assigned to a specific user.
  - `role_name_or_id` *(string, optional)*: Filter permissions for a specific role.
- **Outputs:** `list[PermissionSummary]`
  - `id`: Permission grant UUID.
  - `user_id`: Target user UUID.
  - `user_name`: Target user name.
  - `role_id`: Role UUID.
  - `role_name`: Role name.
  - `target_type`: Target entity type (`system`, `data_center`, `cluster`, `vm`, `storage_domain`).
  - `target_id`: Target entity UUID (null for system-wide).
  - `target_name`: Target entity display name (null for system-wide).

**Example Output:**
```json
[
  {
    "id": "583901b2-1029-4d22-94ea-62881234abcd",
    "user_id": "05ff7a22-d131-11f0-a587-00505691ee8b",
    "user_name": "admin@internal-authz",
    "role_id": "00000000-0000-0000-0000-000000000001",
    "role_name": "SuperUser",
    "target_type": "system",
    "target_id": null,
    "target_name": null
  }
]
```

---

### 111. `ovirt_permission_add`

Grants an authorization role to a user on a target entity or system-wide.

> **Enterprise Security Matrix:** Granting high-privilege administrative roles (`SuperUser`, `DataCenterAdmin`, `ClusterAdmin`) modifies the hypervisor security posture and requires `confirm=True` in Safe Mode.

- **Inputs:**
  - `user_name_or_id` *(string, required)*: Username or UUID of the recipient user.
  - `role_name_or_id` *(string, required)*: Role name (e.g. `'PowerUserRole'`, `'UserRole'`, `'SuperUser'`) or UUID.
  - `target_type` *(string, optional, default: 'system')*: Target entity type: `'system'`, `'data_center'`, `'cluster'`, `'vm'`, or `'storage_domain'`.
  - `target_name_or_id` *(string, optional)*: Target entity name or UUID (required when `target_type != 'system'`).
  - `confirm` *(bool, optional, default: false)*: Confirmation flag required in Safe Mode when assigning administrative roles.
- **Outputs:** `PermissionResult`
  - `success`: `true` if granted.
  - `action`: `"add"`.
  - `permission_id`: UUID of the newly granted permission.
  - `user_name`: Target username.
  - `role_name`: Granted role name.
  - `target_type`: Entity type.
  - `target_name`: Target entity name.
  - `message`: Outcome description.

**Example Output:**
```json
{
  "success": true,
  "action": "add",
  "permission_id": "bb401290-7819-4821-b012-990011223344",
  "user_name": "mcp-service@internal-authz",
  "role_name": "PowerUserRole",
  "target_type": "vm",
  "target_name": "testvm001",
  "message": "Role 'PowerUserRole' successfully granted to user 'mcp-service@internal-authz' on vm 'testvm001'."
}
```

---

### 112. `ovirt_permission_remove`

Revokes and removes an authorization permission grant from oVirt / OLVM by its permission UUID.

> **Safe Mode Protection:** Revoking permissions is a destructive security action and requires `confirm=True` in Safe Mode.

- **Inputs:**
  - `permission_id` *(string, required)*: UUID of the permission grant to revoke.
  - `confirm` *(bool, optional, default: false)*: Confirmation flag required in Safe Mode.
- **Outputs:** `PermissionResult`
  - `success`: `true` if revoked.
  - `action`: `"remove"`.
  - `permission_id`: Revoked permission UUID.
  - `user_name`: Username affected.
  - `role_name`: Revoked role name.
  - `message`: Outcome description.

**Example Output:**
```json
{
  "success": true,
  "action": "remove",
  "permission_id": "bb401290-7819-4821-b012-990011223344",
  "user_name": "mcp-service@internal-authz",
  "role_name": "PowerUserRole",
  "target_type": "unknown",
  "target_name": null,
  "message": "Permission grant 'bb401290-7819-4821-b012-990011223344' (role: 'PowerUserRole', user: 'mcp-service@internal-authz') successfully revoked."
}
```

---

## Connecting to AI MCP Clients

`ovirt-mcp` supports two primary deployment models:
1. **Local Desktop Mode (`stdio`):** Claude Desktop launches the server on-demand on your local machine (via Docker or Python venv).
2. **24/7 Network Daemon Mode (`sse`):** The server runs continuously in background (on a home server, NAS, Proxmox, or cloud VM) as a classic Docker container. Any AI client (Claude Desktop, Cursor, LibreChat) connects over HTTP via Server-Sent Events (`/sse`).

---

### Method 1: Docker Desktop for Claude (Zero-Install Setup)

No Python, C compiler, or virtual environment required on your workstation!

#### Step 1: Build the Docker Image
```bash
git clone https://github.com/gerilab/ovirt-mcp.git
cd ovirt-mcp
docker build -t ovirt-mcp .
```

#### Step 2: Configure Claude Desktop
Locate your configuration file:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add the `ovirt` server configuration:
```json
{
  "mcpServers": {
    "ovirt": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e", "OVIRT_URL=https://olvm-engine.example.com/ovirt-engine/api",
        "-e", "OVIRT_USERNAME=admin@internal",
        "-e", "OVIRT_PASSWORD=YourSecurePasswordHere",
        "-e", "OVIRT_INSECURE=true",
        "-e", "MCP_COMPACT_MODE=true",
        "ovirt-mcp"
      ]
    }
  }
}
```
Restart Claude Desktop. The hammer icon will show all 112 oVirt tools loaded!

---

### Method 2: Classic 24/7 Docker Container (Network SSE Daemon)

Run `ovirt-mcp` continuously in background on a central server (e.g. Proxmox LXC/VM, TrueNAS, unRAID, or dedicated Linux server). Multiple team members and AI clients connect to the shared instance over LAN without installing Docker on their local laptops.

#### Step 1: Start with Docker Compose
Clone the repository and copy the environment template:
```bash
git clone https://github.com/gerilab/ovirt-mcp.git
cd ovirt-mcp
cp .env.example .env
```

Edit `.env` with your engine credentials:
```env
OVIRT_URL=https://olvm-engine.example.com/ovirt-engine/api
OVIRT_USERNAME=admin@internal
OVIRT_PASSWORD=YourSecurePasswordHere
OVIRT_INSECURE=true
MCP_TRANSPORT=sse
MCP_PORT=8000
```

Start the daemon in background:
```bash
docker compose up -d
```

*(Alternatively, without docker-compose)*:
```bash
docker run -d \
  --name ovirt-mcp \
  --restart unless-stopped \
  -p 8000:8000 \
  -e OVIRT_URL="https://olvm-engine.example.com/ovirt-engine/api" \
  -e OVIRT_USERNAME="admin@internal" \
  -e OVIRT_PASSWORD="YourSecurePasswordHere" \
  -e OVIRT_INSECURE="true" \
  -e MCP_TRANSPORT="sse" \
  -e MCP_HOST="0.0.0.0" \
  -e MCP_PORT="8000" \
  ovirt-mcp
```

#### Step 2: Check Logs and Health
```bash
docker logs -f ovirt-mcp
```
Output confirms:
```text
INFO - Starting oVirt/OLVM MCP server in network daemon mode (transport='sse', bind='0.0.0.0:8000')...
```

#### Step 3: Connect AI Clients via Network URL
Configure Claude Desktop or Cursor on any computer on your network:
```json
{
  "mcpServers": {
    "ovirt": {
      "url": "http://192.0.2.10:8000/sse"
    }
  }
}
```
*(Replace `192.0.2.10` with your central server's IP address).*

---

### Method 3: Native Python Virtual Environment

If you prefer running directly on your host operating system without Docker:

```bash
cd /automation/mcp/ovirt-mcp
source .venv/bin/activate
ovirt-mcp
```

Configure Claude Desktop:
```json
{
  "mcpServers": {
    "ovirt": {
      "command": "/automation/mcp/ovirt-mcp/.venv/bin/ovirt-mcp",
      "env": {
        "OVIRT_URL": "https://olvm-engine.example.com/ovirt-engine/api",
        "OVIRT_USERNAME": "admin@internal",
        "OVIRT_PASSWORD": "YourSecurePasswordHere",
        "OVIRT_INSECURE": "true",
        "MCP_COMPACT_MODE": "true"
      }
    }
  }
}
```

---

## Testing & Quality Verification

### Run the Interactive Live Diagnostic Runner

Verify your live oVirt/OLVM engine connection and test all tools against real hypervisor infrastructure:

```bash
python scripts/test_live_olvm.py
```

### Run Automated Unit Tests

Unit tests execute without needing access to a live engine using mocked SDK interfaces:

```bash
pytest -v tests/unit
```

### Code Formatting and Strict Type Checking

All code follows strict Python typing and Ruff linting standards:

```bash
# Code formatting and linting
ruff check src tests scripts --fix
ruff format src tests scripts

# Strict static type analysis
mypy src tests
```

---

## Troubleshooting & FAQ

### 1. `No valid profile found in credentials`
- **Cause:** oVirt and OLVM require an AAA authentication profile suffix.
- **Solution:** Specify the full account format in `OVIRT_USERNAME`. For the default local admin, use `admin@internal`. For internal domain accounts, use `user@internal`.

### 2. `Invalid user credentials`
- **Cause:** Incorrect password or mismatched profile.
- **Solution:** Verify the password in the engine web administration portal. Ensure the username matches the profile shown on the login screen.

### 3. `Failed to build ovirt-engine-sdk-python: curl/curl.h: No such file or directory`
- **Cause:** Missing native C development headers for `libcurl` or `libxml2`.
- **Solution:**
  - Ubuntu/Debian: `sudo apt install -y libcurl4-openssl-dev libxml2-dev gcc`
  - RHEL/Oracle Linux: `sudo dnf install -y libcurl-devel libxml2-devel gcc`

### 4. `Operation blocked: Server is in READ-ONLY mode`
- **Cause:** An action was attempted that would alter hypervisor state while `MCP_READ_ONLY=true`.
- **Solution:** If mutations are intended, set `MCP_READ_ONLY=false` in `.env`.

### 5. `Operation requires confirmation in Safe Mode`
- **Cause:** Destructive actions (like shutting down a VM) require confirmation.
- **Solution:** Supply `confirm=True` as a tool argument.

---

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
