"""Index approved Git checkouts and already retrieved documents.

Purpose: build a deterministic local index without reading secret paths.
Milestone: 05
Status: IMPLEMENTED
Ownership: knowledge.indexer
Dependencies: Chunker, parser, symbols, dependency graph, and the index store.
Expected tests: repeatability, incremental updates, deletion, and secret exclusion.
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Literal

from qa_mcp_hub.config.models import RepositoryReference
from qa_mcp_hub.core.enums import EpistemicStatus, IndexingPermission
from qa_mcp_hub.core.errors import GitInspectionError, HubError, PathAllowlistError
from qa_mcp_hub.knowledge.chunker import chunk_text, hash_text
from qa_mcp_hub.knowledge.code_parser import ParsedReference, parse_source
from qa_mcp_hub.knowledge.dependency_graph import build_edges
from qa_mcp_hub.knowledge.models import (
    DependencyEdge,
    DocumentRecord,
    IndexManifest,
    SourceCitation,
)
from qa_mcp_hub.knowledge.symbol_extractor import extract_symbols
from qa_mcp_hub.repositories.git_metadata import (
    last_commit_for_path,
    list_tracked_files,
    read_git_metadata,
)
from qa_mcp_hub.repositories.registry import effective_excludes, effective_includes
from qa_mcp_hub.security.path_allowlist import resolve_within
from qa_mcp_hub.storage.index_store import IndexStore

_MAX_FILES = 2000
_MAX_BYTES = 262144
_SKIP_SUFFIXES = {
    ".dll",
    ".exe",
    ".gif",
    ".gz",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".pyo",
    ".so",
    ".webp",
    ".whl",
    ".zip",
}
_EXTRA_NAMES = {"credentials.json", "credentials.yaml", "secrets.json"}


def index_repository(
    repository: RepositoryReference,
    *,
    profile_id: str,
    root: Path,
    store: IndexStore,
    clock: Callable[[], datetime] | None = None,
) -> IndexManifest:
    """Index one approved checkout. Secret paths are skipped before they are read."""
    if repository.indexing is IndexingPermission.none:
        raise HubError("indexing_not_permitted", "indexing_not_permitted")
    now = (clock or (lambda: datetime.now(UTC)))()
    try:
        metadata = read_git_metadata(root, (root,))
        tracked = list_tracked_files(root, (root,))
    except (GitInspectionError, PathAllowlistError) as exc:
        manifest = IndexManifest(
            profile_id=profile_id,
            repository_id=repository.id,
            revision=None,
            indexed_at=now,
            mode="skipped",
            warnings=(exc.code,),
        )
        store.save_manifest(manifest)
        store.commit()
        return manifest
    existing = store.file_hashes(profile_id, repository.id)
    warnings: list[str] = []
    if repository.indexing is not IndexingPermission.content:
        warnings.append("content_not_stored")
    selected = _select_files(root, tracked, repository, warnings)
    seen: set[str] = set()
    for relative, resolved in selected:
        text = _read_text(resolved)
        if text is None:
            warnings.append(f"unreadable:{relative}")
            continue
        if "\x00" in text:
            warnings.append(f"binary_skipped:{relative}")
            continue
        seen.add(relative)
        digest = hash_text(text)
        if existing.get(relative) == digest:
            continue
        sha, stamp, matches = _file_revision(
            root, relative, metadata.head_sha, metadata.dirty
        )
        if sha != metadata.head_sha and not matches:
            warnings.append(f"file_revision_unverified:{relative}")
        citation = SourceCitation(
            profile_id=profile_id,
            source_kind="repository",
            source_id=repository.id,
            path=relative,
            start_line=1,
            end_line=1,
            revision=sha,
            commit_sha=sha,
            source_timestamp=stamp,
            retrieved_at=now,
            matches_revision=matches and not metadata.dirty,
        )
        store_text = repository.indexing is IndexingPermission.content
        parsed = parse_source(relative, text) if store_text else None
        chunks = (
            chunk_text(
                text,
                citation,
                language=parsed.language if parsed else "unknown",
            )
            if store_text
            else ()
        )
        symbols = (
            extract_symbols(citation, parsed.symbols)
            if parsed is not None and parsed.evidence is not EpistemicStatus.unknown
            else ()
        )
        if parsed is not None and parsed.evidence is EpistemicStatus.unknown:
            warnings.append(f"parser_unknown:{relative}")
        references = parsed.references if parsed is not None else ()
        store.replace_path(
            profile_id=profile_id,
            source_id=repository.id,
            path=relative,
            content_hash=digest,
            language=parsed.language if parsed else "unknown",
            references_json=json.dumps(
                [_reference_payload(item) for item in references]
            ),
            chunks=chunks,
            symbols=symbols,
        )
    removed = tuple(path for path in existing if path not in seen)
    if removed:
        store.delete_paths(profile_id, repository.id, removed)
    _rebuild_edges(store, profile_id, repository.id)
    mode: Literal["full", "incremental"] = "incremental" if existing else "full"
    manifest = IndexManifest(
        profile_id=profile_id,
        repository_id=repository.id,
        revision=metadata.head_sha,
        indexed_at=now,
        file_count=len(seen),
        chunk_count=store.chunk_count(profile_id, repository.id),
        mode=mode,
        dirty=metadata.dirty,
        warnings=tuple(dict.fromkeys(warnings)),
    )
    store.save_manifest(manifest)
    store.commit()
    return manifest


def index_document(
    record: DocumentRecord,
    *,
    profile_id: str,
    store: IndexStore,
    clock: Callable[[], datetime] | None = None,
) -> IndexManifest:
    """Index one document the caller already retrieved. This does not fetch it."""
    now = (clock or (lambda: datetime.now(UTC)))()
    source_id = f"doc:{record.citation.provider}:{record.citation.document_id}"
    if record.status != "read":
        store.delete_paths(profile_id, source_id, (record.citation.document_id,))
        manifest = IndexManifest(
            profile_id=profile_id,
            repository_id=source_id,
            revision=record.citation.revision,
            indexed_at=now,
            mode="skipped",
            warnings=(record.status,),
        )
        store.save_manifest(manifest)
        store.commit()
        return manifest
    revision = record.citation.revision or "unversioned"
    citation = SourceCitation(
        profile_id=profile_id,
        source_kind="document",
        source_id=source_id,
        path=record.citation.document_id,
        start_line=1,
        end_line=1,
        revision=revision,
        commit_sha=None,
        source_timestamp=record.citation.retrieved_at,
        url=record.citation.url,
        retrieved_at=now,
        matches_revision=record.citation.revision is not None,
    )
    chunks = chunk_text(record.untrusted_text, citation, language="document")
    store.replace_path(
        profile_id=profile_id,
        source_id=source_id,
        path=record.citation.document_id,
        content_hash=hash_text(record.untrusted_text),
        language="document",
        references_json="[]",
        chunks=chunks,
        symbols=(),
    )
    manifest = IndexManifest(
        profile_id=profile_id,
        repository_id=source_id,
        revision=revision,
        indexed_at=now,
        file_count=1,
        chunk_count=len(chunks),
        mode="full",
        warnings=record.warnings,
    )
    store.save_manifest(manifest)
    store.commit()
    return manifest


def _select_files(
    root: Path,
    tracked: tuple[str, ...],
    repository: RepositoryReference,
    warnings: list[str],
) -> tuple[tuple[str, Path], ...]:
    excludes = effective_excludes(repository.exclude)
    includes = effective_includes(repository.include, repository.exclude)
    selected: list[tuple[str, Path]] = []
    for relative in tracked:
        posix = relative.replace("\\", "/")
        if len(selected) >= _MAX_FILES:
            warnings.append("file_limit_reached")
            break
        if _excluded(posix, excludes) or PurePosixPath(posix).name in _EXTRA_NAMES:
            continue
        if includes and not any(_matches(posix, pattern) for pattern in includes):
            continue
        if PurePosixPath(posix).suffix.lower() in _SKIP_SUFFIXES:
            continue
        candidate = root / relative
        try:
            resolved = resolve_within(candidate, (root,))
        except PathAllowlistError:
            warnings.append(f"path_rejected:{posix}")
            continue
        if not resolved.is_file():
            continue
        try:
            size = resolved.stat().st_size
        except OSError:
            warnings.append(f"unreadable:{posix}")
            continue
        if size > _MAX_BYTES:
            warnings.append(f"file_too_large:{posix}")
            continue
        selected.append((posix, resolved))
    return tuple(selected)


def _excluded(path: str, patterns: tuple[str, ...]) -> bool:
    name = PurePosixPath(path).name
    for pattern in patterns:
        if _matches(path, pattern) or _matches(name, pattern):
            return True
    return False


def _matches(path: str, pattern: str) -> bool:
    if "**" in pattern:
        expression = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        return re.fullmatch(expression, path) is not None
    return fnmatch(path, pattern)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _file_revision(
    root: Path,
    relative: str,
    head: str,
    dirty: bool,
) -> tuple[str, datetime | None, bool]:
    try:
        sha, stamp = last_commit_for_path(root, (root,), relative)
    except (GitInspectionError, PathAllowlistError):
        return head, None, False
    return sha, stamp, not dirty


def _reference_payload(reference: ParsedReference) -> dict[str, object]:
    return {
        "kind": reference.kind,
        "source_name": reference.source_name,
        "target_name": reference.target_name,
        "target_hint": reference.target_hint,
        "start_line": reference.start_line,
        "evidence": reference.evidence.value,
        "detail": reference.detail,
    }


def _rebuild_edges(store: IndexStore, profile_id: str, repository_id: str) -> None:
    files = store.paths(profile_id)
    names: dict[str, list[tuple[str, str]]] = {}
    for symbol in store.symbols(profile_id):
        if symbol.kind not in {"function", "class"}:
            continue
        names.setdefault(symbol.name, []).append(
            (symbol.citation.source_id, symbol.citation.path)
        )
    symbol_index = {name: tuple(items) for name, items in names.items()}
    edges: list[DependencyEdge] = []
    for path, payloads in store.references_for(profile_id, repository_id).items():
        references = tuple(
            item
            for item in (_parsed_reference(payload) for payload in payloads)
            if item is not None
        )
        edges.extend(
            build_edges(
                profile_id=profile_id,
                repository_id=repository_id,
                path=path,
                references=references,
                files=files,
                symbols_by_name=symbol_index,
            )
        )
    store.replace_edges(profile_id, repository_id, tuple(edges))


def _parsed_reference(payload: dict[str, object]) -> ParsedReference | None:
    kind = payload.get("kind")
    source_name = payload.get("source_name")
    target_name = payload.get("target_name")
    start_line = payload.get("start_line")
    evidence = payload.get("evidence")
    detail = payload.get("detail")
    hint = payload.get("target_hint")
    names = (kind, source_name, target_name, detail)
    if not all(isinstance(item, str) for item in names):
        return None
    if not isinstance(start_line, int):
        return None
    if not isinstance(evidence, str):
        return None
    try:
        status = EpistemicStatus(evidence)
    except ValueError:
        return None
    return ParsedReference(
        kind=kind if isinstance(kind, str) else "",
        source_name=source_name if isinstance(source_name, str) else "",
        target_name=target_name if isinstance(target_name, str) else "",
        target_hint=hint if isinstance(hint, str) else None,
        start_line=start_line,
        evidence=status,
        detail=detail if isinstance(detail, str) else "",
    )
