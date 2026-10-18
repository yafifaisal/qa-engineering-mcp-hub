"""Stable symbol identities from parser output.

Purpose: assign source spans and evidence labels to extracted names.
Milestone: 05
Status: IMPLEMENTED
Ownership: knowledge.symbol_extractor
Dependencies: Code parser output and knowledge models.
Expected tests: duplicate names, spans, and stable identity.
"""

import hashlib

from qa_mcp_hub.knowledge.code_parser import ParsedSymbol
from qa_mcp_hub.knowledge.models import SourceCitation, SymbolRecord


def extract_symbols(
    citation: SourceCitation,
    symbols: tuple[ParsedSymbol, ...],
) -> tuple[SymbolRecord, ...]:
    """Build symbol records. Identity ignores retrieval time."""
    records: list[SymbolRecord] = []
    for symbol in symbols:
        span = citation.model_copy(
            update={
                "start_line": max(symbol.start_line, 1),
                "end_line": max(symbol.end_line, symbol.start_line, 1),
            }
        )
        identity = "\0".join(
            (
                span.profile_id,
                span.source_id,
                span.path,
                span.revision,
                symbol.kind,
                symbol.name,
                str(span.start_line),
            )
        )
        records.append(
            SymbolRecord(
                symbol_id=hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24],
                name=symbol.name[:200],
                kind=symbol.kind,
                citation=span,
                evidence=symbol.evidence,
                detail=symbol.detail[:200],
            )
        )
    return tuple(records)
