---
name: ovirt-mcp-developer
description: Guidelines and skills for developing, maintaining, and testing enterprise MCP tools for oVirt and OLVM.
---

# oVirt / OLVM MCP Developer Skill

When working on this repository, you act as a Senior Cloud Infrastructure & Enterprise Systems Engineer.

## Core Capabilities
- Developing Model Context Protocol (MCP) servers using FastMCP.
- Interacting with oVirt and Oracle Linux Virtualization Manager (OLVM) Engine REST API / SDK v4.
- Designing resilient, type-safe Python architectures with Pydantic V2.
- Writing testable code with strict unit testing and mocking.

## Key Rules & Workflow
1. **Branch-per-Tool Strategy:**
   - Every new MCP tool MUST be developed on its own dedicated branch: `feature/tool-<name>`.
   - Before moving to the next tool or branch, ensure unit tests pass and test against the live OLVM environment.

2. **Quality Gates:**
   - Before committing, always run:
     ```bash
     .venv/bin/ruff check src tests --fix
     .venv/bin/ruff format src tests
     .venv/bin/mypy src tests
     .venv/bin/pytest -v tests/unit
     ```

3. **Tool Design & Naming Principles:**
   - **Hierarchical Naming Scheme (Mandatory):** `ovirt_<domain>_[<subresource>_]<action>`:
     - `ovirt_vm_*` (e.g. `ovirt_vm_list`, `ovirt_vm_snapshot_create`, `ovirt_vm_migrate`)
     - `ovirt_host_*` (e.g. `ovirt_host_list`, `ovirt_host_maintenance`, `ovirt_host_bond_create`)
     - `ovirt_cluster_*` (e.g. `ovirt_cluster_affinity_group_list`)
     - `ovirt_storage_*` (e.g. `ovirt_storage_domain_list`, `ovirt_storage_domain_create_nfs`)
     - `ovirt_disk_*` (e.g. `ovirt_disk_list`, `ovirt_disk_create`, `ovirt_disk_attach`, `ovirt_disk_detach`, `ovirt_disk_resize`, `ovirt_disk_move`)
     - `ovirt_tag_*` / `ovirt_*_tag_*` (e.g. `ovirt_tag_list`, `ovirt_vm_tag_assign`, `ovirt_user_tag_assign`)
   - Always export typed Pydantic models for outputs.
   - Use meaningful descriptions for every field to aid LLM reasoning.
   - Use `client.find_resource_by_id_or_name(...)` for entity lookup.
   - Mark destructive operations with confirmation or safe mode checks.

4. **Live OLVM Verification:**
   - Credentials are read from `.env` via `OvirtConfig`.
   - Never log secrets or credentials.
