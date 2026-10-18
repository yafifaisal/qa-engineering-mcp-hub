"""Single-use approvals for a pipeline trigger.

Purpose: bind one trigger to a job, a parameter digest, and an expiry.
Milestone: 08
Status: IMPLEMENTED
Ownership: core.approvals
Dependencies: Core errors.
Expected tests: expiry, single use, action binding, and digest mismatch.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from qa_mcp_hub.core.errors import HubError


class ApprovalGrant(BaseModel):
    """A one-time permission to trigger one registered job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    token: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    action: str = "pipeline_trigger"
    job_id: str
    parameter_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime


class ApprovalLedger:
    """In-memory single-use ledger. A consumed grant cannot be reused."""

    def __init__(self) -> None:
        self._issued: dict[str, ApprovalGrant] = {}
        self._used: set[str] = set()

    def issue(self, grant: ApprovalGrant) -> ApprovalGrant:
        """Record a grant. The same token cannot be issued twice."""
        if grant.action != "pipeline_trigger":
            raise HubError("approval_rejected", "approval action is not a trigger")
        if grant.token in self._issued:
            raise HubError("approval_rejected", "approval token is already issued")
        self._issued[grant.token] = grant
        return grant

    def consume(
        self,
        token: str,
        *,
        job_id: str,
        parameter_digest: str,
        now: datetime,
    ) -> None:
        """Spend a matching grant. Expiry and reuse both fail closed."""
        grant = self._issued.get(token)
        if grant is None or token in self._used:
            raise HubError("approval_rejected", "approval is missing or already used")
        if grant.job_id != job_id or grant.parameter_digest != parameter_digest:
            raise HubError("approval_rejected", "approval does not match this trigger")
        if grant.expires_at <= now:
            raise HubError("approval_rejected", "approval has expired")
        self._used.add(token)
