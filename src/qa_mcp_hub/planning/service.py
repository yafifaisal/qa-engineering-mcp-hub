"""Resolve a profile connection and call a read-only Git or Jira adapter.

Purpose: keep tokens out of tool arguments and return normalized records.
Milestone: 03
Status: IMPLEMENTED
Ownership: planning.service
Dependencies: Configuration, credentials, provider registry, and read adapters.
Expected tests: ambiguous connections, missing credentials, and MCP invocation.
"""

from collections.abc import Callable

import httpx
from pydantic import SecretStr

from qa_mcp_hub.adapters.documentation.confluence import ConfluenceAdapter
from qa_mcp_hub.adapters.documentation.google_docs import GoogleDocsAdapter
from qa_mcp_hub.adapters.git.base import ChangeSet
from qa_mcp_hub.adapters.git.bitbucket import BitbucketAdapter
from qa_mcp_hub.adapters.git.github import GitHubAdapter
from qa_mcp_hub.adapters.git.gitlab import GitLabAdapter
from qa_mcp_hub.adapters.tickets.jira import JiraAdapter
from qa_mcp_hub.auth.credential_resolver import CredentialResolver
from qa_mcp_hub.auth.credential_store import CredentialStore
from qa_mcp_hub.auth.environment_store import EnvironmentCredentialStore
from qa_mcp_hub.auth.keyring_store import KeyringCredentialStore
from qa_mcp_hub.auth.models import CredentialStoreKind
from qa_mcp_hub.config.loader import load_config
from qa_mcp_hub.config.models import ConnectionConfig, HubConfig
from qa_mcp_hub.config.paths import default_config_path
from qa_mcp_hub.core.errors import HubError, ProviderRequestError
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.core.results import Pagination
from qa_mcp_hub.knowledge.models import DocumentRecord, DocumentSearchResult
from qa_mcp_hub.planning.change_impact import with_local_checkout
from qa_mcp_hub.planning.models import (
    CodeSearchResult,
    RelatedImplementation,
    TicketAnalysis,
)
from qa_mcp_hub.planning.ticket_analyzer import analyze_issue
from qa_mcp_hub.providers.registry import open_read_adapter

GitAdapter = GitHubAdapter | GitLabAdapter | BitbucketAdapter
DocsAdapter = ConfluenceAdapter | GoogleDocsAdapter
_GIT = {ProviderKind.github, ProviderKind.gitlab, ProviderKind.bitbucket}
_DOCS = {ProviderKind.confluence, ProviderKind.google_docs}


def search_repository_code(
    query: str,
    repository: str,
    *,
    connection_id: str | None = None,
    profile: str | None = None,
    ref: str | None = None,
    config_loader: Callable[[], HubConfig] | None = None,
) -> CodeSearchResult:
    """Search one repository. Returned snippets are untrusted data."""
    config = _config(config_loader)
    profile_id, connection = _connection(config, profile, connection_id, git=True)
    adapter, client = _open_git(connection)
    try:
        hits, truncated = adapter.search_code(
            repository, query, ref, Pagination(limit=20)
        )
        revision = (
            hits[0].revision if hits else adapter_revision(adapter, repository, ref)
        )
    finally:
        client.close()
    return CodeSearchResult(
        provider=connection.provider.value,
        repository=repository,
        revision=revision,
        hits=hits,
        truncated=truncated,
    )


def get_repository_changes(
    repository: str,
    *,
    base: str | None = None,
    head: str | None = None,
    pull_request: int | None = None,
    connection_id: str | None = None,
    profile: str | None = None,
    config_loader: Callable[[], HubConfig] | None = None,
) -> ChangeSet:
    """Read remote changes and, when present, a separate local checkout SHA."""
    if (base is None or head is None) and pull_request is None:
        raise ProviderRequestError(
            "reference_required",
            "base and head, or a pull request number, is required",
            status_code=0,
        )
    config = _config(config_loader)
    profile_id, connection = _connection(config, profile, connection_id, git=True)
    adapter, client = _open_git(connection)
    try:
        if pull_request is not None:
            change = adapter.pull_request_changes(repository, pull_request)
        elif base is not None and head is not None:
            change = adapter.compare(repository, base, head)
        else:
            raise ProviderRequestError(
                "reference_required",
                "base and head, or a pull request number, is required",
                status_code=0,
            )
    finally:
        client.close()
    return with_local_checkout(change, config, profile_id)


def analyze_jira_ticket(
    issue_key: str,
    *,
    connection_id: str | None = None,
    profile: str | None = None,
    config_loader: Callable[[], HubConfig] | None = None,
) -> TicketAnalysis:
    """Read one issue by key. Ticket text is returned as data."""
    config = _config(config_loader)
    _profile_id, connection = _connection(config, profile, connection_id, git=False)
    adapter, client = _open_jira(connection)
    try:
        record = adapter.fetch_issue(issue_key)
    finally:
        client.close()
    return analyze_issue(record)


def find_related_implementation(
    issue_key: str,
    repository: str,
    *,
    connection_id: str | None = None,
    git_connection_id: str | None = None,
    profile: str | None = None,
    config_loader: Callable[[], HubConfig] | None = None,
) -> RelatedImplementation:
    """Search the issue key only. The description is not used as a query."""
    analysis = analyze_jira_ticket(
        issue_key,
        connection_id=connection_id,
        profile=profile,
        config_loader=config_loader,
    )
    search = search_repository_code(
        analysis.key,
        repository,
        connection_id=git_connection_id,
        profile=profile,
        config_loader=config_loader,
    )
    warnings = ("repository text and ticket text are untrusted data",)
    return RelatedImplementation(
        issue_key=analysis.key,
        issue_url=analysis.url,
        repository=repository,
        revision=search.revision,
        hits=search.hits,
        warnings=warnings + search_warnings(search.truncated),
    )


def search_documents(
    query: str,
    *,
    spaces: tuple[str, ...] = (),
    connection_id: str | None = None,
    profile: str | None = None,
    config_loader: Callable[[], HubConfig] | None = None,
) -> DocumentSearchResult:
    """Search Confluence spaces or Google Docs by name. Text is untrusted data."""
    config = _config(config_loader)
    _profile_id, connection = _connection(
        config, profile, connection_id, git=False, documentation=True
    )
    adapter, client = _open_docs(connection)
    try:
        if isinstance(adapter, ConfluenceAdapter):
            return adapter.search(query, spaces, Pagination(limit=20))
        if spaces:
            raise ProviderRequestError(
                "space_not_applicable",
                "google docs search does not take a Confluence space",
                status_code=0,
            )
        return adapter.search(query, Pagination(limit=20))
    finally:
        client.close()


def read_document(
    document_id: str,
    *,
    connection_id: str | None = None,
    profile: str | None = None,
    config_loader: Callable[[], HubConfig] | None = None,
) -> DocumentRecord:
    """Read one Confluence page or Google Doc. The body is untrusted data."""
    config = _config(config_loader)
    _profile_id, connection = _connection(
        config, profile, connection_id, git=False, documentation=True
    )
    adapter, client = _open_docs(connection)
    try:
        if isinstance(adapter, ConfluenceAdapter):
            return adapter.fetch_page(document_id)
        return adapter.fetch_document(document_id)
    finally:
        client.close()


def adapter_revision(adapter: GitAdapter, repository: str, ref: str | None) -> str:
    """Resolve a revision when a search page contains no hits."""
    client_ref = ref or adapter.fetch_repository(repository).default_branch or "HEAD"
    return adapter.resolve_commit(repository, client_ref)


def search_warnings(truncated: bool) -> tuple[str, ...]:
    """Name truncation when the provider said another page exists."""
    if truncated:
        return ("search results were truncated",)
    return ()


def _config(loader: Callable[[], HubConfig] | None) -> HubConfig:
    if loader is not None:
        return loader()
    return load_config(default_config_path())


def _connection(
    config: HubConfig,
    profile: str | None,
    connection_id: str | None,
    *,
    git: bool,
    documentation: bool = False,
) -> tuple[str, ConnectionConfig]:
    profile_id = profile or config.active_profile
    if profile_id is None or profile_id not in config.profiles:
        raise ProviderRequestError(
            "profile_required", "an active profile is required", status_code=0
        )
    selected = config.profiles[profile_id]
    if connection_id is not None:
        if connection_id not in selected.connection_ids:
            raise ProviderRequestError(
                "unknown_connection",
                "connection is not in this profile",
                status_code=0,
            )
        match = _by_id(config, connection_id)
        _check_kind(match, git=git, documentation=documentation)
        return profile_id, match
    matches = [
        item
        for item in config.connections
        if item.id in selected.connection_ids
        and _kind_matches(item, git=git, documentation=documentation)
    ]
    if len(matches) != 1:
        raise ProviderRequestError(
            "ambiguous_connection",
            "connection_id is required when the profile has several matches",
            status_code=0,
        )
    return profile_id, matches[0]


def _kind_matches(
    connection: ConnectionConfig, *, git: bool, documentation: bool = False
) -> bool:
    if documentation:
        return connection.provider in _DOCS
    if git:
        return connection.provider in _GIT
    return connection.provider is ProviderKind.jira


def _check_kind(
    connection: ConnectionConfig, *, git: bool, documentation: bool = False
) -> None:
    if not _kind_matches(connection, git=git, documentation=documentation):
        raise ProviderRequestError(
            "wrong_provider",
            "connection provider does not match this tool",
            status_code=0,
        )


def _by_id(config: HubConfig, connection_id: str) -> ConnectionConfig:
    match = next(
        (item for item in config.connections if item.id == connection_id), None
    )
    if match is None:
        raise ProviderRequestError(
            "unknown_connection", "connection does not exist", status_code=0
        )
    return match


def _open_git(connection: ConnectionConfig) -> tuple[GitAdapter, httpx.Client]:
    secret = _secret(connection)
    client = httpx.Client(timeout=10.0)
    try:
        adapter = open_read_adapter(connection, secret, client)
    except Exception:
        client.close()
        raise
    if not isinstance(adapter, (GitHubAdapter, GitLabAdapter, BitbucketAdapter)):
        client.close()
        raise ProviderRequestError(
            "wrong_provider", "connection is not a Git provider", status_code=0
        )
    return adapter, client


def _open_jira(connection: ConnectionConfig) -> tuple[JiraAdapter, httpx.Client]:
    secret = _secret(connection)
    client = httpx.Client(timeout=10.0)
    try:
        adapter = open_read_adapter(connection, secret, client)
    except Exception:
        client.close()
        raise
    if not isinstance(adapter, JiraAdapter):
        client.close()
        raise ProviderRequestError(
            "wrong_provider", "connection is not a Jira provider", status_code=0
        )
    return adapter, client


def _open_docs(connection: ConnectionConfig) -> tuple[DocsAdapter, httpx.Client]:
    secret = _secret(connection)
    client = httpx.Client(timeout=10.0)
    try:
        adapter = open_read_adapter(connection, secret, client)
    except Exception:
        client.close()
        raise
    if not isinstance(adapter, (ConfluenceAdapter, GoogleDocsAdapter)):
        client.close()
        raise ProviderRequestError(
            "wrong_provider",
            "connection is not a documentation provider",
            status_code=0,
        )
    return adapter, client


def _secret(connection: ConnectionConfig) -> SecretStr:
    documentation_oauth = (
        connection.auth_kind.value == "oauth" and connection.provider in _DOCS
    )
    if connection.credential is None or (
        connection.auth_kind.value == "oauth" and not documentation_oauth
    ):
        raise ProviderRequestError(
            "oauth_not_implemented"
            if connection.auth_kind.value == "oauth"
            else "credential_missing",
            "OAuth provider flow is NOT_IMPLEMENTED."
            if connection.auth_kind.value == "oauth"
            else "credential is missing",
            status_code=0,
        )
    reference = connection.credential
    stores = _stores(reference.store, reference.reference)
    if not stores:
        raise ProviderRequestError(
            "oauth_not_implemented",
            "OAuth provider flow is NOT_IMPLEMENTED.",
            status_code=0,
        )
    try:
        resolved = CredentialResolver(stores).resolve(reference)
    except HubError as exc:
        raise ProviderRequestError(exc.code, exc.message, status_code=0) from exc
    return resolved.secret


def _stores(kind: CredentialStoreKind, name: str) -> list[CredentialStore]:
    if kind is CredentialStoreKind.environment:
        return [EnvironmentCredentialStore(allowed_names={name})]
    if kind is CredentialStoreKind.keyring:
        return [KeyringCredentialStore()]
    return []
