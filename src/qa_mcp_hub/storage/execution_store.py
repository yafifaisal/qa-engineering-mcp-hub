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
from qa_mcp_hub.workflows.models import ExecutionRecord, ExecutionStatus, StepEvidence

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
CREATE TABLE IF NOT EXISTS step_results (
    execution_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY (execution_id, step_id)
);
CREATE TABLE IF NOT EXISTS ci_observations (
    observation_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    job_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    pipeline_status TEXT NOT NULL,
    record_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_manifests (
    execution_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    review_state TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    PRIMARY KEY (execution_id, profile_id)
);
CREATE TABLE IF NOT EXISTS evidence_publications (
    digest TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    state TEXT NOT NULL
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
            connection.execute(
                """
                DELETE FROM step_results
                WHERE execution_id = ? AND profile_id = ?
                """,
                (record.execution_id, record.profile_id),
            )
            for step in record.step_results:
                connection.execute(
                    """
                    INSERT INTO step_results (
                        execution_id, profile_id, step_id, status, result_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.execution_id,
                        record.profile_id,
                        step.step_id,
                        step.status.value,
                        step.model_dump_json(),
                    ),
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

    def steps(self, profile_id: str, execution_id: str) -> tuple[StepEvidence, ...]:
        """Return persisted step rows for one profile-owned execution."""
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT result_json FROM step_results
                WHERE execution_id = ? AND profile_id = ?
                ORDER BY step_id
                """,
                (execution_id, profile_id),
            ).fetchall()
        return tuple(StepEvidence.model_validate_json(str(row[0])) for row in rows)

    def save_ci_observation(
        self,
        *,
        profile_id: str,
        provider: str,
        job_id: str,
        run_id: str,
        pipeline_status: str,
        record_json: str,
    ) -> None:
        """Store one CI observation. The status column is not a QA assertion."""
        observation_id = f"{profile_id}:{job_id}:{run_id}"
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ci_observations (
                    observation_id, profile_id, provider, job_id, run_id,
                    pipeline_status, record_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(observation_id) DO UPDATE SET
                    pipeline_status = excluded.pipeline_status,
                    record_json = excluded.record_json
                """,
                (
                    observation_id,
                    profile_id,
                    provider,
                    job_id,
                    run_id,
                    pipeline_status,
                    record_json,
                ),
            )
            connection.commit()

    def ci_observations(self, profile_id: str, job_id: str) -> tuple[str, ...]:
        """Return CI JSON for one profile and job."""
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT record_json FROM ci_observations
                WHERE profile_id = ? AND job_id = ?
                ORDER BY run_id
                """,
                (profile_id, job_id),
            ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def save_manifest(
        self, profile_id: str, execution_id: str, manifest_json: str
    ) -> None:
        """Store a manifest. An existing review state is left unchanged."""
        with self._lock, self._connect() as connection:
            current = connection.execute(
                """
                SELECT review_state FROM evidence_manifests
                WHERE execution_id = ? AND profile_id = ?
                """,
                (execution_id, profile_id),
            ).fetchone()
            review = "UNREVIEWED" if current is None else str(current["review_state"])
            connection.execute(
                """
                INSERT INTO evidence_manifests (
                    execution_id, profile_id, review_state, manifest_json
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(execution_id, profile_id) DO UPDATE SET
                    manifest_json = excluded.manifest_json
                """,
                (execution_id, profile_id, review, manifest_json),
            )
            connection.commit()

    def manifest_row(self, profile_id: str, execution_id: str) -> tuple[str, str]:
        """Return the stored review state and manifest JSON."""
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT review_state, manifest_json FROM evidence_manifests
                WHERE execution_id = ? AND profile_id = ?
                """,
                (execution_id, profile_id),
            ).fetchone()
        if row is None:
            raise HubError("unknown_execution", "evidence manifest was not found")
        return str(row["review_state"]), str(row["manifest_json"])

    def set_review_state(self, profile_id: str, execution_id: str, state: str) -> None:
        """Record an explicit QA review. Execution status is not an input."""
        if state not in {"UNREVIEWED", "APPROVED", "REJECTED"}:
            raise HubError("approval_rejected", "review state is not recognized")
        with self._lock, self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE evidence_manifests
                SET review_state = ?
                WHERE execution_id = ? AND profile_id = ?
                """,
                (state, execution_id, profile_id),
            )
            if updated.rowcount != 1:
                raise HubError("unknown_execution", "evidence manifest was not found")
            connection.commit()

    def publication_state(self, digest: str) -> str | None:
        """Return a prior publication state for this evidence digest."""
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT state FROM evidence_publications WHERE digest = ?",
                (digest,),
            ).fetchone()
        if row is None:
            return None
        return str(row["state"])

    def record_publication(
        self, *, digest: str, execution_id: str, profile_id: str, state: str
    ) -> None:
        """Remember one publication attempt. A later call does not send again."""
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO evidence_publications (
                    digest, execution_id, profile_id, state
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(digest) DO UPDATE SET state = excluded.state
                """,
                (digest, execution_id, profile_id, state),
            )
            connection.commit()

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
