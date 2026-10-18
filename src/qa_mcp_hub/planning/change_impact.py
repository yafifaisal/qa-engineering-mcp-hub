"""Separate a remote committed revision from a local working tree.

Purpose: attach local HEAD and dirty state without replacing the remote SHA.
Milestone: 03
Status: IMPLEMENTED
Ownership: planning.change_impact
Dependencies: Change records, repository registry, and local Git metadata.
Expected tests: matching checkout, dirty tree, and no registered checkout.
"""

from pathlib import Path

from qa_mcp_hub.adapters.git.base import ChangeSet
from qa_mcp_hub.config.models import HubConfig
from qa_mcp_hub.core.errors import GitInspectionError, PathAllowlistError
from qa_mcp_hub.repositories.git_metadata import read_git_metadata
from qa_mcp_hub.repositories.registry import approved_roots, list_repositories


def with_local_checkout(
    change: ChangeSet, config: HubConfig, profile_id: str
) -> ChangeSet:
    """Record local HEAD when a registered checkout matches the remote slug."""
    roots = approved_roots(config, profile_id)
    match = _matching_path(config, profile_id, change.repository)
    if match is None or not roots:
        return change.model_copy(
            update={
                "local_head_sha": None,
                "local_dirty": None,
                "revisions_differ": None,
            }
        )
    try:
        metadata = read_git_metadata(Path(match), roots)
    except (GitInspectionError, PathAllowlistError, OSError):
        return change.model_copy(
            update={
                "local_head_sha": None,
                "local_dirty": None,
                "revisions_differ": None,
            }
        )
    return change.model_copy(
        update={
            "local_head_sha": metadata.head_sha,
            "local_dirty": metadata.dirty,
            "revisions_differ": metadata.head_sha != change.remote_head_sha,
        }
    )


def _matching_path(config: HubConfig, profile_id: str, repository: str) -> str | None:
    needle = repository.strip("/").lower()
    for item in list_repositories(config, profile_id):
        if item.path is None:
            continue
        remote = (item.remote or "").lower().rstrip("/")
        if remote.endswith(".git"):
            remote = remote[: -len(".git")]
        if remote.endswith(needle) or item.path.rstrip("/").lower().endswith(needle):
            return item.path
    return None
