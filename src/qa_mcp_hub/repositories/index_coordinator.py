"""Plan an index, and execute one when the caller asks.

Purpose: keep the Milestone 02 plan record, and index when execution is requested.
Milestone: 05
Status: IMPLEMENTED
Ownership: repositories.index_coordinator
Dependencies: Repository registry, knowledge indexer, and the index store.
Expected tests: revision pinning, permission denial, and secret exclusion.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from qa_mcp_hub.config.models import RepositoryReference
from qa_mcp_hub.core.errors import HubError, PathAllowlistError
from qa_mcp_hub.core.policies import authorize_indexing
from qa_mcp_hub.knowledge.indexer import index_repository
from qa_mcp_hub.knowledge.models import IndexManifest
from qa_mcp_hub.repositories.models import IndexPlan
from qa_mcp_hub.repositories.registry import effective_excludes, effective_includes
from qa_mcp_hub.security.path_allowlist import resolve_within
from qa_mcp_hub.storage.index_store import IndexStore


def plan_index(
    repository: RepositoryReference,
    *,
    revision: str | None,
) -> IndexPlan:
    """Record an indexing plan. File contents are not read."""
    decision = authorize_indexing(repository.indexing)
    if not decision.permitted:
        return IndexPlan(
            repository_id=repository.id,
            revision=revision,
            permission=repository.indexing,
            include=(),
            exclude=effective_excludes(repository.exclude),
            status="NOT_EXECUTED",
            reason=decision.reason,
        )
    return IndexPlan(
        repository_id=repository.id,
        revision=revision,
        permission=repository.indexing,
        include=effective_includes(repository.include, repository.exclude),
        exclude=effective_excludes(repository.exclude),
        status="NOT_EXECUTED",
        reason=decision.reason,
    )


def execute_index(
    repository: RepositoryReference,
    *,
    profile_id: str,
    roots: tuple[Path, ...],
    store: IndexStore,
    clock: Callable[[], datetime] | None = None,
) -> IndexManifest:
    """Index one checkout when the profile granted permission. Plans stay plans."""
    decision = authorize_indexing(repository.indexing)
    if not decision.permitted:
        raise HubError("indexing_not_permitted", decision.reason)
    if repository.path is None:
        raise HubError("local_checkout_required", "indexing requires a local checkout")
    try:
        root = resolve_within(Path(repository.path), roots)
    except PathAllowlistError as exc:
        raise HubError("outside_workspace", exc.message) from exc
    return index_repository(
        repository,
        profile_id=profile_id,
        root=root,
        store=store,
        clock=clock,
    )
