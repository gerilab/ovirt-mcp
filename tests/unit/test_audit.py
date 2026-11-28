"""Unit tests for SDK parity and coverage audit engine."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

from ovirt_mcp.server import main

audit_script_path = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "audit_sdk_coverage.py"
)
spec = importlib.util.spec_from_file_location("audit_sdk_coverage", audit_script_path)
assert spec and spec.loader
audit_mod = importlib.util.module_from_spec(spec)
sys.modules["audit_sdk_coverage"] = audit_mod
spec.loader.exec_module(audit_mod)


def test_audit_types_coverage() -> None:
    """Verify that type coverage audit introspects target SDK types."""
    results = audit_mod.audit_types_coverage()
    assert len(results) >= 10

    names = [r.resource_name for r in results]
    assert "Host" in names
    assert "Virtual Machine (Vm)" in names
    assert "Virtual Disk" in names
    assert "Storage Domain" in names

    for r in results:
        assert r.total_sdk_properties > 0
        assert r.covered_properties_count >= 0
        assert 0.0 <= r.coverage_percent <= 100.0
        assert len(r.covered_fields) + len(r.missing_fields) == r.total_sdk_properties


def test_audit_services_coverage() -> None:
    """Verify that service coverage audit inspects SDK service actions."""
    results = audit_mod.audit_services_coverage()
    assert len(results) >= 5

    names = [r.service_name for r in results]
    assert "VmService" in names
    assert "HostService" in names

    for r in results:
        assert r.total_actions > 0
        assert 0.0 <= r.coverage_percent <= 100.0


def test_format_terminal_report() -> None:
    """Verify terminal report formatting."""
    type_results = audit_mod.audit_types_coverage()
    service_results = audit_mod.audit_services_coverage()
    report = audit_mod.format_terminal_report(type_results, service_results)

    assert "SDK Parity & Coverage Audit Report" in report
    assert "Total Registered MCP Tools:" in report
    assert "Virtual Machine (Vm)" in report


def test_generate_markdown_matrix() -> None:
    """Verify Markdown matrix generation."""
    type_results = audit_mod.audit_types_coverage()
    service_results = audit_mod.audit_services_coverage()
    markdown = audit_mod.generate_markdown_matrix(type_results, service_results)

    assert "# oVirt / OLVM SDK Parity & Coverage Matrix" in markdown
    assert "## 1. Resource Domain Coverage Summary" in markdown
    assert "## 2. Service Action & Mutation Tool Coverage" in markdown
    assert "## 3. Detailed Unmapped Fields per Resource Domain" in markdown
    assert "## 4. Unmapped Service Action Methods (Candidate Tools)" in markdown


def test_audit_main_cli() -> None:
    """Verify audit main function runs with custom arguments and write-markdown."""
    with patch.object(Path, "write_text") as mock_write:
        code = audit_mod.main(["--audit", "--write-markdown"])
        assert code == 0
        mock_write.assert_called_once()
        content = mock_write.call_args[0][0]
        assert "# oVirt / OLVM SDK Parity & Coverage Matrix" in content


def test_server_cli_audit_flag() -> None:
    """Verify ovirt-mcp server CLI handles --audit argument."""
    with (
        patch("sys.argv", ["ovirt-mcp", "--audit"]),
        patch("ovirt_mcp.server.run_audit_cli", return_value=0) as mock_audit,
    ):
        try:
            main()
        except SystemExit as exc:
            assert exc.code == 0
        mock_audit.assert_called_once()
