"""Deterministic keyword retrieval with an optional local embedding hook.

Purpose: rank indexed excerpts without requiring a hosted embedding service.
Milestone: 05
Status: IMPLEMENTED
Ownership: knowledge.retriever
Dependencies: Chunk records and an optional embedding protocol.
Expected tests: stable ranking, result caps, and unused embeddings.
"""

import math
from typing import Protocol

from qa_mcp_hub.knowledge.models import ChunkRecord

_EXCERPT = 400


class EmbeddingProvider(Protocol):
    """Local vectors supplied by the caller. This hub does not call a host."""

    def embed(self, text: str) -> tuple[float, ...]:
        """Embed one string. The string is untrusted data."""


def rank_chunks(
    query: str,
    chunks: tuple[ChunkRecord, ...],
    embeddings: EmbeddingProvider | None,
    *,
    limit: int,
) -> tuple[tuple[int, str, ChunkRecord], ...]:
    """Return ``(score, excerpt, chunk)`` in a stable order."""
    tokens = tuple(part.lower() for part in query.split())
    vectors: dict[str, tuple[float, ...]] = {}
    query_vector: tuple[float, ...] = ()
    if embeddings is not None:
        query_vector = embeddings.embed(query)
        for chunk in chunks:
            vectors[chunk.chunk_id] = embeddings.embed(chunk.text)
    scored: list[tuple[int, str, str, int, str, ChunkRecord]] = []
    for chunk in chunks:
        keyword = _keyword_score(query, tokens, chunk.text)
        blended = keyword
        if query_vector and chunk.chunk_id in vectors:
            blended += int(_cosine(query_vector, vectors[chunk.chunk_id]) * 10)
        if blended <= 0:
            continue
        scored.append(
            (
                -blended,
                chunk.citation.source_id,
                chunk.citation.path,
                chunk.citation.start_line,
                chunk.chunk_id,
                chunk,
            )
        )
    scored.sort()
    chosen = scored[:limit]
    return tuple((-item[0], item[5].text[:_EXCERPT], item[5]) for item in chosen)


def embeddings_active(provider: EmbeddingProvider | None) -> bool:
    """Return whether ranking will consult an injected provider."""
    return provider is not None


def _keyword_score(query: str, tokens: tuple[str, ...], text: str) -> int:
    lowered = text.lower()
    score = 10 if query.lower() in lowered else 0
    score += sum(1 for token in tokens if token in lowered)
    return score


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
