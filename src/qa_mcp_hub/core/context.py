"""Immutable execution context for one provider or repository operation.

Purpose: freeze profile, connection, environment, and source revision together.
Milestone: 02
Status: IMPLEMENTED
Ownership: core.context
Dependencies: Core policy, approval, and audit contracts.
Expected tests: scope isolation, deadline propagation, correlation, and cancellation.
"""

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ExecutionContext(BaseModel):
    """A frozen snapshot. Later profile edits cannot retarget this operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(min_length=1, max_length=128)
    connection_id: str | None = Field(default=None, max_length=128)
    environment: str = Field(min_length=1, max_length=64)
    source_revision: str | None = Field(default=None, max_length=128)
    correlation_id: str = Field(min_length=8, max_length=64)

    @classmethod
    def create(
        cls,
        *,
        profile_id: str,
        connection_id: str | None,
        environment: str,
        source_revision: str | None = None,
        correlation_id: str | None = None,
    ) -> "ExecutionContext":
        """Copy the supplied identity into a new immutable context."""
        return cls(
            profile_id=profile_id,
            connection_id=connection_id,
            environment=environment,
            source_revision=source_revision,
            correlation_id=correlation_id or uuid4().hex,
        )
