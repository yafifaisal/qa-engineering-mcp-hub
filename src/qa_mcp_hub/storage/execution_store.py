"""Durable execution records in a local SQLite file.

Purpose: persist run state per profile and recover a corrupt file.
Milestone: 06
Status: IMPLEMENTED
Ownership: storage.execution_store
Dependencies: Execution records and SQLite.
Expected tests: profile isolation, recovery, and terminal reads.
"""

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.workflows.models import ExecutionRecord, ExecutionStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    execution_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    status TEXT NOT NULL,
    record_json TEXT NOT NULL
);
"""


class ExecutionStore:
    """Profile-scoped run records. Writes are serialized."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.recovery_warning: str | None = None
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not _healthy(path):
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            path.rename(path.with_name(f"{path.name}.corrupt-{stamp}"))
            self.recovery_warning = "execution_store_recovered"
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            row = connection.execute("SELECT version FROM schema_meta").fetchone()
            if row is None:
                connection.execute("INSERT INTO schema_meta (version) VALUES (1)")
            connection.commit()

    def save(self, record: ExecutionRecord) -> None:
        """Insert or replace one profile-owned record."""
        payload = record.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (execution_id, profile_id, status, record_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(execution_id) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    status = excluded.status,
                    record_json = excluded.record_json
                """,
                (record.execution_id, record.profile_id, record.status.value, payload),
            )
            connection.commit()

    def get(self, profile_id: str, execution_id: str) -> ExecutionRecord:
        """Return one record when the profile matches."""
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT record_json FROM runs
                WHERE execution_id = ? AND profile_id = ?
                """,
                (execution_id, profile_id),
            ).fetchone()
        if row is None:
            raise HubError(
                "unknown_execution", "execution was not found for this profile"
            )
        text = row[0]
        if not isinstance(text, str):
            raise HubError("execution_corrupt", "execution row had an unexpected type")
        return ExecutionRecord.model_validate_json(text)

    def status_of(self, profile_id: str, execution_id: str) -> ExecutionStatus:
        """Read the current status without leaving the profile scope."""
        return self.get(profile_id, execution_id).status

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
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


def dumps_preview(record: ExecutionRecord) -> str:
    """Serialize a record without adding fields."""
    return json.dumps(json.loads(record.model_dump_json()), sort_keys=True)
