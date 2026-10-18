"""Path, symlink, and profile-boundary tests for repository registration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from qa_mcp_hub.config.models import (
    CURRENT_SCHEMA_VERSION,
    ConnectionConfig,
    DeploymentKind,
    HubConfig,
    ProfileConfig,
    QAWorkspaceReference,
    RepositoryReference,
)
from qa_mcp_hub.core.errors import PathAllowlistError, RepositoryRegistryError
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.repositories.discovery import discover_local_repositories
from qa_mcp_hub.repositories.registry import register_repository
from qa_mcp_hub.security.path_allowlist import resolve_within


def _config(root: Path) -> HubConfig:
    return HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={
            "alpha": ProfileConfig(workspace_id="alpha-workspace"),
        },
        connections=(
            ConnectionConfig(
                id="github-alpha",
                provider=ProviderKind.github,
                deployment=DeploymentKind.CLOUD,
                base_url="https://api.github.com",
            ),
        ),
        workspaces=(QAWorkspaceReference(id="alpha-workspace", path=str(root)),),
    )


def test_registration_rejects_traversal_outside_the_workspace(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    escaped = root / ".." / "outside"
    with pytest.raises(PathAllowlistError):
        register_repository(
            _config(root),
            "alpha",
            RepositoryReference(
                id="escaped", display_name="Escaped", path=str(escaped)
            ),
        )
    with pytest.raises(PathAllowlistError):
        resolve_within(Path("approved\x00repo"), [root])


def test_symlink_to_another_tree_is_not_an_approved_repository(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / ".git").mkdir()
    link = root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("this platform cannot create a directory symlink")
    found = discover_local_repositories(root, approved_roots=[root])
    assert found == ()
    with pytest.raises(PathAllowlistError):
        register_repository(
            _config(root),
            "alpha",
            RepositoryReference(id="escape", display_name="Escape", path=str(link)),
        )


def test_repository_cannot_use_another_profiles_connection(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    root.mkdir()
    config = HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={
            "alpha": ProfileConfig(workspace_id="alpha-workspace"),
            "beta": ProfileConfig(connection_ids=("github-beta",)),
        },
        connections=(
            ConnectionConfig(
                id="github-beta",
                provider=ProviderKind.github,
                deployment=DeploymentKind.CLOUD,
                base_url="https://api.github.com",
            ),
        ),
        workspaces=(QAWorkspaceReference(id="alpha-workspace", path=str(root)),),
    )
    with pytest.raises(RepositoryRegistryError, match="not available"):
        register_repository(
            config,
            "alpha",
            RepositoryReference(
                id="payments",
                display_name="Payments",
                remote="example/payments",
                connection_id="github-beta",
            ),
        )


def test_patterns_and_remote_urls_cannot_carry_traversal_or_userinfo() -> None:
    with pytest.raises(ValidationError):
        RepositoryReference(
            id="service",
            display_name="Service",
            path="/work/service",
            include=("../secrets",),
        )
    with pytest.raises(ValidationError):
        RepositoryReference(
            id="service",
            display_name="Service",
            remote="https://user:qa_mcp_placeholder@github.com/example/repo.git",
            connection_id="github-alpha",
        )
