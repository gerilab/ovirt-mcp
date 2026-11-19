# Developer and AI Agent Guidelines for `ovirt-mcp`

Welcome to the **ovirt-mcp** repository. This document defines the engineering standards, architecture rules, and development workflows for both human contributors and autonomous AI Agents.

---

## 1. Project Overview & Mission

`ovirt-mcp` is an enterprise-grade Model Context Protocol (MCP) server designed to connect Large Language Models (LLMs) with **oVirt** and **Oracle Linux Virtualization Manager (OLVM)** platforms.

Key principles:
- **Zero Ambiguity:** Strict Pydantic V2 typing for all tool inputs and outputs.
- **Enterprise Reliability:** Automatic reconnection, TLS/CA cert caching, retry logic, and structured error handling.
- **Safety First:** Safe mode protection for destructive operations (VM deletion, snapshot rollback, host reboot).
- **Extensibility:** Clean separation between communication (`client/`), schemas (`models/`), MCP tools (`tools/`), resources (`resources/`), and prompt workflows (`prompts/`).

---

## 2. Git Branching & Workflow Rules

1. **Main Branch Protection:**
   - The `main` branch is always stable, tested, and releasable.
   - Never commit directly to `main` for new features or tools.

2. **Single-Tool Feature Branches:**
   - Work on one tool or logical toolset per branch.
   - Branch naming format: `feature/tool-<tool_name>` (e.g. `feature/tool-vm-list`, `feature/tool-vm-snapshot`).
   - Workflow:
     1. Create feature branch from latest `main`.
     2. Implement Pydantic schema and SDK interaction.
     3. Add FastMCP tool decorator and docstrings.
     4. Write unit tests with mocks in `tests/unit/`.
     5. Test against a live OLVM/oVirt test environment.
     6. Run `ruff` check/format and `mypy` typecheck.
     7. Open PR / Merge to `main`.

---

## 3. Tool Naming Scheme & Namespacing (Mandatory)

All MCP tools exposed to AI Agents MUST adhere to a strict, hierarchical naming convention:

```text
ovirt_<domain>_[<subresource>_]<action>
```

### Domain Prefixes:
- `ovirt_vm_*`: **All operations concerning virtual machines.**
  - Direct lifecycle: `ovirt_vm_list`, `ovirt_vm_get`, `ovirt_vm_create`, `ovirt_vm_delete`, `ovirt_vm_start`, `ovirt_vm_stop`, `ovirt_vm_shutdown`, `ovirt_vm_reboot`, `ovirt_vm_events`
  - Migration & placement: `ovirt_vm_migrate`, `ovirt_vm_pin`
  - Snapshots: `ovirt_vm_snapshot_list`, `ovirt_vm_snapshot_create`, `ovirt_vm_snapshot_restore`, `ovirt_vm_snapshot_delete`
  - Media & CD-ROM: `ovirt_vm_iso_attach`, `ovirt_vm_iso_eject`, `ovirt_vm_cdrom_list`
  - Disk attachments: `ovirt_disk_attach`, `ovirt_disk_detach` (with `ovirt_vm_disk_*` aliases)
  - Network interfaces: `ovirt_vm_nic_add`, `ovirt_vm_nic_remove`
  - Resources & console: `ovirt_vm_update`, `ovirt_vm_graphics_consoles`, `ovirt_vm_ticket`
- `ovirt_host_*`: Operations on hypervisor physical hosts (`list`, `get`, `activate`, `maintenance`, `restart`, `stats`, `nics`, `numa`, `devices`, `storage`, `events`, `bonding`).
- `ovirt_cluster_*`: Operations on clusters and affinity groups.
- `ovirt_storage_*`: Operations on storage domains (`list`, `get`, `create_nfs`, `attach`, `activate`, `maintenance`, `detach`, `delete`).
- `ovirt_disk_*`: Operations on storage disks (`list`, `create`, `attach`, `detach`, `resize`, `move`, `copy`, `sparsify`).
- `ovirt_tag_*` / `ovirt_*_tag_*`: Operations on hierarchical inventory tags and assignments across VMs, hosts, and users.
- `ovirt_template_*`: Operations on VM golden image templates.
- `ovirt_datacenter_*`, `ovirt_quota_*`, `ovirt_network_*`: Logical infrastructure and policy enforcement.

Never use generic or flat names (e.g. `snapshot_create` or `migrate_vm`). Always prefix with `ovirt_<domain>_...`.

---

## 4. Code Standards & Tooling

Every contribution must pass all quality gates:

```bash
# 1. Format and Linting
ruff check src tests --fix
ruff format src tests

# 2. Strict Type Checking
mypy src tests

# 3. Unit Tests
pytest -v tests/unit
```

### Type Checking Requirements
- Strict mode is enabled (`disallow_untyped_defs = true`).
- Every function, method, and tool must have explicit argument types and return type annotations.
- Do not use `Any` where a specific model or SDK type can be specified.

---

## 4. How to Add a New MCP Tool

When adding an MCP tool, follow this 4-step pattern:

### Step 1: Define Pydantic Models (`src/ovirt_mcp/models/<domain>.py`)
```python
from pydantic import BaseModel, Field


class VmSummary(BaseModel):
    id: str = Field(description="Unique UUID of the virtual machine")
    name: str = Field(description="Virtual machine display name")
    status: str = Field(description="Current status (e.g., up, down, paused)")
    cluster: str = Field(description="Cluster name hosting the VM")
```

### Step 2: Implement Tool Function (`src/ovirt_mcp/tools/<domain>.py`)
- Always use `@mcp.tool(name="ovirt_...", description="...")`.
- Provide comprehensive docstrings.
- Wrap calls with `OvirtClient` and catch/map SDK exceptions to `OvirtMCPError`.

### Step 3: Write Unit Tests (`tests/unit/test_<domain>.py`)
- Mock SDK calls using `unittest.mock.MagicMock`.
- Test both success and error branches (e.g. `NotFoundError`, connection drops).

### Step 4: Verify with Live OLVM
- Test against live engine using `.env` credentials.

---

## 5. oVirt & OLVM Specific Best Practices

- **Resource Lookup:** Always use `client.find_resource_by_id_or_name(...)` to support both UUIDs and human-readable names without duplicate lookup logic.
- **Asynchronous Operations:** Actions like starting a VM or creating a snapshot are asynchronous in oVirt. If an operation needs verification, poll with timeout rather than blocking indefinitely.
- **Image Locking:** Always check if a disk or VM is `LOCKED` before attempting write/snapshot/migration operations.
- **Sensitive Data:** Never print passwords, tokens, or ticket credentials into logs.
