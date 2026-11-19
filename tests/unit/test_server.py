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
