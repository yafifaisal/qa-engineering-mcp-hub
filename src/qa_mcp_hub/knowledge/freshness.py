"""Compare an indexed revision with the approved checkout.

Purpose: warn when search results come from a stale or missing source.
Milestone: 05
Status: IMPLEMENTED
Ownership: knowledge.freshness
Dependencies: Index manifests and Git metadata.
Expected tests: current, stale, missing, and dirty checkouts.
"""

from qa_mcp_hub.core.enums import EpistemicStatus
from qa_mcp_hub.knowledge.models import FreshnessReport


def assess_freshness(
    repository_id: str,
    *,
    indexed_revision: str | None,
    current_revision: str | None,
    dirty: bool,
) -> FreshnessReport:
    """Label one repository index. A dirty tree is stale even when HEAD matches."""
    if indexed_revision is None or current_revision is None:
        return FreshnessReport(
            repository_id=repository_id,
            state="missing",
            evidence=EpistemicStatus.unknown,
            indexed_revision=indexed_revision,
            current_revision=current_revision,
            warning="indexed revision or checkout revision is missing",
        )
    if indexed_revision != current_revision:
        return FreshnessReport(
            repository_id=repository_id,
            state="stale",
            evidence=EpistemicStatus.inferred,
            indexed_revision=indexed_revision,
            current_revision=current_revision,
            warning="indexed commit does not match the checkout HEAD",
        )
    if dirty:
        return FreshnessReport(
            repository_id=repository_id,
            state="stale",
            evidence=EpistemicStatus.inferred,
            indexed_revision=indexed_revision,
            current_revision=current_revision,
            warning="working tree differs from the indexed commit",
        )
    return FreshnessReport(
        repository_id=repository_id,
        state="current",
        evidence=EpistemicStatus.verified,
        indexed_revision=indexed_revision,
        current_revision=current_revision,
    )
