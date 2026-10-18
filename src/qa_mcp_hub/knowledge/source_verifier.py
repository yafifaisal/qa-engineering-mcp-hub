"""Check that a citation still matches the approved file.

Purpose: detect deleted files and line drift after indexing.
Milestone: 05
Status: IMPLEMENTED
Ownership: knowledge.source_verifier
Dependencies: Source citations and content hashes.
Expected tests: matching lines, missing files, and conflicting text.
"""

from pathlib import Path

from qa_mcp_hub.core.enums import EpistemicStatus
from qa_mcp_hub.knowledge.chunker import hash_span
from qa_mcp_hub.knowledge.models import SourceCitation


def verify_citation(
    root: Path,
    citation: SourceCitation,
    expected_hash: str,
) -> EpistemicStatus:
    """Re-read the cited lines. Missing files are UNKNOWN, not a match."""
    if citation.source_kind != "repository":
        return EpistemicStatus.inferred
    candidate = root / citation.path
    if not candidate.is_file():
        return EpistemicStatus.unknown
    try:
        text = candidate.read_text(encoding="utf-8")
    except OSError:
        return EpistemicStatus.unknown
    if hash_span(text, citation.start_line, citation.end_line) != expected_hash:
        return EpistemicStatus.conflicting
    if not citation.matches_revision:
        return EpistemicStatus.inferred
    return EpistemicStatus.verified
