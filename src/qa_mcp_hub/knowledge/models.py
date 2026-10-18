"""Normalized document records for later knowledge indexing.

Purpose: carry Confluence and Google Docs text as data, with a stable citation.
Milestone: 04
Status: IMPLEMENTED
Ownership: knowledge.models
Dependencies: Pydantic v2.
Expected tests: citations, truncation, and redaction of credential material.

Chunking, symbols, and retrieval remain Milestone 05 and are not defined here.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentStatus = Literal["read", "inaccessible", "removed", "unsupported"]


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
