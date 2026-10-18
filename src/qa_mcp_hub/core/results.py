"""Normalized operation results and source references.

Purpose: carry pagination, provenance, and error status without provider payloads.
Milestone: 02
Status: IMPLEMENTED
Ownership: core.results
Dependencies: Core enums, models, errors, and source references.
Expected tests: state validation, deterministic serialization, and evidence rules.
"""

from pydantic import BaseModel, ConfigDict, Field

from qa_mcp_hub.core.enums import EpistemicStatus, OperationStatus
from qa_mcp_hub.core.errors import HubError


class Pagination(BaseModel):
    """A bounded page request. Callers choose the cursor; providers do not."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=256)


class SourceReference(BaseModel):
    """Where a future evidence item would have come from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str | None = None
    repository_id: str | None = None
    revision: str | None = None
    path: str | None = None


class ToolResult(BaseModel):
    """A normalized tool outcome. Success is never implied by an empty payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: OperationStatus
    epistemic: EpistemicStatus
    summary: str = Field(min_length=1, max_length=512)
    source: SourceReference | None = None
    error_code: str | None = None


def result_from_error(
    error: HubError, *, source: SourceReference | None = None
) -> ToolResult:
    """Map a typed error into a result without attaching the exception payload."""
    status = (
        OperationStatus(error.code)
        if error.code in {item.value for item in OperationStatus}
        else OperationStatus.failed
    )
    epistemic = (
        EpistemicStatus.unknown
        if status is not OperationStatus.success
        else EpistemicStatus.verified
    )
    return ToolResult(
        status=status,
        epistemic=epistemic,
        summary=error.message,
        source=source,
        error_code=error.code,
    )
