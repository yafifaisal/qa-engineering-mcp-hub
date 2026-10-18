"""Validate a registered repository before anyone treats it as readable.

Purpose: check allowlists, local Git metadata, and credential presence.
Milestone: 02
Status: IMPLEMENTED
Ownership: repositories.validator
Dependencies: Repository models, path allowlist, Git metadata, and provider contracts.
Expected tests: missing roots, unsafe paths, remote mismatch, and diagnostic stability.
"""

import os
from pathlib import Path

from qa_mcp_hub.auth.credential_resolver import CredentialResolver
from qa_mcp_hub.auth.credential_store import (
    CredentialError,
    CredentialNotFoundError,
    CredentialStoreUnavailableError,
)
from qa_mcp_hub.auth.environment_store import EnvironmentCredentialStore
from qa_mcp_hub.auth.keyring_store import KeyringCredentialStore
from qa_mcp_hub.auth.models import AuthKind, CredentialReference, CredentialStoreKind
from qa_mcp_hub.config.models import HubConfig, RepositoryReference
from qa_mcp_hub.core.errors import (
    GitInspectionError,
    PathAllowlistError,
    RepositoryRegistryError,
)
from qa_mcp_hub.repositories.git_metadata import read_git_metadata
from qa_mcp_hub.repositories.models import (
    GitMetadata,
    RepositoryValidation,
    ValidationIssue,
)
from qa_mcp_hub.repositories.registry import (
    approved_roots,
    effective_excludes,
    get_repository,
)
from qa_mcp_hub.security.path_allowlist import resolve_within


def validate_repository(
    config: HubConfig,
    profile_id: str,
    repository_id: str,
    *,
    resolver: CredentialResolver | None = None,
    environ: dict[str, str] | None = None,
) -> RepositoryValidation:
    """Validate one profile-owned repository. Remote APIs are not called."""
    repository = get_repository(config, profile_id, repository_id)
    issues: list[ValidationIssue] = []
    metadata: GitMetadata | None = None
    provider_status = "not_applicable"
    roots = approved_roots(config, profile_id)
    if repository.path is not None:
        metadata = _validate_local(repository.path, roots, issues)
    elif repository.path_env is not None:
        metadata = _validate_env_path(repository.path_env, roots, issues, environ)
    if repository.remote is not None or (
        repository.path is None and repository.path_env is None
    ):
        provider_status = "NOT_IMPLEMENTED"
        _validate_remote(config, profile_id, repository, issues, resolver)
    elif repository.connection_id is not None:
        provider_status = "NOT_IMPLEMENTED"
        _validate_remote(config, profile_id, repository, issues, resolver)
    return RepositoryValidation(
        repository_id=repository.id,
        ok=not issues,
        issues=tuple(issues),
        metadata=metadata,
        provider_status=provider_status,
        protected_patterns=effective_excludes(repository.exclude),
    )


def _validate_local(
    raw_path: str,
    roots: tuple[Path, ...],
    issues: list[ValidationIssue],
) -> GitMetadata | None:
    try:
        resolved = resolve_within(Path(raw_path), roots)
        return read_git_metadata(resolved, roots)
    except (PathAllowlistError, GitInspectionError) as exc:
        issues.append(ValidationIssue(code=exc.code, message=exc.message))
        return None


def _validate_env_path(
    name: str,
    roots: tuple[Path, ...],
    issues: list[ValidationIssue],
    environ: dict[str, str] | None,
) -> GitMetadata | None:
    source = os.environ if environ is None else environ
    raw_path = source.get(name)
    if not raw_path:
        issues.append(
            ValidationIssue(
                code="path_missing",
                message=f"environment variable {name} is not set",
            )
        )
        return None
    return _validate_local(raw_path, roots, issues)


def _validate_remote(
    config: HubConfig,
    profile_id: str,
    repository: RepositoryReference,
    issues: list[ValidationIssue],
    resolver: CredentialResolver | None,
) -> None:
    if repository.connection_id is None:
        issues.append(
            ValidationIssue(
                code="connection_missing",
                message="remote repository requires a connection reference",
            )
        )
        return
    profile = config.profiles[profile_id]
    if repository.connection_id not in profile.connection_ids:
        raise RepositoryRegistryError("connection is not available in this profile")
    connection = next(
        item for item in config.connections if item.id == repository.connection_id
    )
    if connection.credential is None or connection.auth_kind is AuthKind.none:
        issues.append(
            ValidationIssue(
                code="credential_missing",
                message="remote connection has no credential reference",
            )
        )
        return
    if connection.credential.store is CredentialStoreKind.oauth_reference:
        issues.append(
            ValidationIssue(
                code="oauth_not_implemented",
                message="OAuth provider flow is NOT_IMPLEMENTED.",
            )
        )
        return
    active_resolver = resolver or _resolver_for(connection.credential)
    try:
        resolved = active_resolver.resolve(connection.credential)
    except CredentialNotFoundError:
        issues.append(
            ValidationIssue(
                code="credential_missing",
                message="Credential is missing from the configured backend.",
            )
        )
        return
    except CredentialStoreUnavailableError:
        issues.append(
            ValidationIssue(
                code="credential_store_unavailable",
                message="credential store is unavailable",
            )
        )
        return
    except CredentialError:
        issues.append(
            ValidationIssue(
                code="credential_missing",
                message="Credential is missing from the configured backend.",
            )
        )
        return
    del resolved


def _resolver_for(reference: CredentialReference) -> CredentialResolver:
    if reference.store is CredentialStoreKind.environment:
        store: EnvironmentCredentialStore | KeyringCredentialStore = (
            EnvironmentCredentialStore(allowed_names={reference.reference})
        )
    elif reference.store is CredentialStoreKind.keyring:
        store = KeyringCredentialStore()
    else:
        raise CredentialError("credential backend is not configured")
    return CredentialResolver([store])
