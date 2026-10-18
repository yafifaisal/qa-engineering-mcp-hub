"""Profile-scoped indexing and grounded retrieval.

Purpose: search only repositories and documents allowed by the active profile.
Milestone: 05
Status: IMPLEMENTED
Ownership: knowledge.service
Dependencies: Indexer, retriever, verifier, freshness, and the repository registry.
Expected tests: authorization, provenance, conflicts, and partial traces.
"""

import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from qa_mcp_hub.config.loader import load_config
from qa_mcp_hub.config.models import HubConfig
from qa_mcp_hub.config.paths import default_config_dir
from qa_mcp_hub.core.enums import EpistemicStatus, IndexingPermission
from qa_mcp_hub.core.errors import GitInspectionError, HubError, PathAllowlistError
from qa_mcp_hub.knowledge.freshness import assess_freshness
from qa_mcp_hub.knowledge.indexer import index_document, index_repository
from qa_mcp_hub.knowledge.models import (
    ChunkRecord,
    DocumentRecord,
    Finding,
    FlowHop,
    FlowTrace,
    FreshnessReport,
    ImplementationReport,
    IndexManifest,
    KnowledgeHit,
    KnowledgeSearchResult,
    SourceCitation,
)
from qa_mcp_hub.knowledge.retriever import EmbeddingProvider, rank_chunks
from qa_mcp_hub.knowledge.source_verifier import verify_citation
from qa_mcp_hub.planning.models import ImpactReport
from qa_mcp_hub.repositories.git_metadata import (
    changed_tracked_paths,
    read_git_metadata,
)
from qa_mcp_hub.repositories.registry import approved_roots, list_repositories
from qa_mcp_hub.security.path_allowlist import resolve_within
from qa_mcp_hub.storage.index_store import IndexStore
from qa_mcp_hub.storage.sqlite_store import SqliteDatabase

_QUERY_LIMIT = 200
_ISSUE_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
_CLAIM = re.compile(r"CLAIM\s+([A-Za-z0-9_.-]{1,64})=([A-Za-z0-9_.-]{1,64})")
_TRACE_DEPTH = 4


class KnowledgeEngine:
    """Local knowledge index. Retrieved text cannot change tool permissions."""

    def __init__(
        self,
        store: IndexStore,
        *,
        embeddings: EmbeddingProvider | None = None,
        clock: Callable[[], datetime] | None = None,
        config_loader: Callable[[], HubConfig] | None = None,
    ) -> None:
        self._store = store
        self._embeddings = embeddings
        self._clock = clock or (lambda: datetime.now(UTC))
        self._config_loader = config_loader or load_config

    def close(self) -> None:
        """Close the index database."""
        self._store.close()

    def refresh(self, profile: str | None = None) -> tuple[IndexManifest, ...]:
        """Index permitted local checkouts. Remote-only repositories are skipped."""
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        roots = approved_roots(config, profile_id)
        manifests: list[IndexManifest] = []
        for repository in list_repositories(config, profile_id):
            if not repository.enabled or repository.indexing is IndexingPermission.none:
                continue
            if repository.path is None or not roots:
                manifests.append(
                    _skipped(
                        profile_id,
                        repository.id,
                        self._clock(),
                        "local_checkout_required",
                    )
                )
                continue
            try:
                root = resolve_within(Path(repository.path), roots)
            except PathAllowlistError:
                manifests.append(
                    _skipped(
                        profile_id,
                        repository.id,
                        self._clock(),
                        "outside_workspace",
                    )
                )
                continue
            manifests.append(
                index_repository(
                    repository,
                    profile_id=profile_id,
                    root=root,
                    store=self._store,
                    clock=self._clock,
                )
            )
        return tuple(manifests)

    def index_documents(
        self,
        records: tuple[DocumentRecord, ...],
        profile: str | None = None,
    ) -> tuple[IndexManifest, ...]:
        """Store documents the caller already retrieved for this profile."""
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        return tuple(
            index_document(
                record,
                profile_id=profile_id,
                store=self._store,
                clock=self._clock,
            )
            for record in records
        )

    def search(
        self,
        query: str,
        profile: str | None = None,
        *,
        limit: int = 20,
    ) -> KnowledgeSearchResult:
        """Refresh permitted repositories and return ranked, cited excerpts."""
        _validate_query(query)
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        warnings = [
            *_recovery(self._store),
            *_pre_refresh_warnings(config, profile_id, self._store),
        ]
        self.refresh(profile_id)
        tokens = tuple(part.lower() for part in query.split())
        chunks = self._store.chunks_matching(profile_id, tokens)
        embeddings_used = False
        try:
            ranked = rank_chunks(
                query,
                chunks,
                self._embeddings,
                limit=min(max(limit, 1), 50),
            )
            embeddings_used = self._embeddings is not None
        except (ArithmeticError, TypeError, ValueError):
            ranked = rank_chunks(query, chunks, None, limit=min(max(limit, 1), 50))
            warnings.append("embeddings_failed")
        freshness = _freshness_reports(config, profile_id, self._store)
        stale = {item.repository_id for item in freshness if item.state != "current"}
        for item in freshness:
            if item.warning:
                warnings.append(f"{item.repository_id}: {item.warning}")
        roots = _roots_for(config, profile_id)
        hits: list[KnowledgeHit] = []
        for score, excerpt, chunk in ranked:
            evidence, note = _verify_chunk(chunk, roots)
            if note:
                warnings.append(note)
            source_id = chunk.citation.source_id
            hits.append(
                KnowledgeHit(
                    citation=chunk.citation,
                    excerpt=excerpt,
                    score=score,
                    evidence=evidence,
                    content_hash=chunk.content_hash,
                    stale=source_id in stale,
                )
            )
        return KnowledgeSearchResult(
            query=query,
            hits=tuple(hits),
            findings=_claims(chunks),
            warnings=tuple(dict.fromkeys(warnings)),
            embeddings_used=embeddings_used,
        )

    def find_implementation(
        self,
        issue_key: str,
        profile: str | None = None,
    ) -> ImplementationReport:
        """Find the issue key in indexed Git text. The summary is not searched."""
        if _ISSUE_KEY.fullmatch(issue_key) is None:
            raise HubError("issue_key_invalid", "issue key format is invalid")
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        warnings = [
            "a source mention is not proof that the code implements the ticket",
            *_pre_refresh_warnings(config, profile_id, self._store),
        ]
        self.refresh(profile_id)
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(issue_key)}(?!\d)")
        chunks = self._store.chunks_matching(profile_id, (issue_key.lower(),))
        roots = _roots_for(config, profile_id)
        mentions: list[KnowledgeHit] = []
        for chunk in chunks:
            mentioned = pattern.search(chunk.text) is not None
            if chunk.citation.source_kind != "repository" or not mentioned:
                continue
            evidence, note = _verify_chunk(chunk, roots)
            if note:
                warnings.append(note)
            mentions.append(
                KnowledgeHit(
                    citation=chunk.citation,
                    excerpt=chunk.text[:400],
                    score=10,
                    evidence=evidence,
                    content_hash=chunk.content_hash,
                )
            )
        relationship = EpistemicStatus.inferred if mentions else EpistemicStatus.unknown
        return ImplementationReport(
            issue_key=issue_key,
            mentions=tuple(mentions),
            relationship=relationship,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def trace(self, symbol: str, profile: str | None = None) -> FlowTrace:
        """Walk source references. The result is never a complete runtime graph."""
        if not symbol or len(symbol) > 200 or any(char.isspace() for char in symbol):
            raise HubError("symbol_invalid", "symbol name is invalid")
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        self.refresh(profile_id)
        symbols = [
            item
            for item in self._store.symbols(profile_id)
            if item.name == symbol and item.kind in {"function", "class"}
        ]
        statement = (
            "These hops are source references only. "
            "This is not a complete runtime call graph."
        )
        if not symbols:
            return FlowTrace(
                statement="the symbol is not in the approved index",
                evidence=EpistemicStatus.unknown,
                unknown_relationships=("symbol_missing",),
            )
        edges = self._store.edges(profile_id)
        hops: list[FlowHop] = []
        unknown: list[str] = []
        queue = [
            (item.citation.source_id, item.citation.path, item.name, 0)
            for item in symbols
        ]
        seen: set[tuple[str, str, str]] = set()
        while queue:
            repository_id, path, name, depth = queue.pop(0)
            marker = (repository_id, path, name)
            if marker in seen:
                continue
            seen.add(marker)
            if depth >= _TRACE_DEPTH:
                unknown.append("trace depth limit reached")
                continue
            for edge in edges:
                if (
                    edge.source_repository != repository_id
                    or edge.source_path != path
                    or edge.source_symbol != name
                ):
                    continue
                hops.append(
                    FlowHop(
                        source_repository=edge.source_repository,
                        source_path=edge.source_path,
                        source_symbol=edge.source_symbol,
                        target_repository=edge.target_repository,
                        target_path=edge.target_path,
                        target_symbol=edge.target_symbol,
                        kind=edge.kind,
                        evidence=edge.evidence,
                    )
                )
                if edge.kind != "call":
                    continue
                if edge.evidence is EpistemicStatus.unknown or edge.target_path is None:
                    unknown.append(edge.reason)
                    continue
                if edge.target_repository and edge.target_path:
                    queue.append(
                        (
                            edge.target_repository,
                            edge.target_path,
                            edge.target_symbol,
                            depth + 1,
                        )
                    )
        return FlowTrace(
            statement=statement,
            evidence=_trace_evidence(hops, unknown),
            hops=tuple(hops),
            unknown_relationships=tuple(dict.fromkeys(unknown)),
        )

    def analyze_impact(
        self,
        repository_id: str,
        paths: tuple[str, ...] | None,
        profile: str | None = None,
    ) -> ImpactReport:
        """Return a source-level impact report for one approved repository."""
        from qa_mcp_hub.planning.change_impact import build_impact

        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        self.refresh(profile_id)
        selected = paths
        if selected is None:
            selected = self.changed_paths(repository_id, profile_id)
        safe = tuple(path for path in selected if path and ".." not in path.split("/"))
        return build_impact(
            repository_id,
            safe,
            self._store.symbols(profile_id),
            self._store.edges(profile_id),
        )

    def changed_paths(
        self, repository_id: str, profile: str | None = None
    ) -> tuple[str, ...]:
        """Return tracked paths Git reports as changed in one approved checkout."""
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        repository = next(
            (
                item
                for item in list_repositories(config, profile_id)
                if item.id == repository_id and item.path is not None
            ),
            None,
        )
        if repository is None or repository.path is None:
            return ()
        roots = approved_roots(config, profile_id)
        try:
            root = resolve_within(Path(repository.path), roots)
            return changed_tracked_paths(root, roots)
        except (GitInspectionError, PathAllowlistError):
            return ()


def resolve_index_path() -> Path:
    """Return the local index path. An environment override is a path, not a secret."""
    override = os.environ.get("QA_MCP_INDEX_PATH", "").strip()
    if override:
        return Path(override)
    return default_config_dir() / "knowledge" / "index.sqlite"


def open_engine(
    *,
    embeddings: EmbeddingProvider | None = None,
    config_loader: Callable[[], HubConfig] | None = None,
) -> KnowledgeEngine:
    """Open the local knowledge index."""
    store = IndexStore(SqliteDatabase(resolve_index_path()))
    return KnowledgeEngine(store, embeddings=embeddings, config_loader=config_loader)


def search_knowledge(
    query: str,
    profile: str | None = None,
    *,
    config_loader: Callable[[], HubConfig] | None = None,
) -> KnowledgeSearchResult:
    """Search the active profile index."""
    engine = open_engine(config_loader=config_loader)
    try:
        return engine.search(query, profile)
    finally:
        engine.close()


def find_implementation(
    issue_key: str,
    profile: str | None = None,
    *,
    config_loader: Callable[[], HubConfig] | None = None,
) -> ImplementationReport:
    """Find issue-key mentions in the profile index."""
    engine = open_engine(config_loader=config_loader)
    try:
        return engine.find_implementation(issue_key, profile)
    finally:
        engine.close()


def trace_cross_repo_flow(
    symbol: str,
    profile: str | None = None,
    *,
    config_loader: Callable[[], HubConfig] | None = None,
) -> FlowTrace:
    """Trace source references for one symbol."""
    engine = open_engine(config_loader=config_loader)
    try:
        return engine.trace(symbol, profile)
    finally:
        engine.close()


def _profile_id(config: HubConfig, requested: str | None) -> str:
    name = requested or config.active_profile
    if name is None or name not in config.profiles:
        raise HubError("profile_required", "an active profile is required")
    return name


def _validate_query(query: str) -> None:
    if len(query) > _QUERY_LIMIT or not query.split() or len(query.split()) > 8:
        raise HubError("query_invalid", "knowledge query must contain 1 to 8 words")


def _skipped(
    profile_id: str, repository_id: str, now: datetime, warning: str
) -> IndexManifest:
    return IndexManifest(
        profile_id=profile_id,
        repository_id=repository_id,
        revision=None,
        indexed_at=now,
        mode="skipped",
        warnings=(warning,),
    )


def _recovery(store: IndexStore) -> list[str]:
    if store.recovery_warning:
        return [store.recovery_warning]
    return []


def _pre_refresh_warnings(
    config: HubConfig, profile_id: str, store: IndexStore
) -> list[str]:
    warnings: list[str] = []
    for report in _freshness_reports(config, profile_id, store):
        if report.state != "current" and report.warning:
            warnings.append(f"{report.repository_id}: {report.warning}")
    return warnings


def _freshness_reports(
    config: HubConfig, profile_id: str, store: IndexStore
) -> tuple[FreshnessReport, ...]:
    reports: list[FreshnessReport] = []
    roots = approved_roots(config, profile_id)
    for repository in list_repositories(config, profile_id):
        manifest = store.manifest(profile_id, repository.id)
        if manifest is None or repository.path is None:
            continue
        current: str | None = None
        dirty = False
        try:
            root = resolve_within(Path(repository.path), roots)
            metadata = read_git_metadata(root, roots)
            current = metadata.head_sha
            dirty = metadata.dirty
        except (GitInspectionError, PathAllowlistError):
            current = None
        reports.append(
            assess_freshness(
                repository.id,
                indexed_revision=manifest.revision,
                current_revision=current,
                dirty=dirty,
            )
        )
    return tuple(reports)


def _roots_for(config: HubConfig, profile_id: str) -> dict[str, Path]:
    roots = approved_roots(config, profile_id)
    found: dict[str, Path] = {}
    for repository in list_repositories(config, profile_id):
        if repository.path is None:
            continue
        try:
            found[repository.id] = resolve_within(Path(repository.path), roots)
        except PathAllowlistError:
            continue
    return found


def _verify_chunk(
    chunk: ChunkRecord, roots: dict[str, Path]
) -> tuple[EpistemicStatus, str | None]:
    if chunk.citation.source_kind != "repository":
        return EpistemicStatus.inferred, None
    root = roots.get(chunk.citation.source_id)
    if root is None:
        return EpistemicStatus.unknown, f"source_missing:{chunk.citation.path}"
    evidence = verify_citation(root, chunk.citation, chunk.content_hash)
    if not chunk.citation.matches_revision and evidence is EpistemicStatus.verified:
        evidence = EpistemicStatus.inferred
    note = None
    if evidence is EpistemicStatus.unknown:
        note = f"source_missing:{chunk.citation.path}"
    elif evidence is EpistemicStatus.conflicting:
        note = f"source_conflict:{chunk.citation.path}"
    return evidence, note


def _claims(chunks: tuple[ChunkRecord, ...]) -> tuple[Finding, ...]:
    grouped: dict[str, dict[str, list[SourceCitation]]] = {}
    for chunk in chunks:
        for match in _CLAIM.finditer(chunk.text):
            values = grouped.setdefault(match.group(1), {})
            values.setdefault(match.group(2), []).append(chunk.citation)
    findings: list[Finding] = []
    for key, values in sorted(grouped.items()):
        citations = tuple(
            citation for group in values.values() for citation in group[:4]
        )
        if len(values) > 1:
            evidence = EpistemicStatus.conflicting
            statement = f"CLAIM {key} has conflicting values in indexed sources"
        elif len(citations) < 2:
            evidence = EpistemicStatus.unknown
            statement = f"CLAIM {key} appears in one indexed source"
        else:
            evidence = EpistemicStatus.verified
            statement = (
                f"CLAIM {key} has the same value in the indexed sources that state it"
            )
        findings.append(
            Finding(statement=statement, evidence=evidence, citations=citations)
        )
    return tuple(findings)


def _trace_evidence(hops: list[FlowHop], unknown: list[str]) -> EpistemicStatus:
    if unknown or not hops:
        return EpistemicStatus.unknown
    if any(hop.evidence is EpistemicStatus.conflicting for hop in hops):
        return EpistemicStatus.conflicting
    if any(hop.evidence is not EpistemicStatus.verified for hop in hops):
        return EpistemicStatus.inferred
    return EpistemicStatus.verified
