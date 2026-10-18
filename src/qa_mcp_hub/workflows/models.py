"""Approved workflow documents and execution records.

Purpose: type workflow steps, run status, and API-only evidence.
Milestone: 06
Status: IMPLEMENTED
Ownership: workflows.models
Dependencies: Pydantic v2.
Expected tests: validation, dependency references, and PASS invariants.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutionStatus(StrEnum):
    """Lifecycle of one registered suite or workflow run."""

    queued = "QUEUED"
    running = "RUNNING"
    verifying = "VERIFYING"
    passed = "PASSED"
    failed = "FAILED"
    blocked = "BLOCKED"
    inconclusive = "INCONCLUSIVE"
    cancelled = "CANCELLED"
    timed_out = "TIMED_OUT"
    error = "ERROR"


class StepKind(StrEnum):
    """Workflow step families. Verification steps run only from the registry."""

    api_suite = "api_suite"
    database_assertion = "database_assertion"
    kafka_assertion = "kafka_assertion"
    business_assertion = "business_assertion"


class WorkflowStep(BaseModel):
    """One ordered step. Database and Kafka steps stay unavailable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: StepKind
    target: str
    depends_on: tuple[str, ...] = ()
    assertion_ids: tuple[str, ...] = ()


class WorkflowDefinition(BaseModel):
    """One versioned workflow document from a QA Workspace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    id: str
    name: str
    description: str = ""
    implementation_status: Literal["NOT_IMPLEMENTED", "SCAFFOLDED", "IMPLEMENTED"]
    enabled: bool
    approved: bool = False
    required_capabilities: tuple[str, ...] = ()
    evidence_policy: str
    steps: tuple[WorkflowStep, ...] = Field(min_length=1)
    source_path: str = ""


class WorkflowCandidate(BaseModel):
    """A suggested workflow. Discovery never marks it approved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    reason: str
    approved: Literal[False] = False
    executable: Literal[False] = False


class PlannedStep(BaseModel):
    """One step in a preview. The preview does not start a process."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: StepKind
    target: str
    available: bool
    reason: str
    argv: tuple[str, ...] = ()


class WorkflowExplanation(BaseModel):
    """Immutable plan preview. It has not executed a suite."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_id: str
    name: str
    approved: bool
    enabled: bool
    api_only: bool
    executed: Literal[False] = False
    database_verified: Literal[False] = False
    kafka_verified: Literal[False] = False
    steps: tuple[PlannedStep, ...]
    blocked_reason: str | None = None


class ApiOnlyEvidence(BaseModel):
    """Evidence for checks that actually ran. Unrun checks stay unverified."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["api-only", "e2e"] = "api-only"
    execution_id: str
    profile_id: str
    workflow_id: str
    suite_ids: tuple[str, ...]
    suite_version: str
    source_revision: str | None
    checks: tuple[Literal["api", "database", "kafka", "business"], ...] = ("api",)
    database_verified: bool = False
    kafka_verified: bool = False
    assertion_total: int = Field(ge=0)
    assertion_failed: int = Field(ge=0)
    status: ExecutionStatus
    runner_exit_code: int | None
    runner_completed: bool

    @model_validator(mode="after")
    def pass_requires_assertions(self) -> "ApiOnlyEvidence":
        """A PASS record must contain real assertion results and a clean runner."""
        if self.database_verified and "database" not in self.checks:
            raise ValueError("database verification was not executed")
        if self.kafka_verified and "kafka" not in self.checks:
            raise ValueError("kafka verification was not executed")
        if self.status is ExecutionStatus.passed and (
            self.assertion_total < 1
            or self.assertion_failed > 0
            or (
                "api" in self.checks
                and (not self.runner_completed or self.runner_exit_code != 0)
            )
            or ("database" in self.checks and not self.database_verified)
            or ("kafka" in self.checks and not self.kafka_verified)
        ):
            raise ValueError("PASS requires runner success and actual assertions")
        return self


class StepEvidence(BaseModel):
    """One persisted workflow step. ``verified`` requires an executed pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    kind: str
    target: str
    status: ExecutionStatus
    executed: bool
    verified: bool
    reason: str
    evidence_ref: str


class ExecutionRecord(BaseModel):
    """Persisted run. Runner success and assertion success stay separate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str
    profile_id: str
    workflow_id: str
    suite_ids: tuple[str, ...]
    suite_version: str
    source_revision: str | None
    status: ExecutionStatus
    assertion_status: ExecutionStatus
    runner_completed: bool
    runner_exit_code: int | None
    transitions: tuple[str, ...]
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    evidence: ApiOnlyEvidence
    excerpt: str = ""
    warnings: tuple[str, ...] = ()
    step_results: tuple[StepEvidence, ...] = ()


class RunReceipt(BaseModel):
    """Either a preview or a persisted run. A preview has no execution id."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    executed: bool
    plan: WorkflowExplanation | None = None
    run: ExecutionRecord | None = None
    blocked_reason: str | None = None
