"""Aggregate failures, blocked checks, and unresolved critical defects.

Purpose: recommend review readiness without changing the QA review state.
Milestone: 10
Status: IMPLEMENTED
Ownership: release.risk_engine
Dependencies: Evidence manifests and defect records.
Expected tests: critical defects block readiness and do not approve release.
"""

from qa_mcp_hub.evidence.models import EvidenceCheckStatus, EvidenceManifest
from qa_mcp_hub.release.models import CoverageReport, DefectRecord, ReleaseReport

_OPEN = frozenset({"open", "reopened", "in_progress"})
_RESOLVED = frozenset({"resolved", "closed", "done"})


def assess(
    manifest: EvidenceManifest,
    coverage: CoverageReport,
    defects: tuple[DefectRecord, ...] | None,
    *,
    coverage_recorded: bool,
) -> ReleaseReport:
    """Build a recommendation. The review state argument is copied, not changed."""
    failed = _count(manifest, EvidenceCheckStatus.failed)
    blocked = _count(manifest, EvidenceCheckStatus.blocked)
    incomplete = _count(manifest, EvidenceCheckStatus.inconclusive) + _count(
        manifest, EvidenceCheckStatus.not_executed
    )
    critical = 0
    reasons: list[str] = []
    if defects is None:
        reasons.append("defect register was not provided")
    else:
        for item in defects:
            if item.severity == "critical" and item.state in _OPEN:
                critical += 1
            elif item.severity == "critical" and item.state not in _RESOLVED:
                critical += 1
    if not coverage_recorded:
        reasons.append("requirement map was not provided")
    elif coverage.uncovered:
        reasons.append("mapped requirements were not executed and passed")
    if manifest.overall is not EvidenceCheckStatus.passed:
        reasons.append("mandatory evidence is not a pass")
    if failed:
        reasons.append("executed checks failed")
    if blocked:
        reasons.append("executed checks are blocked")
    if incomplete:
        reasons.append("verification is incomplete")
    if critical:
        reasons.append("unresolved critical defects remain")
    if critical or manifest.overall is EvidenceCheckStatus.blocked:
        recommendation = "BLOCKED"
    elif reasons:
        recommendation = "NOT_READY"
    else:
        recommendation = "READY_FOR_REVIEW"
        reasons.append("this recommendation does not approve the release")
    return ReleaseReport(
        execution_id=manifest.execution_id,
        recommendation=recommendation,
        reasons=tuple(reasons),
        review_state=manifest.review_state,
        coverage_percent=coverage.percent,
        failed_count=failed,
        blocked_count=blocked,
        incomplete_count=incomplete,
        critical_open=critical,
    )


def _count(manifest: EvidenceManifest, status: EvidenceCheckStatus) -> int:
    return sum(1 for item in manifest.checks if item.result is status)
