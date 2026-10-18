"""Decide whether mandatory evidence is complete.

Purpose: keep an overall PASS from a run that skipped a required check.
Milestone: 10
Status: IMPLEMENTED
Ownership: evidence.completeness
Dependencies: Evidence policy and check models.
Expected tests: API-only omission and missing E2E evidence.
"""

from qa_mcp_hub.evidence.models import (
    EvidenceCheck,
    EvidenceCheckStatus,
    EvidencePolicy,
)

_RANK = {
    EvidenceCheckStatus.failed: 5,
    EvidenceCheckStatus.blocked: 4,
    EvidenceCheckStatus.inconclusive: 3,
    EvidenceCheckStatus.not_executed: 2,
    EvidenceCheckStatus.passed: 1,
    EvidenceCheckStatus.not_applicable: 0,
}


def overall_status(
    policy: EvidencePolicy, checks: tuple[EvidenceCheck, ...]
) -> EvidenceCheckStatus:
    """Return PASSED only when every required check ran and passed."""
    by_name = {item.name: item for item in checks}
    results: list[EvidenceCheckStatus] = []
    for name in policy.required_checks:
        item = by_name.get(name)
        if item is None or not item.executed:
            results.append(EvidenceCheckStatus(policy.missing_required_result))
            continue
        results.append(item.result)
    if not results:
        return EvidenceCheckStatus.inconclusive
    worst = max(results, key=lambda item: _RANK[item])
    if worst is EvidenceCheckStatus.passed and any(
        item is not EvidenceCheckStatus.passed for item in results
    ):
        return EvidenceCheckStatus.inconclusive
    return worst
