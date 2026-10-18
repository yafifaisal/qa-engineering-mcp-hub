"""Versioned evidence policies, checks, and manifests.

Purpose: keep evidence facts tied to one execution and one review state.
Milestone: 10
Status: IMPLEMENTED
Ownership: evidence.models
Dependencies: Pydantic v2.
Expected tests: status separation, policy validation, and manifest identity.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCheckStatus(StrEnum):
    """Outcome of one evidence check. These values are not execution statuses."""

    passed = "PASSED"
    failed = "FAILED"
    not_executed = "NOT_EXECUTED"
    not_applicable = "NOT_APPLICABLE"
    blocked = "BLOCKED"
    inconclusive = "INCONCLUSIVE"


class ReviewState(StrEnum):
    """QA review of a manifest. It is not copied from the execution status."""

    unreviewed = "UNREVIEWED"
    approved = "APPROVED"
    rejected = "REJECTED"


class RedactionSettings(BaseModel):
    """How collected text is sanitized before it can be stored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: str
    block_on_secret_detection: bool


class EvidencePolicy(BaseModel):
    """One versioned evidence policy loaded from the QA workspace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(ge=1, le=1)
    id: str
    name: str
    implementation_status: str
    required_checks: tuple[str, ...]
    optional_checks: tuple[str, ...] = ()
    missing_required_result: str
    redaction: RedactionSettings
    external_publication: str = "deny"


class EvidenceCheck(BaseModel):
    """One check. Detail is present only when that check actually ran."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    result: EvidenceCheckStatus
    executed: bool
    evidence_reference: str
    detail: str = ""


class EvidenceArtifact(BaseModel):
    """A stored report file and the digest used for a tamper check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    sha256: str
    size: int = Field(ge=0)


class EvidenceManifest(BaseModel):
    """Evidence for one execution. Review state starts unreviewed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    execution_id: str
    profile_id: str
    policy_id: str
    suite_version: str
    source_revision: str
    generated_at: datetime
    overall: EvidenceCheckStatus
    checks: tuple[EvidenceCheck, ...]
    artifacts: tuple[EvidenceArtifact, ...] = ()
    review_state: ReviewState = ReviewState.unreviewed
    limitations: tuple[str, ...] = ()
    http_excerpt: str = ""


class PublicationPreview(BaseModel):
    """A publication plan. The preview itself does not contact a provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    executed: bool = False
    reason: str
    execution_id: str
    destination: str
    review_state: ReviewState = ReviewState.unreviewed
