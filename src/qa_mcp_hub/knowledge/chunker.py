"""Deterministic line windows that keep file and line provenance.

Purpose: split source text into stable, bounded chunks.
Milestone: 05
Status: IMPLEMENTED
Ownership: knowledge.chunker
Dependencies: Knowledge models.
Expected tests: stable boundaries, overlap, large lines, and provenance.
"""

import hashlib

from qa_mcp_hub.knowledge.models import ChunkRecord, SourceCitation

_WINDOW = 80
_OVERLAP = 5
_MAX_LINE = 2000


def chunk_text(
    text: str,
    citation_template: SourceCitation,
    *,
    language: str,
) -> tuple[ChunkRecord, ...]:
    """Split text into stable windows. Line numbers are 1-based and inclusive."""
    lines, truncated = _bounded_lines(text)
    if not lines:
        return ()
    step = _WINDOW - _OVERLAP
    records: list[ChunkRecord] = []
    start = 0
    while start < len(lines):
        end = min(len(lines), start + _WINDOW)
        body = "\n".join(lines[start:end])
        start_line = start + 1
        citation = citation_template.model_copy(
            update={"start_line": start_line, "end_line": end}
        )
        records.append(
            ChunkRecord(
                chunk_id=_chunk_id(citation, body),
                citation=citation,
                language=language,
                text=body,
                content_hash=hash_text(body),
                text_truncated=truncated,
            )
        )
        if end == len(lines):
            break
        start += step
    return tuple(records)


def hash_span(text: str, start_line: int, end_line: int) -> str:
    """Hash the same bounded lines the chunker stored."""
    lines, _truncated = _bounded_lines(text)
    selected = lines[start_line - 1 : end_line]
    return hash_text("\n".join(selected))


def hash_text(text: str) -> str:
    """Return a stable digest of one chunk or file body."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_id(citation: SourceCitation, body: str) -> str:
    parts = (
        citation.profile_id,
        citation.source_kind,
        citation.source_id,
        citation.path,
        citation.revision,
        str(citation.start_line),
        str(citation.end_line),
        hash_text(body),
    )
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]


def _bounded_lines(text: str) -> tuple[list[str], bool]:
    truncated = False
    lines: list[str] = []
    for line in text.splitlines():
        if len(line) > _MAX_LINE:
            lines.append(line[:_MAX_LINE])
            truncated = True
        else:
            lines.append(line)
    return lines, truncated
