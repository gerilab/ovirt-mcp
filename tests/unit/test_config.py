"""Unit tests for OvirtConfig."""

from ovirt_mcp.config import OvirtConfig


def test_config_defaults() -> None:
    """Test default values of OvirtConfig."""
    cfg = OvirtConfig(_env_file=None, ovirt_password="test_secret")  # type: ignore[arg-type,call-arg]
    assert cfg.ovirt_url == "https://localhost/ovirt-engine/api"
    assert cfg.ovirt_username == "admin@internal"
    assert cfg.ovirt_password.get_secret_value() == "test_secret"
    assert cfg.ovirt_insecure is False
    assert cfg.ovirt_timeout == 30
    assert cfg.mcp_safe_mode is True
    assert cfg.mcp_transport == "stdio"
    assert cfg.mcp_host == "0.0.0.0"
    assert cfg.mcp_port == 8000


def test_config_transport_custom() -> None:
    """Test custom network transport configuration."""
    cfg = OvirtConfig(
        _env_file=None,  # type: ignore[call-arg]
        ovirt_password="test_secret",  # type: ignore[arg-type]
        mcp_transport="sse",
        mcp_host="127.0.0.1",
        mcp_port=9090,
    )
    assert cfg.mcp_transport == "sse"
    assert cfg.mcp_host == "127.0.0.1"
    assert cfg.mcp_port == 9090


def test_sanitized_url() -> None:
    """Test sanitized_url removes trailing slashes."""
    cfg = OvirtConfig(
        ovirt_url="https://olvm.example.com/ovirt-engine/api///",
        ovirt_password="test",  # type: ignore[arg-type]
    )
    assert cfg.sanitized_url() == "https://olvm.example.com/ovirt-engine/api"
