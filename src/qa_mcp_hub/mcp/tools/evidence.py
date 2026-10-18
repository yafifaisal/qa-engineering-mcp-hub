"""MCP tools for evidence generation, completeness, and publication.

Purpose: expose evidence operations without fabricating a missing run.
Milestone: 10
Status: IMPLEMENTED
Ownership: mcp.tools.evidence
Dependencies: Evidence service and approvals.
Expected tests: discovery, completeness, and denied publication.
"""

from datetime import datetime

from qa_mcp_hub.evidence.models import EvidenceManifest, PublicationPreview
from qa_mcp_hub.evidence.service import (
    generate_evidence,
    prepare_evidence,
    publish_evidence,
    validate_evidence,
)


def generate_evidence_tool(
    execution_id: str,
    policy_id: str,
    profile: str | None = None,
    ci_job_id: str = "",
) -> EvidenceManifest:
    """Collect evidence for one stored execution."""
    return generate_evidence(
        execution_id, policy_id, profile=profile, ci_job_id=ci_job_id
    )


def validate_evidence_completeness_tool(
    execution_id: str, profile: str | None = None
) -> EvidenceManifest:
    """Check stored artifacts. This does not change the QA review."""
    return validate_evidence(execution_id, profile=profile)


def prepare_evidence_publication_tool(
    execution_id: str, destination: str, profile: str | None = None
) -> PublicationPreview:
    """Preview publication. This tool does not call a provider."""
    return prepare_evidence(execution_id, destination, profile=profile)


def publish_approved_evidence_tool(
    execution_id: str,
    destination: str,
    approval_token: str,
    confirmed: bool = False,
    qa_review: str = "",
    issue_key: str = "",
    profile: str | None = None,
    now: datetime | None = None,
) -> PublicationPreview:
    """Publish only when the caller supplies an explicit review and approval."""
    from datetime import UTC
    from datetime import datetime as clock

    moment = now or clock.now(UTC)
    return publish_evidence(
        execution_id,
        destination,
        token=approval_token,
        confirmed=confirmed,
        qa_review=qa_review,
        now=moment,
        issue_key=issue_key,
        profile=profile,
    )
