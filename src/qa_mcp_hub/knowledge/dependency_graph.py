"""Source-grounded dependency edges.

Purpose: link verified code references without claiming a runtime call graph.
Milestone: 05
Status: IMPLEMENTED
Ownership: knowledge.dependency_graph
Dependencies: Parsed references and indexed file paths.
Expected tests: unresolved edges, cross-repository links, and cycles.
"""

import hashlib

from qa_mcp_hub.core.enums import EpistemicStatus
from qa_mcp_hub.knowledge.code_parser import ParsedReference
from qa_mcp_hub.knowledge.models import DependencyEdge

_SAME_REPO = "import resolves to a file in this repository"
_OTHER_REPO = (
    "a matching path exists in another indexed repository; "
    "runtime linkage was not observed"
)
_MISSING = "import target is not in the index"
_AMBIGUOUS = "name matches more than one symbol"


def build_edges(
    *,
    profile_id: str,
    repository_id: str,
    path: str,
    references: tuple[ParsedReference, ...],
    files: dict[tuple[str, str], str],
    symbols_by_name: dict[str, tuple[tuple[str, str], ...]],
) -> tuple[DependencyEdge, ...]:
    """Resolve references against files already accepted into this profile index."""
    edges: list[DependencyEdge] = []
    for reference in references:
        target_repo, target_path, evidence, reason = _resolve(
            repository_id,
            path,
            reference,
            files,
            symbols_by_name,
        )
        identity = "\0".join(
            (
                profile_id,
                repository_id,
                path,
                reference.source_name,
                reference.kind,
                reference.target_name,
                target_repo or "",
                target_path or "",
                str(reference.start_line),
            )
        )
        edges.append(
            DependencyEdge(
                edge_id=hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24],
                profile_id=profile_id,
                source_repository=repository_id,
                source_path=path,
                source_symbol=reference.source_name[:200],
                target_repository=target_repo,
                target_path=target_path,
                target_symbol=reference.target_name[:200],
                kind=reference.kind,
                evidence=evidence,
                reason=reason,
            )
        )
    return tuple(edges)


def _resolve(
    repository_id: str,
    path: str,
    reference: ParsedReference,
    files: dict[tuple[str, str], str],
    symbols_by_name: dict[str, tuple[tuple[str, str], ...]],
) -> tuple[str | None, str | None, EpistemicStatus, str]:
    if reference.kind == "import" and reference.target_hint:
        resolved = _package_init(reference.target_hint, files, repository_id)
        same = (repository_id, resolved)
        if same[1] is not None and same in files:
            return repository_id, same[1], EpistemicStatus.verified, _SAME_REPO
        others = [
            (repo, file_path)
            for (repo, file_path) in files
            if repo != repository_id and _hint_matches(file_path, reference.target_hint)
        ]
        if len(others) == 1:
            repo, file_path = others[0]
            return repo, file_path, EpistemicStatus.inferred, _OTHER_REPO
        return None, None, EpistemicStatus.unknown, _MISSING
    if reference.kind == "call":
        matches = symbols_by_name.get(reference.target_name, ())
        local = [item for item in matches if item[0] == repository_id]
        if len(local) == 1:
            evidence = (
                EpistemicStatus.verified
                if local[0][1] == path
                else EpistemicStatus.inferred
            )
            return local[0][0], local[0][1], evidence, reference.detail
        if len(local) > 1:
            return None, None, EpistemicStatus.unknown, _AMBIGUOUS
        others = [item for item in matches if item[0] != repository_id]
        if len(others) == 1:
            return (
                others[0][0],
                others[0][1],
                EpistemicStatus.inferred,
                "name matches one symbol in another indexed repository; "
                "runtime linkage was not observed",
            )
        return None, None, EpistemicStatus.unknown, _MISSING
    if reference.kind in {"route", "publisher", "consumer", "job", "database"}:
        return None, None, reference.evidence, reference.detail
    return None, None, EpistemicStatus.unknown, reference.detail or _MISSING


def _package_init(
    hint: str,
    files: dict[tuple[str, str], str],
    repository_id: str,
) -> str | None:
    if (repository_id, hint) in files:
        return hint
    init = hint[: -len(".py")] + "/__init__.py" if hint.endswith(".py") else None
    if init is not None and (repository_id, init) in files:
        return init
    return hint if (repository_id, hint) in files else None


def _hint_matches(path: str, hint: str) -> bool:
    return path == hint or path.endswith("/" + hint)
