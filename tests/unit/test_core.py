from pathlib import Path

import pytest
from pydantic import ValidationError

from qa_mcp_hub.config import (
    ConnectionConfig,
    HubConfig,
    HubSettings,
    ProfileConfig,
    default_config_dir,
)
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
    assert "profiles_and_credentials" in catalog.implemented
    assert "interactive_setup" in catalog.implemented
    assert "mcp_client_config_generation" in catalog.implemented
    assert "search_repository_code" in catalog.implemented
    assert "analyze_jira_ticket" in catalog.implemented
    assert "search_documents" in catalog.implemented
    assert "read_document" in catalog.implemented
    assert "search_knowledge" in catalog.implemented
    assert "find_implementation" in catalog.implemented
    assert "generate_test_scenario_draft" in catalog.implemented
    assert "list_registered_suites" in catalog.implemented
    assert "submit_test_run" in catalog.implemented
    assert "verify_e2e_workflow" in catalog.implemented
    assert "list_pipeline_runs" in catalog.implemented
    assert "prepare_pipeline_trigger" in catalog.implemented
    assert "search_test_cases" in catalog.implemented
    assert "prepare_result_publication" in catalog.implemented
    assert "generate_evidence" in catalog.implemented
    assert "assess_release_readiness" in catalog.implemented
    assert "community_release" in catalog.planned
    assert "postgresql_mysql_kafka" not in catalog.planned
    assert "bitbucket_pipelines_github_actions_jenkins" not in catalog.planned
    assert "xray_testrail_spreadsheet" not in catalog.planned
    assert "bruno_postman" not in catalog.planned


def test_legacy_core_config_names_resolve_to_canonical_models() -> None:
    with pytest.warns(DeprecationWarning):
        from qa_mcp_hub.core.models import Connection as LegacyConnection
    with pytest.warns(DeprecationWarning):
        from qa_mcp_hub.core.models import HubConfig as LegacyHubConfig
    with pytest.warns(DeprecationWarning):
        from qa_mcp_hub.core.models import Profile as LegacyProfile

    assert LegacyConnection is ConnectionConfig
    assert LegacyHubConfig is HubConfig
    assert LegacyProfile is ProfileConfig


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
