"""Immutable facts captured when a run is submitted.

Purpose: freeze profile, suite version, and limits for one execution.
Milestone: 06
Status: IMPLEMENTED
Ownership: runners.execution_context
Dependencies: Pydantic.
Expected tests: immutability and scope isolation.
"""

from pydantic import BaseModel, ConfigDict


class ExecutionContext(BaseModel):
    """Snapshot used by a run. Later configuration edits do not change it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str
    profile_id: str
    workflow_id: str
    suite_ids: tuple[str, ...]
    suite_version: str
    source_revision: str | None
    timeout_seconds: int
    environment: str | None
    allow_mutations: bool
