"""Milestone 01 tests for versioned, profile-scoped configuration."""

import os
import stat
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from qa_mcp_hub.auth.models import (
    AuthKind,
    CredentialReference,
    CredentialScope,
    CredentialStoreKind,
)
from qa_mcp_hub.config import (
    ConfigLoadError,
    ConfigMigrationError,
    ConfigResolutionError,
    ConfigValidationError,
    ConnectionConfig,
    DeploymentKind,
    DuplicateKeyError,
    ExecutionOverrides,
    ExecutionPreferences,
    HubConfig,
    HubSettings,
    ProfileConfig,
    QAWorkspaceReference,
    RepositoryReference,
    default_config_dir,
    default_config_path,
    inspect_config,
    load_config,
    load_yaml_text,
    migrate_config,
    resolve_config,
    save_config,
    validate_config,
)
from qa_mcp_hub.core.models import ProviderKind


def _credential(
    connection_id: str = "github-primary",
    *,
    profile: str = "development",
) -> CredentialReference:
    return CredentialReference(
        store=CredentialStoreKind.environment,
        reference="QA_MCP_GITHUB_PAT",
        scope=CredentialScope(
            profile=profile,
            provider=ProviderKind.github,
            connection_id=connection_id,
            host="api.github.com",
            account="qa-user",
        ),
        kind=AuthKind.pat,
    )


def _config() -> HubConfig:
    return HubConfig(
        schema_version=1,
        active_profile="development",
        profiles={
            "development": ProfileConfig(
                workspace_id="qa-workspace",
                repository_ids=("service",),
                connection_ids=("github-primary", "github-secondary"),
                execution=ExecutionOverrides(
                    timeout_seconds=200,
                    dry_run=False,
                ),
                log_level="WARNING",
            )
        },
        connections=(
            ConnectionConfig(
                id="github-primary",
                provider=ProviderKind.github,
                deployment=DeploymentKind.CLOUD,
                base_url="https://api.github.com",
                account="qa-user",
                auth_kind=AuthKind.pat,
                credential=_credential(),
            ),
            ConnectionConfig(
                id="github-secondary",
                provider=ProviderKind.github,
                deployment=DeploymentKind.CLOUD,
                base_url="https://github.example.invalid",
            ),
        ),
        repositories=(
            RepositoryReference(
                id="service",
                display_name="Example service",
                path_env="QA_MCP_SERVICE_PATH",
                connection_id="github-primary",
            ),
        ),
        workspaces=(
            QAWorkspaceReference(id="qa-workspace", path="/work/qa-workspace"),
        ),
        execution=ExecutionPreferences(
            timeout_seconds=100,
            max_concurrency=2,
            dry_run=True,
            allow_mutations=True,
        ),
        log_level="INFO",
    )


def test_hub_settings_are_strict_and_trim_server_name() -> None:
    assert HubSettings(server_name="  QA Hub  ").server_name == "QA Hub"
    with pytest.raises(ValidationError):
        HubSettings(server_name="   ")
    with pytest.raises(ValidationError):
        HubSettings(unknown_option=True)


def test_version_and_unknown_provider_are_strict() -> None:
    document = _config().model_dump(mode="json")
    document.pop("schema_version")
    with pytest.raises(ValidationError):
        HubConfig.model_validate(document)

    document["schema_version"] = 1
    document["connections"][0]["provider"] = "unknown-provider"
    with pytest.raises(ValidationError):
        HubConfig.model_validate(document)


def test_duplicate_provider_instances_are_supported() -> None:
    config = _config()
    assert [connection.provider for connection in config.connections] == [
        ProviderKind.github,
        ProviderKind.github,
    ]


def test_duplicate_ids_and_invalid_references_are_rejected() -> None:
    config = _config()
    duplicate = config.model_dump(mode="python")
    duplicate["connections"] = [duplicate["connections"][0]] * 2
    with pytest.raises(ValidationError, match="duplicate connection id"):
        HubConfig.model_validate(duplicate)

    missing = config.model_dump(mode="python")
    missing["profiles"]["development"]["connection_ids"] = ["missing"]
    with pytest.raises(ValidationError, match="unknown connection"):
        HubConfig.model_validate(missing)

    missing["profiles"]["development"]["connection_ids"] = []
    missing["active_profile"] = "missing"
    with pytest.raises(ValidationError, match="active profile"):
        HubConfig.model_validate(missing)


def test_connection_and_credential_are_profile_isolated() -> None:
    document = _config().model_dump(mode="python")
    document["profiles"]["other"] = {
        "connection_ids": ["github-primary"],
        "repository_ids": [],
    }
    with pytest.raises(ValidationError, match="cannot be shared"):
        HubConfig.model_validate(document)

    document = _config().model_dump(mode="python")
    document["connections"][0]["credential"]["scope"]["profile"] = "other"
    with pytest.raises(ValidationError, match="credential scope"):
        HubConfig.model_validate(document)


def test_incomplete_authenticated_connection_is_valid_but_none_auth_is_safe() -> None:
    incomplete = ConnectionConfig(
        id="jira-primary",
        provider=ProviderKind.jira,
        deployment=DeploymentKind.CLOUD,
        base_url="https://example.atlassian.net",
        auth_kind=AuthKind.api_token,
    )
    assert incomplete.credential is None

    with pytest.raises(ValidationError, match="must be absent"):
        ConnectionConfig(
            id="github-primary",
            provider=ProviderKind.github,
            deployment=DeploymentKind.CLOUD,
            auth_kind=AuthKind.none,
            credential=_credential(),
        )


def test_yaml_duplicate_keys_and_malformed_input_are_rejected_without_values() -> None:
    with pytest.raises(DuplicateKeyError) as duplicate:
        load_yaml_text("schema_version: 1\nschema_version: 1\n")
    assert "duplicate" in str(duplicate.value)

    sensitive_marker = "do-not-repeat-this-value"
    with pytest.raises(ConfigLoadError) as malformed:
        load_yaml_text(f"schema_version: [\n  {sensitive_marker}\n")
    assert sensitive_marker not in str(malformed.value)


def test_yaml_save_load_roundtrip_and_owner_permissions(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.yaml"
    saved_path = save_config(_config(), path)
    assert saved_path == path
    assert load_config(path) == _config()
    assert "QA_MCP_GITHUB_PAT" in path.read_text(encoding="utf-8")
    assert "do-not-store-a-token" not in path.read_text(encoding="utf-8")
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert not list(path.parent.glob("*.tmp"))


def test_plaintext_secret_fields_are_rejected_without_echoing_values() -> None:
    sensitive_marker = "a-secret-that-must-not-appear"
    document = _config().model_dump(mode="python")
    document["token"] = sensitive_marker
    report = inspect_config(document)
    assert not report.valid
    assert report.issues[0].code == "plaintext_secret_field"
    with pytest.raises(ConfigValidationError) as error:
        validate_config(document)
    assert sensitive_marker not in str(error.value)


def test_configuration_precedence_and_provenance() -> None:
    resolved = resolve_config(
        _config(),
        explicit={
            "active_profile": "development",
            "timeout_seconds": 400,
            "workspace_path": "/explicit/workspace",
        },
        environ={
            "QA_MCP_ACTIVE_PROFILE": "ignored-by-explicit",
            "QA_MCP_TIMEOUT_SECONDS": "300",
            "QA_MCP_MAX_CONCURRENCY": "3",
            "QA_MCP_LOG_LEVEL": "ERROR",
        },
    )
    assert resolved.active_profile == "development"
    assert resolved.workspace_path == "/explicit/workspace"
    assert resolved.execution.timeout_seconds == 400
    assert resolved.execution.max_concurrency == 3
    assert resolved.execution.dry_run is False
    assert resolved.execution.allow_mutations is True
    assert resolved.log_level == "ERROR"
    sources = {item.field: item.source.value for item in resolved.provenance}
    assert sources == {
        "active_profile": "explicit",
        "workspace_path": "explicit",
        "timeout_seconds": "explicit",
        "max_concurrency": "environment",
        "dry_run": "profile",
        "allow_mutations": "user",
        "log_level": "environment",
    }


def test_resolution_rejects_missing_profiles_and_bad_overrides() -> None:
    config = HubConfig(schema_version=1)
    with pytest.raises(ConfigResolutionError, match="no active profile"):
        resolve_config(config, environ={})
    with pytest.raises(ConfigResolutionError, match="unknown option"):
        resolve_config(_config(), explicit={"secret": "forbidden"}, environ={})
    with pytest.raises(ConfigResolutionError, match="integer"):
        resolve_config(
            _config(),
            environ={"QA_MCP_TIMEOUT_SECONDS": "not-an-integer"},
        )


def test_resolved_snapshot_is_detached_and_frozen() -> None:
    config = _config()
    resolved = resolve_config(config, environ={})
    config.profiles["development"] = ProfileConfig()
    assert resolved.profile.connection_ids == (
        "github-primary",
        "github-secondary",
    )
    with pytest.raises(ValidationError):
        resolved.execution.timeout_seconds = 1  # type: ignore[misc]


def test_v0_migration_creates_backup_and_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    legacy = _config().model_dump(mode="json")
    legacy.pop("schema_version")
    legacy["version"] = 0
    path.write_text(yaml.safe_dump(legacy, sort_keys=False), encoding="utf-8")
    original = path.read_text(encoding="utf-8")

    first = migrate_config(path)
    assert first.migrated
    assert first.backup_path is not None
    assert first.backup_path.read_text(encoding="utf-8") == original
    assert load_config(path) == _config()

    migrated_text = path.read_text(encoding="utf-8")
    second = migrate_config(path)
    assert not second.migrated
    assert second.backup_path is None
    assert path.read_text(encoding="utf-8") == migrated_text


def test_failed_migration_restores_original(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    legacy = _config().model_dump(mode="json")
    legacy.pop("schema_version")
    original = yaml.safe_dump(legacy, sort_keys=False)
    path.write_text(original, encoding="utf-8")

    def fail_after_partial_write(target: Path, text: str) -> None:
        del text
        target.write_text("partial", encoding="utf-8")
        raise OSError("simulated write failure")

    with pytest.raises(ConfigMigrationError, match="restored"):
        migrate_config(path, write_target=fail_after_partial_write)
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("win32", Path("AppData/Roaming/qa-mcp-hub/config.yaml")),
        ("darwin", Path("Library/Application Support/qa-mcp-hub/config.yaml")),
        ("linux", Path(".config/qa-mcp-hub/config.yaml")),
    ],
)
def test_cross_platform_config_file_paths(platform: str, expected: Path) -> None:
    home = Path("/person")
    assert (
        default_config_path(home=home, platform=platform, environ={}) == home / expected
    )


def test_native_path_requests_roaming_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_user_config_path(
        appname: str,
        *,
        appauthor: bool,
        roaming: bool,
        ensure_exists: bool,
    ) -> Path:
        captured.update(
            appname=appname,
            appauthor=appauthor,
            roaming=roaming,
            ensure_exists=ensure_exists,
        )
        return Path("/native/config")

    monkeypatch.setattr(
        "qa_mcp_hub.config.paths.user_config_path",
        fake_user_config_path,
    )
    assert default_config_dir() == Path("/native/config")
    assert captured["roaming"] is True
