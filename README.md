# ovirt-mcp: Virtualization Manager for AI Agents

Modern, production-grade Model Context Protocol (MCP) server for **Oracle Linux Virtualization Manager (OLVM)** and **oVirt** hypervisor engines. 

`ovirt-mcp` connects LLMs (Claude, GPT, Llama, Mistral, Ollama) directly to your virtualization infrastructure with token-optimized responses, deep hardware inspection, audit trails, and multi-layered safety controls.

---

## Table of Contents

1. [Features](#features)
2. [Prerequisites & System Packages](#prerequisites--system-packages)
3. [Step-by-Step Installation Guide](#step-by-step-installation-guide)
4. [Configuration Reference (`.env` & `mcp.json`)](#configuration-reference-env--mcpjson)
   - [Method A: Using a `.env` File (File-based)](#method-a-using-a-env-file-file-based)
   - [Method B: Direct `mcp.json` (`env` Block - Zero `.env`)](#method-b-direct-mcpjson-env-block---zero-env)
   - [Configuration Options Breakdown](#configuration-options-breakdown)
   - [Authentication & AAA Profiles](#authentication--aaa-profiles-crucial)
   - [Three-Tier Access & Safety Architecture](#three-tier-access--safety-architecture)
   - [Service Account Provisioning Best Practices](#service-account-provisioning-best-practices)
   - [TLS & SSL Certificate Management](#tls--ssl-certificate-management)
5. [Operational Modes](#operational-modes)
   - [Compact vs. Detailed Mode (Token Optimization)](#compact-vs-detailed-mode-token-optimization)
   - [Safe Mode & Mutation Confirmation (Tier 3)](#safe-mode--mutation-confirmation-tier-3)
   - [Read-Only Enforcement (Tier 2)](#read-only-enforcement-tier-2)
   - [Hierarchical Naming Convention](#hierarchical-naming-convention)
6. [Tool Catalog & Overview](#tool-catalog--overview)
   - [Complete Tool Catalog (TOOLS.md)](TOOLS.md)
   - [Resource Domains Summary](#resource-domains-summary)
   - [Enterprise Telemetry & Observability Highlights](#enterprise-telemetry--observability-highlights)
7. [Connecting to AI MCP Clients](#connecting-to-ai-mcp-clients)
   - [Method 1: Docker Desktop for Claude (Zero-Install Setup)](#method-1-docker-desktop-for-claude-zero-install-setup)
   - [Method 2: Classic 24/7 Docker Container (Network SSE Daemon)](#method-2-classic-247-docker-container-network-sse-daemon)
   - [Method 3: Native Python Virtual Environment (Linux & macOS)](#method-3-native-python-virtual-environment-linux--macos)
   - [Method 4: Windows Desktop & IDE Setup (Step-by-Step for Windows)](#method-4-windows-desktop--ide-setup-step-by-step-for-windows)
   - [Method 5: Remote Linux Jumpbox via SSH (VS Code Remote - SSH)](#method-5-remote-linux-jumpbox-via-ssh-vs-code-remote---ssh)
   - [Method 6: Kiro IDE on Remote Linux (via SSH)](#method-6-kiro-ide-on-remote-linux-via-ssh)
8. [Testing & Quality Verification](#testing--quality-verification)
9. [Troubleshooting & FAQ](#troubleshooting--faq)
10. [Version History & Changelog](CHANGELOG.md)

---

## Features

- **Fast Inventory (`ovirt_vm_list`):** Query VMs across clusters with RAM, vCPU, IP addresses, cluster, host, and HA status in milliseconds.
- **Deep Hardware & Policy Inspection (`ovirt_vm_get`):** Access detailed CPU topology, memory ballooning ceilings, NUMA/IO threads, VirtIO-SCSI multi-queue, affinity groups, affinity labels, BIOS/TPM settings, thin-provisioned disk sizes (actual vs. provisioned), and vNIC bindings.
- **Dual Response Modes (Compact vs. Detailed):**
  - **Compact Mode:** ~90 tokens per VM (up to **86% token savings**), ideal for local and small context window models (Ollama, Mistral 7B, Llama 3 8B).
  - **Detailed Mode:** Comprehensive enterprise topology (~650 tokens per VM) for complex engineering tasks with frontier LLMs.
- **Audit Log Inspection (`ovirt_vm_events`):** Filter and analyze engine lifecycle events, warnings, failure reasons, and admin actions.
- **Real-Time Storage & Disk I/O Telemetry (`ovirt_vm_get`, `ovirt_disk_list`):** Per-disk live read/write throughput (bytes/s), read/write IOPS, and read/write latency.
- **Storage Domain Health & Overcommitment Analysis (`ovirt_storage_domain_get`):** Capacity health status (`healthy`, `warning`, `critical`, `overcommitted`), free space ratios, thin-provisioning overcommit ratios, aggregated domain IOPS, top I/O disks, and hosted VM workload mapping.
- **Asynchronous Job & Step Tracking (`ovirt_job_list`, `ovirt_job_get`):** Monitor background tasks, live migrations, disk moves, and snapshot tasks with step-by-step execution phases and progress percentages (0-100%).
- **Audit Entity Correlation (`ovirt_system_events`):** Direct correlation of audit log entries with target UUIDs (`vm_id`, `host_id`, `cluster_id`, `storage_domain_id`) for immediate deep investigation.
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

## Configuration Reference (`.env` & `mcp.json`)

`ovirt-mcp` provides two flexible, production-ready configuration methods to fit different workflows:

1. **[Method A: Using a `.env` File (File-based)](#method-a-using-a-env-file-file-based):** Preferred for background daemons, Docker Compose, automated command-line scripts, or developers who keep their credentials in a standalone file.
2. **[Method B: Direct `mcp.json` (`env` Block - Zero `.env`)](#method-b-direct-mcpjson-env-block---zero-env):** Preferred for AI IDE extensions (VS Code, Cline, Roo Code, Claude Desktop, Cursor), where all credentials and policies are encapsulated directly inside the MCP client settings without maintaining a `.env` file on disk.

Both methods support the exact same configuration parameters. If both are present, variables passed in the client process environment (Method B) override the `.env` file (Method A).

---

### Method A: Using a `.env` File (File-based)

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

---

### Method B: Direct `mcp.json` (`env` Block - Zero `.env`)

If you prefer keeping your entire setup inside your AI client configuration without creating or managing a separate `.env` file, populate the `"env"` block directly in your `mcp.json`:

```json
{
  "mcpServers": {
    "ovirt": {
      "command": "ovirt-mcp",
      "args": [],
      "env": {
        "OVIRT_URL": "https://olvm-engine.example.com/ovirt-engine/api",
        "OVIRT_USERNAME": "mcp-service@internal-authz",
        "OVIRT_PASSWORD": "YourSecurePasswordHere",
        "OVIRT_INSECURE": "true",
        "OVIRT_AUTO_DOWNLOAD_CA": "true",
        "MCP_COMPACT_MODE": "true",
        "MCP_SAFE_MODE": "true",
        "MCP_READ_ONLY": "false",
        "OVIRT_TIMEOUT": "30",
        "OVIRT_MAX_RETRIES": "3",
        "MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

> [!TIP]
> When using Method B, `ovirt-mcp` does not require a `.env` file to exist on disk. Pydantic Settings automatically reads all configuration parameters from the environment variables injected into the process by your MCP client.

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

### Three-Tier Access & Safety Architecture

To avoid security pitfalls and clarify how permissions interact between the oVirt/OLVM hypervisor and the MCP server, `ovirt-mcp` implements a strict **Three-Tier Security Architecture**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│  Tier 1: oVirt / OLVM Engine AAA Role Permissions (Engine-Level Floor) │
│  • ReadOnlyAdmin: Physically blocks ALL mutations (HTTP 403 Forbidden).│
│  • Operational/Admin Roles: Allow specific mutations within role scope.│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│  Tier 2: MCP Server Mode Gate (MCP_READ_ONLY in .env)                  │
│  • true:  Locally aborts all mutating tools before network calls.      │
│  • false: Allows tool calls to proceed to confirmation check.          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│  Tier 3: Safe Mode Gate & Confirmation (MCP_SAFE_MODE + confirm=True)  │
│  • true (default): Mutating/destructive actions require confirm=True.  │
│  • If confirm=False/missing: Operation is safely rejected with prompt. │
└────────────────────────────────────────────────────────────────────────┘
```

#### How the Tiers Interact (The Access Decision Matrix)

| Operational Scenario | oVirt / OLVM AAA Role | `MCP_READ_ONLY` | `MCP_SAFE_MODE` | Runtime Behavior |
|---|---|---|---|---|
| **Read-Only Monitoring (Recommended for Read-Only Agents)** | `ReadOnlyAdmin` | `true` (or `false`) | Any | **No mutations possible.** If `MCP_READ_ONLY=true`, blocked locally. Even if `MCP_READ_ONLY=false`, oVirt engine physically rejects any write with HTTP 403 Forbidden. |
| **Operational Automation (Recommended Standard)** | `UserVmManager` / `ClusterAdmin` | `false` | `true` (default) | **Safe controlled execution.** AI agents can perform allowed mutations (start, stop, snapshot, disk resize), but *must* provide `confirm=True` for each mutating call. |
| **Emergency Lock / Maintenance Freeze** | Any operational role | `true` | Any | **Instant client-side freeze.** All agent mutations are blocked immediately at the MCP layer without changing user accounts or roles in oVirt. |
| **Autonomous Pipeline (CI/CD / Headless Scripts)** | Scoped custom role | `false` | `false` | **Direct execution without prompts.** AI agents can execute mutations without passing `confirm=True`. *(Use with strict caution and scoped roles).* |

> [!IMPORTANT]
> **Understanding the Role vs. MCP Flag Distinction:**
> - If you assign `ReadOnlyAdmin` to the service account in oVirt, the account **cannot modify anything**, regardless of any `.env` setting or `confirm=True`. oVirt engine enforces this physically.
> - If you want the agent to manage VMs (start, stop, reboot, snapshots), the service account **must have an operational role** in oVirt (e.g. `UserVmManager`, `PowerUserRole`, or a custom scoped role).
> - Having an operational role in oVirt does **not** give the AI agent free rein: you still control safety locally via `MCP_READ_ONLY=true/false` and `MCP_SAFE_MODE=true` (requiring `confirm=True`).

---

### Service Account Provisioning Best Practices

For production environments, **do not use full administrative superuser credentials (`admin@internal`)**. Provision a dedicated service account for your AI agents:

1. **For Monitoring-Only Agents:**
   - Register the user:
     ```text
     ovirt_user_add(user_name="mcp-monitor", domain="internal-authz")
     ```
   - Assign the `ReadOnlyAdmin` role:
     ```text
     ovirt_permission_add(user_name_or_id="mcp-monitor@internal-authz", role_name_or_id="ReadOnlyAdmin", target_type="system")
     ```
   - In `.env`: set `OVIRT_USERNAME=mcp-monitor@internal-authz` and `MCP_READ_ONLY=true`.

2. **For Operational VM Management Agents:**
   - Register the user:
     ```text
     ovirt_user_add(user_name="mcp-operator", domain="internal-authz")
     ```
   - Assign scoped operational role (e.g. `UserVmManager` scoped to a specific cluster or datacenter):
     ```text
     ovirt_permission_add(user_name_or_id="mcp-operator@internal-authz", role_name_or_id="UserVmManager", target_type="cluster", target_name_or_id="DefaultCluster")
     ```
   - In `.env`: set `OVIRT_USERNAME=mcp-operator@internal-authz`, `MCP_READ_ONLY=false`, and `MCP_SAFE_MODE=true`.

3. **Via oVirt / OLVM Administration Web Portal:**
   - Navigate to **Administration** &rarr; **Configure** &rarr; **Roles**.
   - For read-only monitoring: Assign `ReadOnlyAdmin` to `mcp-service@internal-authz`.
   - For VM operations: Assign `UserVmManager` or `UserVmRunTimePermissions` scoped to the designated Cluster or Data Center.

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

### Safe Mode & Mutation Confirmation (Tier 3)

To prevent accidental hypervisor outages from hallucinatory or unintended agent actions:
1. When `MCP_SAFE_MODE=true` (the default) and `MCP_READ_ONLY=false`, mutating operations strictly require an explicit `confirm=True` parameter.
2. If `confirm=True` is omitted or set to `False`, the server raises `OvirtValidationError` with a detailed description of the pending mutation, prompting the human operator or supervisory agent to confirm.
3. If `MCP_READ_ONLY=true` is set, the operation is blocked immediately with `OvirtPermissionError` (Tier 2), even if `confirm=True` is provided.

### Read-Only Enforcement (Tier 2)

When `MCP_READ_ONLY=true` is set:
- Any action that attempts to modify engine state (stopping VMs, reboots, disk manipulation, quota creation, etc.) is rejected immediately with `OvirtPermissionError: Operation prohibited: Server is operating in read-only mode (MCP_READ_ONLY=true)`.
- Rejections occur locally in the MCP process without transmitting any mutating API request to the hypervisor engine.

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
- **`ovirt_job_*`**: Asynchronous engine background tasks, execution sub-steps, and live progress monitoring (`list`, `get`).

---

## Tool Catalog & Overview

The server exposes **136 production-grade tools** structured into 17 logical resource domains, strictly adhering to the `ovirt_<domain>_[<subresource>_]<action>` naming pattern.

> 📘 **Exhaustive Documentation:** For the complete, parameter-by-parameter reference catalog, input/output schemas, safe mode constraints, and JSON response examples for every tool, see **[TOOLS.md](TOOLS.md)**.

### Resource Domains Summary

| # | Resource Domain | Tool Prefix | Tools Count | Scope & Primary Operations | Reference Link |
|---|-----------------|-------------|:-----------:|----------------------------|----------------|
| 1 | **Testing & Connectivity** | `ovirt_test_connection` | 1 | Engine connectivity validation, version & build metadata | [TOOLS.md#1](TOOLS.md#1-ovirt_test_connection) |
| 2 | **Virtual Machines & Compute** | `ovirt_vm_*` | 22 | VM inventory, lifecycle, live migration, CPU/NUMA pinning, snapshots, CD-ROM/ISO, graphics consoles, SPICE/VNC tickets, and real-time runtime telemetry | [TOOLS.md#2](TOOLS.md#2-ovirt_vm_list) |
| 3 | **Virtual Disks & ISO Media** | `ovirt_disk_*`, `ovirt_storage_iso_*` | 9 | Floating & attached virtual disk lifecycle, attachment, resizing, moving, copying, sparsify (TRIM), and ISO storage querying | [TOOLS.md#3](TOOLS.md#24-ovirt_storage_iso_list) |
| 4 | **Hypervisors & Hosts** | `ovirt_host_*` | 13 | Hypervisor node inventory, hardware metrics, CPU/memory stats, maintenance mode, host activation, power restart, host upgrades, NUMA nodes, physical NICs, devices, and storage connections | [TOOLS.md#4](TOOLS.md#41-ovirt_host_list) |
| 5 | **Affinity & Placement** | `ovirt_affinity_*`, `ovirt_cluster_affinity_*`, `ovirt_*_label_*` | 14 | Host & VM affinity labels, cluster affinity groups (positive/negative VM-VM and VM-Host rules, enforcing/soft policies), and entity label assignments | [TOOLS.md#5](TOOLS.md#54-ovirt_affinity_label_list) |
| 6 | **Host Networking & SAN** | `ovirt_host_network_*`, `ovirt_host_iscsi_*`, `ovirt_host_bond_*` | 6 | Host network attachments, network sync, iSCSI portal discovery and login, and bond interface configuration | [TOOLS.md#6](TOOLS.md#68-ovirt_host_network_attachment_list) |
| 7 | **Storage Domains** | `ovirt_storage_domain_*` | 8 | Storage domain inventory, NFS creation, activation, maintenance, detaching, deletion, space health, overcommitment ratios, domain IOPS, and workload mapping | [TOOLS.md#7](TOOLS.md#72-ovirt_storage_domain_list) |
| 8 | **Templates & Appliances** | `ovirt_template_*`, `ovirt_vm_export`, `ovirt_vm_import`, `ovirt_disk_export` | 7 | VM template creation from VMs, template deletion, OVA appliance export/import, and disk export | [TOOLS.md#8](TOOLS.md#80-ovirt_template_list) |
| 9 | **Clusters & Data Centers** | `ovirt_cluster_*`, `ovirt_datacenter_*` | 4 | Cluster inventory and configuration (CPU types, compatibility versions, memory overcommit, FIPS, BIOS type), and Data Center management | [TOOLS.md#9](TOOLS.md#87-ovirt_cluster_list) |
| 10 | **Resource Quotas** | `ovirt_quota_*` | 4 | Cluster vCPU/RAM limits, storage domain gigabyte limits, and quota lifecycle enforcement | [TOOLS.md#10](TOOLS.md#91-ovirt_quota_list) |
| 11 | **Logical Networks & vNICs** | `ovirt_network_*`, `ovirt_network_profile_*` | 5 | Logical network management (VLAN tagging, MTU, VM network assignment) and vNIC profile listing | [TOOLS.md#11](TOOLS.md#95-ovirt_network_list) |
| 12 | **Resource Tags** | `ovirt_tag_*`, `ovirt_*_tag_*` | 9 | Tag hierarchy management, assigning and unassigning tags across VMs, hosts, and users | [TOOLS.md#12](TOOLS.md#99-ovirt_tag_list) |
| 13 | **Audit Logging & Events** | `ovirt_system_events`, `ovirt_vm_events`, `ovirt_host_events` | 3 | Global and per-entity audit logs, severity filtering, correlation IDs, and entity UUID tracking | [TOOLS.md#13](TOOLS.md#111-ovirt_system_events) |
| 14 | **Identity, Roles & Permissions** | `ovirt_user_*`, `ovirt_role_*`, `ovirt_permission_*` | 10 | User account lookup, addition, deletion, role privilege inspection, and fine-grained permission grants | [TOOLS.md#14](TOOLS.md#112-ovirt_user_list) |
| 15 | **Virtual Machine Pools** | `ovirt_vm_pool_*` | 6 | Stateful & stateless VDI desktop pools, pool creation, parameter updates, allocation, and deletion | [TOOLS.md#15](TOOLS.md#122-ovirt_vm_pool_list) |
| 16 | **Backup & Incremental CBT** | `ovirt_vm_checkpoint_*`, `ovirt_vm_backup_*` | 7 | Changed Block Tracking (CBT) checkpoint management, live backup sessions, scratch disk overlays, and backup finalization | [TOOLS.md#16](TOOLS.md#128-ovirt_vm_checkpoint_list) |
| 17 | **Asynchronous Jobs & Progress** | `ovirt_job_*` | 2 | Real-time monitoring of asynchronous engine operations, execution sub-steps, progress percentages (0-100%), and execution host mapping | [TOOLS.md#17](TOOLS.md#135-ovirt_job_list) |
| **Total** | | | **136** | **Full-Stack Enterprise Virtualization Operations** | **[Complete Catalog](TOOLS.md)** |

---

### Enterprise Telemetry & Observability Highlights

- **Real-Time Per-Disk I/O Telemetry (`ovirt_vm_get`, `ovirt_disk_list`):**
  Inspect instantaneous read/write throughput in bytes/second, read/write IOPS, and hypervisor-reported latency for each attached virtual disk.
- **Storage Domain Overcommitment & Capacity Health (`ovirt_storage_domain_get`):**
  Evaluate thin-provisioning risk with computed `overcommit_ratio`, `space_health` indicators (`healthy`, `warning`, `critical`, `overcommitted`), domain-wide aggregated IOPS, and top I/O active disks.
- **Asynchronous Engine Task Tracking (`ovirt_job_list`, `ovirt_job_get`):**
  Monitor long-running operations (live VM migrations, disk moves, snapshot consolidations) without blocking the AI agent, with step-level status, progress percentages, and host mapping.
- **Audit Correlation & Tracing (`ovirt_system_events`):**
  Correlate operational events directly with engine resource UUIDs (`vm_id`, `host_id`, `cluster_id`, `storage_domain_id`), bridging audit trail diagnostics with live telemetry inspection.

---

## Connecting to AI MCP Clients

`ovirt-mcp` supports versatile deployment models across desktop, remote server, and containerized architectures:
1. **Local Desktop Mode (`stdio`):** Claude Desktop or local LLM agents launch the server on-demand on your workstation via Docker or Python venv.
2. **24/7 Network Daemon Mode (`sse`):** The server runs continuously in background (on Proxmox LXC/VM, TrueNAS, unRAID, or dedicated Linux server) as a Docker container. Any AI client connects over HTTP via Server-Sent Events (`/sse`).
3. **Remote Linux IDE Environments (`stdio`):** When developing on a remote Linux jumpbox or server via **VS Code (Remote - SSH / WSL)** or **Kiro IDE**, the AI agent runs `ovirt-mcp` natively inside the remote environment's Python virtualenv.

---

### Method 1: Docker Desktop for Claude (Zero-Install Setup)

No Python, C compiler, or virtual environment required on your workstation!

#### Step 1: Pull Pre-built Container or Build Locally

Pull the official multi-architecture image (`linux/amd64` and `linux/arm64`) automatically published by GitHub Actions:
```bash
docker pull ghcr.io/gerilab/ovirt-mcp:latest
```

*(Or build it locally from source)*:
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

Add the `ovirt` server configuration (using either `ghcr.io/gerilab/ovirt-mcp:latest` or `ovirt-mcp`):
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
        "-e", "OVIRT_USERNAME=mcp-service@internal-authz",
        "-e", "OVIRT_PASSWORD=YourSecurePasswordHere",
        "-e", "OVIRT_INSECURE=true",
        "-e", "MCP_COMPACT_MODE=true",
        "ghcr.io/gerilab/ovirt-mcp:latest"
      ]
    }
  }
}
```
Restart Claude Desktop. The hammer icon will show all 136 oVirt tools loaded!

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
OVIRT_USERNAME=mcp-service@internal-authz
OVIRT_PASSWORD=YourSecurePasswordHere
OVIRT_INSECURE=true
MCP_TRANSPORT=sse
MCP_PORT=8000
```

Start the daemon in background:
```bash
docker compose up -d
```

*(Alternatively, run with docker directly using GHCR)*:
```bash
docker run -d \
  --name ovirt-mcp \
  --restart unless-stopped \
  -p 8000:8000 \
  -e OVIRT_URL="https://olvm-engine.example.com/ovirt-engine/api" \
  -e OVIRT_USERNAME="mcp-service@internal-authz" \
  -e OVIRT_PASSWORD="YourSecurePasswordHere" \
  -e OVIRT_INSECURE="true" \
  -e MCP_TRANSPORT="sse" \
  -e MCP_HOST="0.0.0.0" \
  -e MCP_PORT="8000" \
  ghcr.io/gerilab/ovirt-mcp:latest
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

### Method 3: Native Python Virtual Environment (Linux & macOS)

If you run directly on a Linux or macOS host operating system:

```bash
cd /path/to/ovirt-mcp
source .venv/bin/activate
ovirt-mcp
```

#### Configure Claude Desktop (macOS / Linux):
Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `~/.config/Claude/claude_desktop_config.json` (Linux):

```json
{
  "mcpServers": {
    "ovirt": {
      "command": "/path/to/ovirt-mcp/.venv/bin/python",
      "args": ["-m", "ovirt_mcp.server"],
      "env": {
        "OVIRT_URL": "https://olvm-engine.example.com/ovirt-engine/api",
        "OVIRT_USERNAME": "mcp-service@internal-authz",
        "OVIRT_PASSWORD": "YourSecurePasswordHere",
        "OVIRT_INSECURE": "true",
        "MCP_COMPACT_MODE": "true",
        "MCP_SAFE_MODE": "true"
      }
    }
  }
}
```

---

### Method 4: Windows Desktop & IDE Setup (Step-by-Step for Windows & uv/uvx)

This step-by-step guide is designed for Windows users running VS Code, Claude Desktop, Cursor, Cline, or Roo Code on Windows 10/11.

#### Understanding Windows Requirements & Astral `uv` / `uvx`

> [!NOTE]
> `ovirt-mcp` utilizes the official `ovirt-engine-sdk-python` library, which contains high-performance C extensions compiled against `libxml2` and `libcurl`. On Linux, these compile automatically via system package headers.
>
> On Windows, developers have **three fast, reliable deployment choices**:
> 1. **Option A (Zero-Build via WSL2 with `uvx` - Recommended):** Invoke `uvx` through `wsl.exe`. Zero manual compilation or C++ build tools required on Windows!
> 2. **Option B (Zero-Build via Docker Desktop):** Run the pre-built, non-root multi-arch container `ghcr.io/gerilab/ovirt-mcp:latest`.
> 3. **Option C (Native Windows with `uv` or `venv`):** Run natively using Astral `uv` in Windows PowerShell (requires Microsoft Visual C++ Build Tools installed).

---

#### Option A: Zero-Build via WSL2 with `uvx` (Fastest for Windows Clients)

If you have WSL2 installed (default on modern Windows 10/11), your Windows AI clients (Claude Desktop, VS Code, Cursor) can directly invoke `uvx` through `wsl.exe`. This completely bypasses Windows C++ compiler issues and runs in an isolated Linux micro-environment:

1. **One-time preparation inside WSL (Ubuntu/Debian):**
   ```bash
   # Install uv inside WSL
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install development headers for the SDK
   sudo apt-get update && sudo apt-get install -y libcurl4-openssl-dev libxml2-dev gcc
   ```

2. **Configure Claude Desktop on Windows (`%APPDATA%\Claude\claude_desktop_config.json`):**
   ```json
   {
     "mcpServers": {
       "ovirt": {
         "command": "wsl.exe",
         "args": [
           "uvx",
           "--from",
           "git+https://github.com/gerilab/ovirt-mcp.git",
           "ovirt-mcp"
         ],
         "env": {
           "OVIRT_URL": "https://olvm-engine.example.com/ovirt-engine/api",
           "OVIRT_USERNAME": "admin@ovirt@internal",
           "OVIRT_PASSWORD": "YourSecurePasswordHere",
           "OVIRT_INSECURE": "true",
           "MCP_COMPACT_MODE": "true"
         }
       }
     }
   }
   ```

3. **Configure VS Code (`.vscode/mcp.json`):**
   ```json
   {
     "mcpServers": {
       "ovirt": {
         "command": "wsl.exe",
         "args": [
           "uvx",
           "--from",
           "git+https://github.com/gerilab/ovirt-mcp.git",
           "ovirt-mcp"
         ],
         "env": {
           "OVIRT_URL": "https://olvm-engine.example.com/ovirt-engine/api",
           "OVIRT_USERNAME": "admin@ovirt@internal",
           "OVIRT_PASSWORD": "YourSecurePasswordHere",
           "OVIRT_INSECURE": "true",
           "MCP_COMPACT_MODE": "true"
         }
       }
     }
   }
   ```

---

#### Option B: Zero-Build via Docker Desktop on Windows

If you run Docker Desktop on Windows, no Python, C++ compilers, or repository clones are needed:

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
        "-e", "OVIRT_USERNAME=admin@ovirt@internal",
        "-e", "OVIRT_PASSWORD=YourSecurePasswordHere",
        "-e", "OVIRT_INSECURE=true",
        "-e", "MCP_COMPACT_MODE=true",
        "ghcr.io/gerilab/ovirt-mcp:latest"
      ]
    }
  }
}
```

---

#### Option C: Native Windows with Astral `uv` or Standard Python `venv`

If you want to run `ovirt-mcp` natively on Windows:

1. **Install Astral `uv` on Windows:**
   ```powershell
   winget install --id=astral-sh.uv
   # or via PowerShell installer:
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Clone and Create Virtual Environment with `uv`:**
   ```powershell
   # 1. Clone into your user folder
   cd C:\Users\$env:USERNAME
   git clone https://github.com/gerilab/ovirt-mcp.git
   cd ovirt-mcp

   # 2. Create high-speed virtual environment with uv
   uv venv .venv
   .\.venv\Scripts\Activate.ps1

   # 3. Install ovirt-mcp in editable mode
   uv pip install -e .
   ```

   *(Note: Native Windows compilation requires "Desktop development with C++" installed via Visual Studio Build Tools).*

3. **Windows Path Rules in JSON Configurations:**
   * **Recommended:** Use standard forward slashes (`/`), supported across Python, `uv`, and VS Code:
     `"command": "C:/Users/YourName/ovirt-mcp/.venv/Scripts/ovirt-mcp.exe"`
   * **Alternative:** Double-escaped backslashes:
     `"command": "C:\\Users\\YourName\\ovirt-mcp\\.venv\\Scripts\\ovirt-mcp.exe"`

4. **Configure AI Clients on Windows:**

##### For Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "ovirt": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:/Users/<Username>/ovirt-mcp",
        "ovirt-mcp"
      ],
      "env": {
        "OVIRT_URL": "https://olvm-engine.example.com/ovirt-engine/api",
        "OVIRT_USERNAME": "admin@ovirt@internal",
        "OVIRT_PASSWORD": "YourSecurePasswordHere",
        "OVIRT_INSECURE": "true",
        "MCP_COMPACT_MODE": "true",
        "MCP_SAFE_MODE": "true",
        "MCP_READ_ONLY": "false"
      }
    }
  }
}
```

##### For VS Code with Native `python.exe` (`.vscode/mcp.json`):
```json
{
  "mcpServers": {
    "ovirt": {
      "command": "${workspaceFolder}/.venv/Scripts/python.exe",
      "args": ["-m", "ovirt_mcp.server"],
      "env": {
        "OVIRT_URL": "https://olvm-engine.example.com/ovirt-engine/api",
        "OVIRT_USERNAME": "admin@ovirt@internal",
        "OVIRT_PASSWORD": "YourSecurePasswordHere",
        "OVIRT_INSECURE": "true",
        "MCP_COMPACT_MODE": "true",
        "MCP_SAFE_MODE": "true",
        "MCP_READ_ONLY": "false"
      }
    }
  }
}
```
```

---

### Method 5: Remote Linux Jumpbox via SSH (VS Code Remote - SSH)

This is the standard enterprise architecture: your local developer workstation (Windows, macOS, or Linux laptop) connects over SSH to a remote Linux development server, jumpbox, or bastion host (e.g., `jumpbox-srv01.example.com`) where `ovirt-mcp` is installed.

#### Why Use a Remote SSH Jumpbox?

In production environments, the oVirt/OLVM engine API (e.g. `https://olvm-engine.example.com/ovirt-engine/api`) resides on an **isolated management network / VLAN** (e.g., `10.0.10.0/24`). Developer workstations usually cannot—and for security reasons *should not*—directly route into hypervisor management interfaces.

A Linux jumpbox or CI/CD runner sits directly inside the management network with access to the engine API. Connecting via SSH allows developers to run AI coding assistants seamlessly while keeping all network traffic strictly within the protected hypervisor zone.

#### Understanding the Remote Execution Model

When you connect to a remote host using VS Code Remote - SSH:

| Component | Runs On Local Laptop | Runs On Remote Linux Jumpbox | Notes |
|---|---|---|---|
| **VS Code UI** | Windows / macOS | — | Handles editor window, menus, keystrokes, and rendering. |
| **VS Code Server (`.vscode-server`)** | — | Linux daemon | Runs extension hosts, terminals, and file system watchers. |
| **AI Extensions (Cline, Roo, etc.)** | — | Linux extension host | Spawns MCP client logic directly on the jumpbox. |
| **`ovirt-mcp` Process** | — | Linux subprocess | Executes via stdio using the Linux virtual environment. |
| **oVirt / OLVM API Communication** | — | Linux network stack | Direct HTTPS communication to internal engine IP/FQDN. |

> [!IMPORTANT]
> Because the extension host runs on the **remote Linux machine**, all paths in your MCP configuration must be **Linux paths** (e.g., `/home/devops/ovirt-mcp` or `${workspaceFolder}`), **NOT** Windows paths (`C:\...`).

#### Step 1: Configure SSH Access on Your Local Laptop

On your local workstation, add the jumpbox to your SSH configuration file (`~/.ssh/config` on Linux/macOS or `%USERPROFILE%\.ssh\config` on Windows):

```ssh
Host olvm-jumpbox
    HostName 10.0.10.25
    User devops
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
```

1. Open **VS Code** on your local machine.
2. Install the official **Remote - SSH** extension (`ms-vscode-remote.remote-ssh`).
3. Press `F1` or `Ctrl+Shift+P` (`Cmd+Shift+P` on macOS), type `Remote-SSH: Connect to Host...`, and select `olvm-jumpbox`.
4. A new VS Code window will open connected to the remote jumpbox (indicated in the bottom-left corner).

#### Step 2: Set Up `ovirt-mcp` on the Remote Server

In the integrated terminal of your remote VS Code window (``Ctrl+` ``):

```bash
# Clone the repository
git clone https://github.com/gerilab/ovirt-mcp.git ~/ovirt-mcp
cd ~/ovirt-mcp

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install package
pip install --upgrade pip
pip install -e .

# Verify the CLI tool boots cleanly:
ovirt-mcp --help
```

#### Step 3: Open the Remote Project Directory

In VS Code:
1. Click **File -> Open Folder...**
2. Enter the path where you cloned the repository (e.g. `/home/devops/ovirt-mcp`).
3. Click **OK**.

Opening the workspace folder ensures that `${workspaceFolder}` dynamically and accurately resolves to your remote repository path.

#### Step 4: Extension Setup on Remote Host (Avoid the "Local vs Remote" Trap!)

> [!WARNING]
> **Common Pitfall (Local vs. Remote Extensions):**
> Extensions like **Cline** or **Roo Code** must be installed inside the **remote extension host**, not just locally on your laptop!
> In VS Code's Extensions panel (`Ctrl+Shift+X`), look for the section labeled **SSH: olvm-jumpbox**. If Cline or Roo Code shows an **"Install in SSH: olvm-jumpbox"** button, click it.

#### Step 5: Configure MCP Server (Method A or Method B)

Choose the configuration style that best fits your workflow:

##### Option 1: Workspace-Level Configuration (`.vscode/mcp.json`) — Recommended

Inside your remote workspace, create or edit `.vscode/mcp.json`:

###### Method A: Using a Remote `.env` File
Create `~/ovirt-mcp/.env` with your engine credentials, then configure `.vscode/mcp.json`:
```json
{
  "mcpServers": {
    "ovirt": {
      "command": "${workspaceFolder}/.venv/bin/ovirt-mcp",
      "args": [],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

###### Method B: Zero `.env` File (Credentials Directly in `mcp.json`)
If you prefer keeping credentials entirely inside the IDE settings without an extra `.env` file on disk:
```json
{
  "mcpServers": {
    "ovirt": {
      "command": "${workspaceFolder}/.venv/bin/ovirt-mcp",
      "args": [],
      "cwd": "${workspaceFolder}",
      "env": {
        "OVIRT_URL": "https://olvm-engine.example.com/ovirt-engine/api",
        "OVIRT_USERNAME": "admin@internal",
        "OVIRT_PASSWORD": "YourSecurePasswordHere",
        "OVIRT_INSECURE": "true",
        "OVIRT_AUTO_DOWNLOAD_CA": "true",
        "MCP_COMPACT_MODE": "true",
        "MCP_SAFE_MODE": "true",
        "MCP_READ_ONLY": "false"
      }
    }
  }
}
```

##### Option 2: Cline / Roo Code Remote Settings File

If your extension manages MCP servers via its own JSON file (e.g. `cline_mcp_settings.json`), open the extension MCP settings tab in the remote window and add:

```json
{
  "mcpServers": {
    "ovirt": {
      "command": "/home/devops/ovirt-mcp/.venv/bin/ovirt-mcp",
      "args": [],
      "cwd": "/home/devops/ovirt-mcp",
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

#### Step 6: Verify in Remote VS Code

1. In the Cline or Roo Code MCP panel on the remote host, check that the `ovirt` server has a green status indicator and reports all 136 tools.
2. In the AI chat, submit a test prompt:
   ```text
   Test hypervisor connection using ovirt_test_connection, then list the first 5 VMs with ovirt_vm_list.
   ```

---

### Method 6: Kiro IDE on Remote Linux (via SSH)

**Kiro IDE** is an AI-native agentic development environment equipped with built-in agent loops and first-class Model Context Protocol (MCP) support. When working in enterprise virtualized environments, developers can use Kiro IDE connected directly to remote Linux infrastructure over SSH.

#### Architecture Overview for Kiro IDE

Just like with VS Code Remote - SSH, when Kiro IDE connects to a remote Linux jumpbox:
- The Kiro UI client runs on your local machine.
- Kiro's background agent runner and MCP server processes execute **remotely** on the jumpbox.
- All 136 `ovirt-mcp` tools run natively in the remote Linux virtualenv with direct access to internal OLVM/oVirt management subnets.

#### Step 1: Connect to Remote Linux Host in Kiro

1. Launch **Kiro IDE** on your workstation.
2. Open the remote connection manager (e.g. `Remote: Connect to Host via SSH` or open an SSH workspace).
3. Connect using your SSH credentials (or reference the SSH host alias defined in `~/.ssh/config`).
4. Once connected, open the cloned `ovirt-mcp` directory (e.g., `/home/devops/ovirt-mcp`).

#### Step 2: Configure `.kiro/mcp.json`

Kiro IDE uses a dedicated workspace configuration directory: `.kiro/`.

Inside your remote workspace root, create `.kiro/mcp.json`:

```json
{
  "mcpServers": {
    "ovirt": {
      "command": "${workspaceFolder}/.venv/bin/ovirt-mcp",
      "args": [],
      "cwd": "${workspaceFolder}",
      "env": {
        "OVIRT_URL": "https://olvm-engine.example.com/ovirt-engine/api",
        "OVIRT_USERNAME": "admin@internal",
        "OVIRT_PASSWORD": "YourSecurePasswordHere",
        "OVIRT_INSECURE": "true",
        "OVIRT_AUTO_DOWNLOAD_CA": "true",
        "MCP_COMPACT_MODE": "true",
        "MCP_SAFE_MODE": "true",
        "MCP_READ_ONLY": "false"
      },
      "disabled": false,
      "autoApprove": [
        "ovirt_test_connection",
        "ovirt_vm_list",
        "ovirt_vm_get",
        "ovirt_host_list",
        "ovirt_host_stats",
        "ovirt_storage_domain_list",
        "ovirt_cluster_list"
      ]
    }
  }
}
```

> [!TIP]
> **Kiro `autoApprove` List:**
> By populating the `"autoApprove"` array with harmless read-only inspection tools, Kiro's AI agent can explore hypervisor health, inventory, and metrics instantly without popping up manual permission prompts for every single query.

#### Step 3: Global Configuration (`~/.kiro/mcp.json`)

If you want `ovirt-mcp` to be available across all workspaces on your remote Linux host, place the configuration in `~/.kiro/mcp.json`:

```json
{
  "mcpServers": {
    "ovirt": {
      "command": "/home/devops/ovirt-mcp/.venv/bin/ovirt-mcp",
      "args": [],
      "cwd": "/home/devops/ovirt-mcp",
      "env": {
        "OVIRT_URL": "https://olvm-engine.example.com/ovirt-engine/api",
        "OVIRT_USERNAME": "admin@internal",
        "OVIRT_PASSWORD": "YourSecurePasswordHere",
        "OVIRT_INSECURE": "true",
        "MCP_COMPACT_MODE": "true"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

#### Step 4: Verification and Live Interaction in Kiro

1. In Kiro's MCP panel, verify that `ovirt` shows **Connected** with 136 tools available.
2. Open the Kiro Agent chat panel and try the following real-world virtualization workflows:

##### Diagnostic Query:
```text
Verify our connection with ovirt_test_connection, then check overall CPU and memory utilization across all hypervisor hosts using ovirt_host_stats.
```

##### Troubleshooting Query:
```text
Find all VMs in cluster 'Default' that are in 'down' state, and check their recent events using ovirt_vm_events to see why they stopped.
```

##### Controlled Mutation (Safe Mode):
```text
Create a snapshot named 'pre-upgrade-backup' for VM 'db-prod-01'.
```
When `MCP_SAFE_MODE=true`, `ovirt-mcp` will require explicit confirmation (`confirm=true`), which Kiro's agent will highlight in the prompt interface before triggering the action on the hypervisor.

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

## Version History & Changelog

For detailed release notes, migration guides, and historical changes across releases, see the complete [CHANGELOG.md](CHANGELOG.md) and the [GitHub Releases](https://github.com/gerilab/ovirt-mcp/releases) page.

---

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
