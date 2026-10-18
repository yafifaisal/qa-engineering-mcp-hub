"""Coordination record for a future indexer. This module does not index.

Purpose: turn an explicit indexing permission into a plan Milestone 05 can execute.
Milestone: 02
Status: IMPLEMENTED
Ownership: repositories.index_coordinator
Dependencies: Repository registry, knowledge indexer, freshness, and storage contracts.
Expected tests: revision pinning, deduplication, cancellation, freshness, and isolation.
"""

from qa_mcp_hub.config.models import RepositoryReference
from qa_mcp_hub.core.policies import authorize_indexing
from qa_mcp_hub.repositories.models import IndexPlan
from qa_mcp_hub.repositories.registry import effective_excludes, effective_includes


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
