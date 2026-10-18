"""Registered assertion outcomes and provenance.

Purpose: record what was executed without treating a plan as a result.
Milestone: 07
Status: IMPLEMENTED
Ownership: verification.models
Dependencies: Execution status and Pydantic v2.
Expected tests: outcome invariants and redacted observations.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from qa_mcp_hub.workflows.models import ExecutionStatus


class AssertionDefinition(BaseModel):
    """One reviewed assertion file. The SQL text is not an MCP argument."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    id: str
    kind: Literal["api", "database", "sql", "kafka", "business"]
    implementation_status: Literal["NOT_IMPLEMENTED", "SCAFFOLDED", "IMPLEMENTED"]
    enabled: bool
    connection_id: str | None = None
    definition: dict[str, object]


class CheckResult(BaseModel):
    """One assertion attempt. ``verified`` is true only after a passing run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assertion_id: str
    kind: str
    status: ExecutionStatus
    executed: bool
    verified: bool
    reason: str
    published: bool = False
    consumer_completed: bool = False
    schema_validated: bool = False
    observations: tuple[tuple[str, str], ...] = ()
    warning: str = ""


class AssertionSummary(BaseModel):
    """Public registry row. It omits SQL text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: str
    enabled: bool
    connection_id: str | None = None
    parameters: tuple[str, ...] = ()
    mandatory: bool = True


def summary_for(assertion: AssertionDefinition) -> AssertionSummary:
    """Expose identity and declared parameters without the statement."""
    raw = assertion.definition.get("parameters")
    names: list[str] = []
    if isinstance(raw, list):
        names.extend(str(item) for item in raw)
    key = assertion.definition.get("correlation_key")
    if isinstance(key, str) and key not in names:
        names.append(key)
    mandatory = assertion.definition.get("mandatory", True)
    return AssertionSummary(
        id=assertion.id,
        kind=assertion.kind,
        enabled=assertion.enabled,
        connection_id=assertion.connection_id,
        parameters=tuple(names),
        mandatory=bool(mandatory),
    )


class CorrelationInput(BaseModel):
    """Approved keys supplied with a run. Values are data, not SQL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    values: dict[str, str] = Field(default_factory=dict)
