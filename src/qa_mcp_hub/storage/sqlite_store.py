"""Local SQLite connection for the knowledge index.

Purpose: open a profile index, recover a corrupt file, and apply the schema.
Milestone: 05
Status: IMPLEMENTED
Ownership: storage.sqlite_store
Dependencies: Standard-library SQLite.
Expected tests: schema creation, integrity failure, and recovery.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from qa_mcp_hub.core.errors import HubError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    profile_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    references_json TEXT NOT NULL,
    language TEXT NOT NULL,
    PRIMARY KEY (profile_id, source_id, path)
);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    revision TEXT NOT NULL,
    commit_sha TEXT,
    source_timestamp TEXT,
    retrieved_at TEXT NOT NULL,
    language TEXT NOT NULL,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    matches_revision INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS symbols (
    symbol_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    revision TEXT NOT NULL,
    commit_sha TEXT,
    source_timestamp TEXT,
    retrieved_at TEXT NOT NULL,
    evidence TEXT NOT NULL,
    detail TEXT NOT NULL,
    matches_revision INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS edges (
    edge_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    source_repository TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_symbol TEXT NOT NULL,
    target_repository TEXT,
    target_path TEXT,
    target_symbol TEXT NOT NULL,
    kind TEXT NOT NULL,
    evidence TEXT NOT NULL,
    reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manifests (
    profile_id TEXT NOT NULL,
    repository_id TEXT NOT NULL,
    revision TEXT,
    indexed_at TEXT NOT NULL,
    file_count INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL,
    mode TEXT NOT NULL,
    dirty INTEGER NOT NULL,
    warnings_json TEXT NOT NULL,
    PRIMARY KEY (profile_id, repository_id)
);
CREATE INDEX IF NOT EXISTS idx_chunks_profile ON chunks(profile_id, source_id);
CREATE INDEX IF NOT EXISTS idx_symbols_profile ON symbols(profile_id, name);
"""


class SqliteDatabase:
    """One local database file. A failed integrity check is replaced, not reused."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.recovery_warning: str | None = None
        self._connection = _open(path, self)

    def connection(self) -> sqlite3.Connection:
        """Return the open connection."""
        return self._connection

    def close(self) -> None:
        """Close the connection."""
        self._connection.close()


def _open(path: Path, database: SqliteDatabase) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not _healthy(path):
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path.rename(path.with_name(f"{path.name}.corrupt-{stamp}"))
        database.recovery_warning = "index_recovered"
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(_SCHEMA)
    row = connection.execute("SELECT version FROM schema_meta").fetchone()
    if row is None:
        connection.execute("INSERT INTO schema_meta (version) VALUES (1)")
    connection.commit()
    return connection


def _healthy(path: Path) -> bool:
    try:
        quoted = quote(path.resolve().as_posix(), safe="/:")
        probe = sqlite3.connect(f"file:{quoted}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        row = probe.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error:
        return False
    finally:
        probe.close()
    return row is not None and row[0] == "ok"


def require_text(row: sqlite3.Row, key: str) -> str:
    """Read one text column or reject a corrupt row."""
    value = row[key]
    if not isinstance(value, str):
        raise HubError("index_corrupt", "index row had an unexpected type")
    return value
