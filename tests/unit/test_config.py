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


def test_sanitized_url() -> None:
    """Test sanitized_url removes trailing slashes."""
    cfg = OvirtConfig(
        ovirt_url="https://olvm.example.com/ovirt-engine/api///",
        ovirt_password="test",  # type: ignore[arg-type]
    )
    assert cfg.sanitized_url() == "https://olvm.example.com/ovirt-engine/api"
