from pathlib import Path

import pytest
from pydantic import ValidationError

from qa_mcp_hub.config import HubSettings, default_config_dir
from qa_mcp_hub.core.capabilities import list_capabilities
from qa_mcp_hub.server import hub_health


def test_health_result() -> None:
    result = hub_health()
    assert result.status == "healthy"
    assert result.version == "0.1.0"
    assert result.transport == "stdio"


def test_catalog_distinguishes_future_work() -> None:
    catalog = list_capabilities()
    assert "hub_health" in catalog.implemented
    assert "profiles_and_credentials" not in catalog.implemented
    assert "profiles_and_credentials" in catalog.planned


def test_typed_environment_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_MCP_LOG_LEVEL", "WARNING")
    assert HubSettings().log_level == "WARNING"
    monkeypatch.setenv("QA_MCP_LOG_LEVEL", "NOPE")
    with pytest.raises(ValidationError):
        HubSettings()


@pytest.mark.parametrize(
    ("platform", "suffix"),
    [
        ("win32", Path("AppData/Roaming/qa-mcp-hub")),
        ("darwin", Path("Library/Application Support/qa-mcp-hub")),
        ("linux", Path(".config/qa-mcp-hub")),
    ],
)
def test_cross_platform_config_paths(
    monkeypatch: pytest.MonkeyPatch, platform: str, suffix: Path
) -> None:
    home = Path("/mock-home")
    assert default_config_dir(home=home, platform=platform, environ={}) == home / suffix


def test_windows_appdata_override(monkeypatch: pytest.MonkeyPatch) -> None:
    del monkeypatch
    assert default_config_dir(
        home=Path("/home"),
        platform="win32",
        environ={"APPDATA": "/custom/roaming"},
    ) == Path("/custom/roaming/qa-mcp-hub")


def test_linux_xdg_override(monkeypatch: pytest.MonkeyPatch) -> None:
    del monkeypatch
    assert default_config_dir(
        home=Path("/home"),
        platform="linux",
        environ={"XDG_CONFIG_HOME": "/custom/config"},
    ) == Path("/custom/config/qa-mcp-hub")


def test_transport_cannot_enable_remote_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QA_MCP_TRANSPORT", "http")
    with pytest.raises(ValidationError):
        HubSettings()
