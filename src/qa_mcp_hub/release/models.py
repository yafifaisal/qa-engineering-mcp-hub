"""Release coverage, risk, and recommendation records.

Purpose: describe readiness without an approval flag that can be set true.
Milestone: 10
Status: IMPLEMENTED
Ownership: release.models
Dependencies: Pydantic v2 and evidence review state.
Expected tests: recommendation independence from review state.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from qa_mcp_hub.evidence.models import ReviewState


class MappedRequirement(BaseModel):
    """One requirement linked to a case id that must have executed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str
    case_id: str


class DefectRecord(BaseModel):
    """One defect supplied by a register. Severity is not inferred."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    severity: str
    state: str


class CoverageReport(BaseModel):
    """Coverage computed only from mapped cases that actually executed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int = Field(ge=0)
    covered: int = Field(ge=0)
    percent: int | None
    uncovered: tuple[str, ...] = ()


class ReleaseReport(BaseModel):
    """A recommendation. ``release_approved`` cannot be true."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str
    recommendation: str
    reasons: tuple[str, ...]
    review_state: ReviewState
    release_approved: Literal[False] = False
    coverage_percent: int | None
    failed_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    incomplete_count: int = Field(ge=0)
    critical_open: int = Field(ge=0)
