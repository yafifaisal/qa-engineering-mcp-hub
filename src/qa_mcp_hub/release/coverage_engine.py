"""Calculate requirement coverage from executed mapped cases.

Purpose: count a requirement only when its mapped case ran and passed.
Milestone: 10
Status: IMPLEMENTED
Ownership: release.coverage_engine
Dependencies: Release models and evidence check status.
Expected tests: unexecuted mappings stay uncovered.
"""

from qa_mcp_hub.evidence.models import EvidenceCheckStatus
from qa_mcp_hub.release.models import CoverageReport, MappedRequirement


def calculate_coverage(
    links: tuple[MappedRequirement, ...],
    executed: dict[str, EvidenceCheckStatus],
) -> CoverageReport:
    """Cover a requirement only when a mapped case executed and passed."""
    if not links:
        return CoverageReport(total=0, covered=0, percent=None, uncovered=())
    uncovered: list[str] = []
    covered = 0
    seen: set[str] = set()
    for link in links:
        if link.requirement_id in seen:
            continue
        seen.add(link.requirement_id)
        status = executed.get(link.case_id)
        if status is EvidenceCheckStatus.passed:
            covered += 1
        else:
            uncovered.append(link.requirement_id)
    total = len(seen)
    percent = round(covered * 100 / total) if total else None
    return CoverageReport(
        total=total,
        covered=covered,
        percent=percent,
        uncovered=tuple(uncovered),
    )
