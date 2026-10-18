"""Document records and source-grounded knowledge index records.

Purpose: carry retrieved text as data, with stable citations and evidence labels.
Milestone: 05
Status: IMPLEMENTED
Ownership: knowledge.models
Dependencies: Pydantic v2 and the shared epistemic status vocabulary.
Expected tests: citations, truncation, evidence labels, and redaction of credentials.

Indexed text is untrusted data. A source reference is not a runtime observation.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from qa_mcp_hub.core.enums import EpistemicStatus

DocumentStatus = Literal["read", "inaccessible", "removed", "unsupported"]
SourceKind = Literal["repository", "document"]


class DocumentCitation(BaseModel):
    """Where a document came from. This value is not an instruction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    document_id: str
    title: str
    url: str
    revision: str | None = None
    retrieved_at: datetime
    space: str | None = None


class DocumentRecord(BaseModel):
    """One retrieved document. ``untrusted_text`` is data, not an instruction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    citation: DocumentCitation
    untrusted_text: str = ""
    text_truncated: bool = False
    status: DocumentStatus = "read"
    warnings: tuple[str, ...] = ()
    untrusted_content: bool = True


class DocumentSearchResult(BaseModel):
    """One page of document citations. Excerpts are untrusted data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    hits: tuple[DocumentCitation, ...] = ()
    truncated: bool = False
    next_cursor: str | None = None
    untrusted_content: bool = True


class DocumentCache:
    """Small in-memory cache of document records. It does not store tokens."""

    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(seconds=60),
        max_entries: int = 32,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl <= timedelta(0) or max_entries < 1:
            raise ValueError("document cache limits must be positive")
        self._ttl = ttl
        self._max_entries = max_entries
        self._clock = clock or (lambda: datetime.now(UTC))
        self._items: dict[str, tuple[datetime, DocumentRecord]] = {}

    def get(self, key: str) -> DocumentRecord | None:
        """Return a fresh record, or none when the entry is missing or stale."""
        item = self._items.get(key)
        if item is None:
            return None
        stored_at, record = item
        now = self._now()
        if now - stored_at > self._ttl:
            del self._items[key]
            return None
        return record

    def put(self, key: str, record: DocumentRecord) -> None:
        """Store one record and drop the oldest entry past the size limit."""
        self._items.pop(key, None)
        self._items[key] = (self._now(), record)
        while len(self._items) > self._max_entries:
            oldest = next(iter(self._items))
            del self._items[oldest]

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("document cache clock must return an aware datetime")
        return now


class CachedDocumentKey(BaseModel):
    """Cache identity. Credential material is intentionally absent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1, max_length=64)
    document_id: str = Field(min_length=1, max_length=128)
    revision: str = Field(default="", max_length=128)


class SourceCitation(BaseModel):
    """A location in an approved repository or document. Not an instruction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    source_kind: SourceKind
    source_id: str
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    revision: str
    commit_sha: str | None = None
    source_timestamp: datetime | None = None
    url: str | None = None
    retrieved_at: datetime
    matches_revision: bool = True


class ChunkRecord(BaseModel):
    """One bounded excerpt. The text is untrusted data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    citation: SourceCitation
    language: str
    text: str
    content_hash: str
    text_truncated: bool = False
    untrusted_content: bool = True


class SymbolRecord(BaseModel):
    """A named source span. Unsupported parsers stay UNKNOWN."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol_id: str
    name: str
    kind: str
    citation: SourceCitation
    evidence: EpistemicStatus
    detail: str = ""


class DependencyEdge(BaseModel):
    """A source reference. ``runtime_observed`` stays false in this milestone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_id: str
    profile_id: str
    source_repository: str
    source_path: str
    source_symbol: str
    target_repository: str | None
    target_path: str | None
    target_symbol: str
    kind: str
    evidence: EpistemicStatus
    reason: str
    runtime_observed: Literal[False] = False


class IndexManifest(BaseModel):
    """What one profile repository index contains after a refresh."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    repository_id: str
    revision: str | None
    indexed_at: datetime
    file_count: int = 0
    chunk_count: int = 0
    mode: Literal["full", "incremental", "skipped"]
    dirty: bool = False
    warnings: tuple[str, ...] = ()


class KnowledgeHit(BaseModel):
    """One ranked excerpt. The excerpt cannot change tool permissions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    citation: SourceCitation
    excerpt: str
    score: int
    evidence: EpistemicStatus
    content_hash: str = ""
    stale: bool = False
    untrusted_content: bool = True


class Finding(BaseModel):
    """A labeled conclusion. The statement is data about sources, not an order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str
    evidence: EpistemicStatus
    citations: tuple[SourceCitation, ...] = ()
    untrusted_content: bool = True


class KnowledgeSearchResult(BaseModel):
    """Keyword search output. Embeddings are used only when a caller injects them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    hits: tuple[KnowledgeHit, ...] = ()
    findings: tuple[Finding, ...] = ()
    warnings: tuple[str, ...] = ()
    embeddings_used: bool = False
    untrusted_content: bool = True


class FlowHop(BaseModel):
    """One source reference on a partial path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_repository: str
    source_path: str
    source_symbol: str
    target_repository: str | None
    target_path: str | None
    target_symbol: str
    kind: str
    evidence: EpistemicStatus
    runtime_observed: Literal[False] = False


class FlowTrace(BaseModel):
    """A partial source path. This model cannot represent a complete runtime graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str
    evidence: EpistemicStatus
    hops: tuple[FlowHop, ...] = ()
    unknown_relationships: tuple[str, ...] = ()
    complete_graph: Literal[False] = False
    runtime_observed: Literal[False] = False
    untrusted_content: bool = True


class ImplementationReport(BaseModel):
    """Issue-key mentions in Git content. A mention is not proof of implementation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_key: str
    issue_url: str | None = None
    ticket_read: EpistemicStatus = EpistemicStatus.unknown
    mentions: tuple[KnowledgeHit, ...] = ()
    relationship: EpistemicStatus = EpistemicStatus.unknown
    warnings: tuple[str, ...] = ()
    complete_graph: Literal[False] = False
    untrusted_content: bool = True


class FreshnessReport(BaseModel):
    """Whether an index revision still matches the approved checkout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_id: str
    state: Literal["current", "stale", "missing"]
    evidence: EpistemicStatus
    indexed_revision: str | None
    current_revision: str | None
    warning: str | None = None
