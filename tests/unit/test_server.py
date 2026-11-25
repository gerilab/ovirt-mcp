"""Unit tests for server entrypoint and transport modes."""

from unittest.mock import patch

import pytest

from ovirt_mcp.config import OvirtConfig
from ovirt_mcp.server import main


def test_server_main_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test server.main runs stdio by default."""
    cfg = OvirtConfig(
        _env_file=None,  # type: ignore[call-arg]
        ovirt_password="test",  # type: ignore[arg-type]
        mcp_transport="stdio",
    )
    monkeypatch.setattr("ovirt_mcp.server.get_config", lambda: cfg)

    with patch("ovirt_mcp.server.mcp.run") as mock_run:
        main()
        mock_run.assert_called_once_with(transport="stdio")


def test_server_main_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test server.main runs SSE when configured."""
    cfg = OvirtConfig(
        _env_file=None,  # type: ignore[call-arg]
        ovirt_password="test",  # type: ignore[arg-type]
        mcp_transport="sse",
        mcp_host="0.0.0.0",
        mcp_port=8000,
    )
    monkeypatch.setattr("ovirt_mcp.server.get_config", lambda: cfg)

    with patch("ovirt_mcp.server.mcp.run") as mock_run:
        main()
        mock_run.assert_called_once_with(
            transport="sse",
            host="0.0.0.0",
            port=8000,
        )


@pytest.mark.asyncio
async def test_ovirt_mcp_server_error_wrapping() -> None:
    """Test OvirtMCPServer wraps unexpected crashes into ToolError with error details."""
    from mcp.server.mcpserver.exceptions import ToolError

    from ovirt_mcp.client.exceptions import NotFoundError
    from ovirt_mcp.server import OvirtMCPServer

    test_server = OvirtMCPServer(name="test_err_server")

    @test_server.tool(name="tool_unexpected_crash")
    def tool_unexpected_crash() -> str:
        raise ValueError("Critical Pydantic or internal failure detail")

    @test_server.tool(name="tool_ovirt_error")
    def tool_ovirt_error() -> str:
        raise NotFoundError("VM", "vm-not-found-123")

    # 1. Unexpected crash should surface message
    with pytest.raises(ToolError) as exc_info:
        await test_server.call_tool("tool_unexpected_crash", {})
    assert "Critical Pydantic or internal failure detail" in str(exc_info.value)

    # 2. OvirtMCPError should pass through
    with pytest.raises(ToolError) as exc_info2:
        await test_server.call_tool("tool_ovirt_error", {})
    assert "VM 'vm-not-found-123' not found" in str(exc_info2.value)


def test_server_check_cli_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test check_connection_cli returns 0 on successful engine check."""
    from unittest.mock import MagicMock

    from ovirt_mcp.server import check_connection_cli

    mock_client = MagicMock()
    mock_client.test_connection.return_value = {
        "status": "connected",
        "product_name": "oVirt Engine",
        "version": "4.5.5",
        "url": "https://olvm.example.com/ovirt-engine/api",
    }
    monkeypatch.setattr("ovirt_mcp.server.get_client", lambda: mock_client)

    exit_code = check_connection_cli()
    assert exit_code == 0
    mock_client.test_connection.assert_called_once()


def test_server_check_cli_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test check_connection_cli returns 1 on failed engine check."""
    from unittest.mock import MagicMock

    from ovirt_mcp.server import check_connection_cli

    mock_client = MagicMock()
    mock_client.test_connection.side_effect = RuntimeError("Connection refused")
    monkeypatch.setattr("ovirt_mcp.server.get_client", lambda: mock_client)

    exit_code = check_connection_cli()
    assert exit_code == 1
