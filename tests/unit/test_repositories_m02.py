"""Milestone 02 repository registration, discovery, metadata, and CLI tests."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError
from typer.testing import CliRunner

from qa_mcp_hub.auth.models import (
    AuthKind,
    CredentialReference,
    CredentialScope,
    CredentialStoreKind,
)
from qa_mcp_hub.cli import app
from qa_mcp_hub.config.models import (
    CURRENT_SCHEMA_VERSION,
    ConnectionConfig,
    DeploymentKind,
    HubConfig,
    ProfileConfig,
    QAWorkspaceReference,
    RepositoryReference,
)
from qa_mcp_hub.config.writer import save_config
from qa_mcp_hub.core.enums import IndexingPermission
from qa_mcp_hub.core.errors import RepositoryRegistryError
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.repositories.discovery import discover_local_repositories
from qa_mcp_hub.repositories.git_metadata import read_git_metadata, redact_git_url
from qa_mcp_hub.repositories.index_coordinator import plan_index
from qa_mcp_hub.repositories.registry import (
    list_repositories,
    register_repository,
    remove_repository,
)
from qa_mcp_hub.repositories.validator import validate_repository
from qa_mcp_hub.security.path_allowlist import logically_contained

runner = CliRunner()


def _git(repo: Path, *args: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        pytest.skip("git is not available")
    completed = subprocess.run(  # noqa: S603 - test invokes git with a fixed argument list
        [executable, "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.fail(completed.stderr)
    return completed.stdout.strip()


def _checkout(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    executable = shutil.which("git")
    if executable is None:
        pytest.skip("git is not available")
    subprocess.run(  # noqa: S603 - test invokes git init with a fixed argument list
        [executable, "init", "-b", "main", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(path, "config", "user.email", "qa@example.invalid")
    _git(path, "config", "user.name", "QA")
    (path / "README.txt").write_text("hello\n", encoding="utf-8")
    _git(path, "add", "README.txt")
    _git(path, "commit", "-m", "initial")
    return path


def _config(root: Path) -> HubConfig:
    return HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={
            "alpha": ProfileConfig(
                workspace_id="alpha-workspace",
                connection_ids=("github-alpha",),
            ),
            "beta": ProfileConfig(
                workspace_id="beta-workspace",
                connection_ids=("github-beta",),
            ),
        },
        connections=(
            ConnectionConfig(
                id="github-alpha",
                provider=ProviderKind.github,
                deployment=DeploymentKind.CLOUD,
                base_url="https://api.github.com",
                account="alpha-user",
                auth_kind=AuthKind.pat,
                credential=CredentialReference(
                    store=CredentialStoreKind.environment,
                    reference="QA_MCP_ALPHA_TOKEN",
                    scope=CredentialScope(
                        profile="alpha",
                        provider=ProviderKind.github,
                        connection_id="github-alpha",
                        host="api.github.com",
                        account="alpha-user",
                    ),
                    kind=AuthKind.pat,
                ),
            ),
            ConnectionConfig(
                id="github-beta",
                provider=ProviderKind.github,
                deployment=DeploymentKind.CLOUD,
                base_url="https://api.github.com",
                account="beta-user",
            ),
        ),
        workspaces=(
            QAWorkspaceReference(id="alpha-workspace", path=str(root / "alpha")),
            QAWorkspaceReference(id="beta-workspace", path=str(root / "beta")),
        ),
    )


def test_logical_paths_cover_windows_macos_and_linux() -> None:
    assert logically_contained(
        r"C:\approved\repo",
        r"c:\approved",
        platform="win32",
    )
    assert not logically_contained(
        r"C:\approved\..\outside",
        r"C:\approved",
        platform="win32",
    )
    assert logically_contained(
        r"\\server\share\repo",
        r"\\server\share",
        platform="win32",
    )
    assert not logically_contained(
        r"\\other\share\repo",
        r"\\server\share",
        platform="win32",
    )
    assert logically_contained("/Approved/Repo", "/approved", platform="darwin")
    assert not logically_contained("/Approved/Repo", "/approved", platform="linux")
    assert not logically_contained("/approved/../../etc", "/approved", platform="linux")


def test_local_git_metadata_branch_commit_and_dirty_state(tmp_path: Path) -> None:
    repo = _checkout(tmp_path / "repo")
    metadata = read_git_metadata(repo, [tmp_path])
    assert metadata.branch == "main"
    assert metadata.detached is False
    assert metadata.dirty is False
    assert len(metadata.head_sha) == 40
    (repo / "README.txt").write_text("changed\n", encoding="utf-8")
    assert read_git_metadata(repo, [tmp_path]).dirty is True


def test_detached_head_and_redacted_remote(tmp_path: Path) -> None:
    repo = _checkout(tmp_path / "repo")
    _git(
        repo,
        "remote",
        "add",
        "origin",
        "https://user:qa_mcp_placeholder@github.com/example/repo.git",
    )
    _git(repo, "remote", "add", "upstream", "https://example.invalid/other.git")
    _git(repo, "checkout", "--detach")
    metadata = read_git_metadata(repo, [tmp_path])
    assert metadata.detached is True
    assert metadata.branch is None
    assert metadata.remote_url == "https://github.com/example/repo.git"
    assert "qa_mcp_placeholder" not in (metadata.remote_url or "")
    redacted = redact_git_url("git@github.com:example/repo.git")
    assert redacted == "github.com:example/repo.git"


def test_discovery_stays_inside_the_root_and_skips_secret_directories(
    tmp_path: Path,
) -> None:
    root = tmp_path / "approved"
    _checkout(root / "service")
    hidden = root / "secrets" / "hidden"
    _checkout(hidden)
    found = discover_local_repositories(root, approved_roots=[root])
    assert [Path(item.path).name for item in found] == ["service"]


def test_duplicate_and_ambiguous_repositories_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "alpha"
    repo = _checkout(root / "service")
    config = _config(tmp_path)
    first = RepositoryReference(
        id="service",
        display_name="Service",
        path=str(repo),
    )
    updated = register_repository(config, "alpha", first)
    with pytest.raises(RepositoryRegistryError, match="duplicate repository id"):
        register_repository(updated, "alpha", first)
    with pytest.raises(RepositoryRegistryError, match="duplicate repository path"):
        register_repository(
            updated,
            "alpha",
            RepositoryReference(id="other", display_name="Other", path=str(repo)),
        )
    with pytest.raises(ValidationError, match="ambiguous"):
        RepositoryReference(
            id="mixed",
            display_name="Mixed",
            path=str(repo),
            path_env="QA_MCP_SAMPLE_REPOSITORY_PATH",
        )


def test_profiles_do_not_share_repositories(tmp_path: Path) -> None:
    repo = _checkout(tmp_path / "alpha" / "service")
    config = register_repository(
        _config(tmp_path),
        "alpha",
        RepositoryReference(id="service", display_name="Service", path=str(repo)),
    )
    assert [item.id for item in list_repositories(config, "alpha")] == ["service"]
    assert list_repositories(config, "beta") == ()
    with pytest.raises(RepositoryRegistryError):
        remove_repository(config, "beta", "service")


def test_remote_definition_reports_missing_credential_without_a_network_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QA_MCP_ALPHA_TOKEN", raising=False)
    config = _config(tmp_path)
    updated = register_repository(
        config,
        "alpha",
        RepositoryReference(
            id="payments",
            display_name="Payments",
            remote="example/payments",
            connection_id="github-alpha",
        ),
    )
    report = validate_repository(updated, "alpha", "payments")
    assert report.ok is False
    assert report.provider_status == "NOT_IMPLEMENTED"
    assert report.issues[0].code == "credential_missing"
    assert "qa_mcp" not in report.model_dump_json()


def test_present_credential_still_does_not_claim_provider_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QA_MCP_ALPHA_TOKEN", "qa_mcp_present")
    config = register_repository(
        _config(tmp_path),
        "alpha",
        RepositoryReference(
            id="payments",
            display_name="Payments",
            remote="example/payments",
            connection_id="github-alpha",
        ),
    )
    report = validate_repository(config, "alpha", "payments")
    assert report.ok is True
    assert report.provider_status == "NOT_IMPLEMENTED"
    assert report.metadata is None
    assert "qa_mcp_present" not in report.model_dump_json()


def test_index_plan_does_not_read_repository_files(tmp_path: Path) -> None:
    repo = _checkout(tmp_path / "repo")
    (repo / ".env").write_text("qa_mcp_not_indexed\n", encoding="utf-8")
    reference = RepositoryReference(
        id="service",
        display_name="Service",
        path=str(repo),
        include=(".env", "src/**"),
        indexing=IndexingPermission.content,
    )
    plan = plan_index(reference, revision="a" * 40)
    rendered = plan.model_dump_json()
    assert plan.status == "NOT_EXECUTED"
    assert plan.reason == "registration_only_until_milestone_05"
    assert ".env" in plan.exclude
    assert ".env" not in plan.include
    assert "qa_mcp_not_indexed" not in rendered
    blocked = plan_index(
        reference.model_copy(update={"indexing": IndexingPermission.none}),
        revision=None,
    )
    assert blocked.reason == "indexing_not_permitted"


def test_repository_cli_add_list_discover_validate_and_remove(tmp_path: Path) -> None:
    root = tmp_path / "alpha"
    repo = _checkout(root / "service")
    config_path = tmp_path / "config.yaml"
    save_config(_config(tmp_path), config_path)
    common = ["--config", str(config_path)]
    added = runner.invoke(
        app,
        ["repositories", "add", "service", "--path", str(repo), *common],
    )
    assert added.exit_code == 0, added.output
    listed = runner.invoke(app, ["repositories", "list", *common])
    assert listed.exit_code == 0
    assert "service" in listed.output
    discovered = runner.invoke(
        app,
        ["repositories", "discover", "--root", str(root), *common],
    )
    assert discovered.exit_code == 0
    assert "service" in discovered.output
    assert "not registered" in discovered.output.casefold()
    validated = runner.invoke(app, ["repositories", "validate", "service", *common])
    assert validated.exit_code == 0, validated.output
    assert "Dirty: False" in validated.output
    assert "Provider API: not_applicable" in validated.output
    hidden = runner.invoke(
        app,
        ["repositories", "list", "--profile", "beta", *common],
    )
    assert hidden.exit_code == 0
    assert "service" not in hidden.output
    removed = runner.invoke(app, ["repositories", "remove", "service", *common])
    assert removed.exit_code == 0
    listed_again = runner.invoke(app, ["repositories", "list", *common])
    assert "service" not in listed_again.output
    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["repositories"] == []
