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
from qa_mcp_hub.core.enums import EpistemicStatus
from qa_mcp_hub.core.errors import GitInspectionError, PathAllowlistError
from qa_mcp_hub.knowledge.models import DependencyEdge, SymbolRecord
from qa_mcp_hub.planning.models import ImpactFinding, ImpactReport
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


def analyze_change_impact(
    repository_id: str,
    paths: list[str] | None = None,
    profile: str | None = None,
) -> ImpactReport:
    """Describe source references touched by the named paths. Tests are not run."""
    from qa_mcp_hub.knowledge.service import open_engine

    engine = open_engine()
    try:
        selected = tuple(paths) if paths is not None else None
        return engine.analyze_impact(repository_id, selected, profile)
    finally:
        engine.close()


def build_impact(
    repository_id: str,
    paths: tuple[str, ...],
    symbols: tuple[SymbolRecord, ...],
    edges: tuple[DependencyEdge, ...],
) -> ImpactReport:
    """Build findings from symbols and edges that touch the changed paths."""
    path_set = set(paths)
    findings: list[ImpactFinding] = []
    unknown: list[str] = []
    if not path_set:
        unknown.append("no changed paths were supplied")
    for symbol in symbols:
        same_repo = symbol.citation.source_id == repository_id
        if not same_repo or symbol.citation.path not in path_set:
            continue
        findings.append(
            ImpactFinding(
                statement=f"{symbol.kind} {symbol.name} is defined in a changed file",
                evidence=symbol.evidence,
                path=symbol.citation.path,
                symbol=symbol.name,
            )
        )
    for edge in edges:
        source_hit = (
            edge.source_repository == repository_id and edge.source_path in path_set
        )
        target_hit = (
            edge.target_repository == repository_id and edge.target_path in path_set
        )
        if not source_hit and not target_hit:
            continue
        findings.append(
            ImpactFinding(
                statement=edge.reason,
                evidence=edge.evidence,
                path=edge.source_path,
                symbol=edge.source_symbol,
            )
        )
        if edge.evidence is EpistemicStatus.unknown or edge.target_path is None:
            unknown.append(edge.reason)
    if path_set and not findings:
        unknown.append("no dependency evidence for this change")
    return ImpactReport(
        repository_id=repository_id,
        paths=tuple(sorted(path_set)),
        findings=tuple(findings),
        unknown_relationships=tuple(dict.fromkeys(unknown)),
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
