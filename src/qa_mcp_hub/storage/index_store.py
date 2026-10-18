"""Revision-scoped chunks, symbols, edges, and manifests.

Purpose: persist the knowledge index for one local SQLite file.
Milestone: 05
Status: IMPLEMENTED
Ownership: storage.index_store
Dependencies: Knowledge models and the SQLite connection.
Expected tests: profile isolation, incremental replacement, and deletion.
"""

import json
import sqlite3
from datetime import datetime
from typing import Literal, cast

from qa_mcp_hub.core.enums import EpistemicStatus
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.knowledge.models import (
    ChunkRecord,
    DependencyEdge,
    IndexManifest,
    SourceCitation,
    SymbolRecord,
)
from qa_mcp_hub.storage.sqlite_store import SqliteDatabase, require_text


class IndexStore:
    """Profile-scoped index. Queries always include the profile id."""

    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    @property
    def recovery_warning(self) -> str | None:
        """Set when a corrupt file was moved aside and an empty index was created."""
        return self._database.recovery_warning

    def close(self) -> None:
        """Close the underlying database."""
        self._database.close()

    def file_hashes(self, profile_id: str, source_id: str) -> dict[str, str]:
        """Return stored content hashes for one repository."""
        rows = self._database.connection().execute(
            """
            SELECT path, content_hash FROM files
            WHERE profile_id = ? AND source_id = ?
            """,
            (profile_id, source_id),
        )
        return {
            require_text(row, "path"): require_text(row, "content_hash") for row in rows
        }

    def references_for(
        self, profile_id: str, source_id: str
    ) -> dict[str, list[dict[str, object]]]:
        """Return stored parser references keyed by path."""
        rows = self._database.connection().execute(
            """
            SELECT path, references_json FROM files
            WHERE profile_id = ? AND source_id = ?
            """,
            (profile_id, source_id),
        )
        found: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            payload = json.loads(require_text(row, "references_json"))
            if isinstance(payload, list):
                found[require_text(row, "path")] = [
                    item for item in payload if isinstance(item, dict)
                ]
        return found

    def replace_path(
        self,
        *,
        profile_id: str,
        source_id: str,
        path: str,
        content_hash: str,
        language: str,
        references_json: str,
        chunks: tuple[ChunkRecord, ...],
        symbols: tuple[SymbolRecord, ...],
    ) -> None:
        """Replace one path inside a transaction."""
        connection = self._database.connection()
        self._delete_path(profile_id, source_id, path)
        connection.execute(
            """
            INSERT INTO files (
                profile_id, source_id, path, content_hash, references_json, language
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (profile_id, source_id, path, content_hash, references_json, language),
        )
        for chunk in chunks:
            citation = chunk.citation
            connection.execute(
                """
                INSERT INTO chunks (
                    chunk_id, profile_id, source_kind, source_id, path, start_line,
                    end_line, revision, commit_sha, source_timestamp, retrieved_at,
                    language, text, content_hash, matches_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    profile_id,
                    citation.source_kind,
                    citation.source_id,
                    citation.path,
                    citation.start_line,
                    citation.end_line,
                    citation.revision,
                    citation.commit_sha,
                    _stamp(citation.source_timestamp),
                    citation.retrieved_at.isoformat(),
                    chunk.language,
                    chunk.text,
                    chunk.content_hash,
                    int(citation.matches_revision),
                ),
            )
        for symbol in symbols:
            citation = symbol.citation
            connection.execute(
                """
                INSERT INTO symbols (
                    symbol_id, profile_id, source_id, path, name, kind, start_line,
                    end_line, revision, commit_sha, source_timestamp, retrieved_at,
                    evidence, detail, matches_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol.symbol_id,
                    profile_id,
                    citation.source_id,
                    citation.path,
                    symbol.name,
                    symbol.kind,
                    citation.start_line,
                    citation.end_line,
                    citation.revision,
                    citation.commit_sha,
                    _stamp(citation.source_timestamp),
                    citation.retrieved_at.isoformat(),
                    symbol.evidence.value,
                    symbol.detail,
                    int(citation.matches_revision),
                ),
            )

    def delete_paths(
        self, profile_id: str, source_id: str, paths: tuple[str, ...]
    ) -> None:
        """Remove paths that are no longer tracked."""
        for path in paths:
            self._delete_path(profile_id, source_id, path)

    def replace_edges(
        self, profile_id: str, repository_id: str, edges: tuple[DependencyEdge, ...]
    ) -> None:
        """Replace edges that start in one repository."""
        connection = self._database.connection()
        connection.execute(
            "DELETE FROM edges WHERE profile_id = ? AND source_repository = ?",
            (profile_id, repository_id),
        )
        for edge in edges:
            connection.execute(
                """
                INSERT INTO edges (
                    edge_id, profile_id, source_repository, source_path, source_symbol,
                    target_repository, target_path, target_symbol, kind, evidence,
                    reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.edge_id,
                    edge.profile_id,
                    edge.source_repository,
                    edge.source_path,
                    edge.source_symbol,
                    edge.target_repository,
                    edge.target_path,
                    edge.target_symbol,
                    edge.kind,
                    edge.evidence.value,
                    edge.reason,
                ),
            )

    def save_manifest(self, manifest: IndexManifest) -> None:
        """Upsert one repository manifest."""
        self._database.connection().execute(
            """
            INSERT INTO manifests (
                profile_id, repository_id, revision, indexed_at, file_count,
                chunk_count, mode, dirty, warnings_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (profile_id, repository_id) DO UPDATE SET
                revision = excluded.revision,
                indexed_at = excluded.indexed_at,
                file_count = excluded.file_count,
                chunk_count = excluded.chunk_count,
                mode = excluded.mode,
                dirty = excluded.dirty,
                warnings_json = excluded.warnings_json
            """,
            (
                manifest.profile_id,
                manifest.repository_id,
                manifest.revision,
                manifest.indexed_at.isoformat(),
                manifest.file_count,
                manifest.chunk_count,
                manifest.mode,
                int(manifest.dirty),
                json.dumps(list(manifest.warnings)),
            ),
        )

    def commit(self) -> None:
        """Commit the current transaction."""
        self._database.connection().commit()

    def manifest(self, profile_id: str, repository_id: str) -> IndexManifest | None:
        """Return one manifest, if the repository has been indexed."""
        row = (
            self._database.connection()
            .execute(
                """
            SELECT * FROM manifests
            WHERE profile_id = ? AND repository_id = ?
            """,
                (profile_id, repository_id),
            )
            .fetchone()
        )
        if row is None:
            return None
        warnings_raw = json.loads(require_text(row, "warnings_json"))
        warnings = tuple(item for item in warnings_raw if isinstance(item, str))
        revision = row["revision"]
        mode = require_text(row, "mode")
        if mode not in {"full", "incremental", "skipped"}:
            raise HubError("index_corrupt", "index row had an unexpected type")
        return IndexManifest(
            profile_id=profile_id,
            repository_id=repository_id,
            revision=revision if isinstance(revision, str) else None,
            indexed_at=datetime.fromisoformat(require_text(row, "indexed_at")),
            file_count=int(row["file_count"]),
            chunk_count=int(row["chunk_count"]),
            mode=cast("Literal['full', 'incremental', 'skipped']", mode),
            dirty=bool(row["dirty"]),
            warnings=warnings,
        )

    def paths(self, profile_id: str) -> dict[tuple[str, str], str]:
        """Return every indexed path in one profile."""
        rows = self._database.connection().execute(
            "SELECT source_id, path FROM files WHERE profile_id = ?",
            (profile_id,),
        )
        return {
            (require_text(row, "source_id"), require_text(row, "path")): require_text(
                row, "path"
            )
            for row in rows
        }

    def symbols(self, profile_id: str) -> tuple[SymbolRecord, ...]:
        """Return symbols for one profile."""
        rows = self._database.connection().execute(
            """
            SELECT * FROM symbols
            WHERE profile_id = ?
            ORDER BY path, start_line, name
            """,
            (profile_id,),
        )
        return tuple(_symbol(row) for row in rows)

    def edges(self, profile_id: str) -> tuple[DependencyEdge, ...]:
        """Return edges for one profile."""
        rows = self._database.connection().execute(
            """
            SELECT * FROM edges
            WHERE profile_id = ?
            ORDER BY source_path, source_symbol, target_symbol
            """,
            (profile_id,),
        )
        return tuple(_edge(row) for row in rows)

    def chunks_matching(
        self, profile_id: str, tokens: tuple[str, ...]
    ) -> tuple[ChunkRecord, ...]:
        """Return chunks that contain every token. Matching is case-insensitive."""
        if not tokens:
            return ()
        if len(tokens) > len(_CHUNK_SQL) - 1:
            raise HubError("query_invalid", "knowledge query must contain 1 to 8 words")
        rows = self._database.connection().execute(
            _CHUNK_SQL[len(tokens)],
            (profile_id, *(_like(token) for token in tokens)),
        )
        return tuple(_chunk(row) for row in rows)

    def chunk_count(self, profile_id: str, source_id: str) -> int:
        """Count chunks for one source."""
        row = (
            self._database.connection()
            .execute(
                """
            SELECT COUNT(*) AS total FROM chunks
            WHERE profile_id = ? AND source_id = ?
            """,
                (profile_id, source_id),
            )
            .fetchone()
        )
        if row is None:
            return 0
        return int(row["total"])

    def _delete_path(self, profile_id: str, source_id: str, path: str) -> None:
        connection = self._database.connection()
        connection.execute(
            "DELETE FROM files WHERE profile_id = ? AND source_id = ? AND path = ?",
            (profile_id, source_id, path),
        )
        connection.execute(
            "DELETE FROM chunks WHERE profile_id = ? AND source_id = ? AND path = ?",
            (profile_id, source_id, path),
        )
        connection.execute(
            "DELETE FROM symbols WHERE profile_id = ? AND source_id = ? AND path = ?",
            (profile_id, source_id, path),
        )


_CHUNK_SQL = (
    "",
    (
        "SELECT * FROM chunks WHERE profile_id = ? "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "ORDER BY source_id, path, start_line, chunk_id"
    ),
    (
        "SELECT * FROM chunks WHERE profile_id = ? "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "ORDER BY source_id, path, start_line, chunk_id"
    ),
    (
        "SELECT * FROM chunks WHERE profile_id = ? "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "ORDER BY source_id, path, start_line, chunk_id"
    ),
    (
        "SELECT * FROM chunks WHERE profile_id = ? "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "ORDER BY source_id, path, start_line, chunk_id"
    ),
    (
        "SELECT * FROM chunks WHERE profile_id = ? "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "ORDER BY source_id, path, start_line, chunk_id"
    ),
    (
        "SELECT * FROM chunks WHERE profile_id = ? "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "ORDER BY source_id, path, start_line, chunk_id"
    ),
    (
        "SELECT * FROM chunks WHERE profile_id = ? "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "ORDER BY source_id, path, start_line, chunk_id"
    ),
    (
        "SELECT * FROM chunks WHERE profile_id = ? "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "AND lower(text) LIKE ? ESCAPE '\\' "
        "ORDER BY source_id, path, start_line, chunk_id"
    ),
)


def _stamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _like(token: str) -> str:
    escaped = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped.lower()}%"


def _citation(row: sqlite3.Row, *, kind: str) -> SourceCitation:
    timestamp = row["source_timestamp"]
    commit = row["commit_sha"]
    return SourceCitation(
        profile_id=require_text(row, "profile_id"),
        source_kind="repository" if kind == "repository" else "document",
        source_id=require_text(row, "source_id"),
        path=require_text(row, "path"),
        start_line=int(row["start_line"]),
        end_line=int(row["end_line"]),
        revision=require_text(row, "revision"),
        commit_sha=commit if isinstance(commit, str) else None,
        source_timestamp=(
            datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else None
        ),
        retrieved_at=datetime.fromisoformat(require_text(row, "retrieved_at")),
        matches_revision=bool(row["matches_revision"]),
    )


def _chunk(row: sqlite3.Row) -> ChunkRecord:
    kind = require_text(row, "source_kind")
    if kind not in {"repository", "document"}:
        raise HubError("index_corrupt", "index row had an unexpected type")
    return ChunkRecord(
        chunk_id=require_text(row, "chunk_id"),
        citation=_citation(row, kind=kind),
        language=require_text(row, "language"),
        text=require_text(row, "text"),
        content_hash=require_text(row, "content_hash"),
    )


def _symbol(row: sqlite3.Row) -> SymbolRecord:
    evidence = require_text(row, "evidence")
    return SymbolRecord(
        symbol_id=require_text(row, "symbol_id"),
        name=require_text(row, "name"),
        kind=require_text(row, "kind"),
        citation=_citation(row, kind="repository"),
        evidence=EpistemicStatus(evidence),
        detail=require_text(row, "detail"),
    )


def _edge(row: sqlite3.Row) -> DependencyEdge:
    target_repo = row["target_repository"]
    target_path = row["target_path"]
    return DependencyEdge(
        edge_id=require_text(row, "edge_id"),
        profile_id=require_text(row, "profile_id"),
        source_repository=require_text(row, "source_repository"),
        source_path=require_text(row, "source_path"),
        source_symbol=require_text(row, "source_symbol"),
        target_repository=target_repo if isinstance(target_repo, str) else None,
        target_path=target_path if isinstance(target_path, str) else None,
        target_symbol=require_text(row, "target_symbol"),
        kind=require_text(row, "kind"),
        evidence=EpistemicStatus(require_text(row, "evidence")),
        reason=require_text(row, "reason"),
    )
