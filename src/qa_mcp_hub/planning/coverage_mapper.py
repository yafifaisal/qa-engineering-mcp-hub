"""Map requirement lines to draft scenario text.

Purpose: show which requirement lines a draft mentions, without running tests.
Milestone: 05
Status: IMPLEMENTED
Ownership: planning.coverage_mapper
Dependencies: Planning models.
Expected tests: missing coverage, text overlap, and no executed-test claim.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from qa_mcp_hub.core.enums import EpistemicStatus
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.planning.models import CoverageItem, CoverageMap

_STOP = {"that", "this", "with", "from", "have", "will", "when", "into"}


def map_coverage(requirements: tuple[str, ...], steps: tuple[str, ...]) -> CoverageMap:
    """Compare requirement lines with draft steps. Overlap is not an execution."""
    haystack = " ".join(steps).lower()
    items: list[CoverageItem] = []
    for requirement in requirements:
        words = [
            word
            for word in requirement.lower().split()
            if len(word) > 3 and word not in _STOP
        ]
        matched = any(word in haystack for word in words)
        items.append(
            CoverageItem(
                requirement=requirement[:300],
                evidence=(
                    EpistemicStatus.inferred
                    if matched and words
                    else EpistemicStatus.unknown
                ),
            )
        )
    return CoverageMap(items=tuple(items))


class NormalizedCoverage(BaseModel):
    """A suite correlation. Overlap with a draft is not this report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    automation_suite_id: str
    suite_status: str
    correlated: bool
    evidence: EpistemicStatus


_SUITE_STATUSES = frozenset({"Passed", "Failed", "Blocked", "Untested", "Retest"})


def report_test_coverage(
    links: tuple[tuple[str, str], ...],
    suite_results: Mapping[str, str],
) -> tuple[NormalizedCoverage, ...]:
    """Correlate case suite ids with registered suite results.

    An unknown suite status is a mapping error. A missing suite is unknown,
    and it is not reported as a pass.
    """
    for status in suite_results.values():
        if status not in _SUITE_STATUSES:
            raise HubError("mapping_rejected", "suite result status is not mapped")
    rows: list[NormalizedCoverage] = []
    for source_id, suite_id in links:
        if suite_id and suite_id in suite_results:
            status = suite_results[suite_id]
            rows.append(
                NormalizedCoverage(
                    source_id=source_id,
                    automation_suite_id=suite_id,
                    suite_status=status,
                    correlated=True,
                    evidence=EpistemicStatus.verified,
                )
            )
            continue
        rows.append(
            NormalizedCoverage(
                source_id=source_id,
                automation_suite_id=suite_id,
                suite_status="",
                correlated=False,
                evidence=EpistemicStatus.unknown,
            )
        )
    return tuple(rows)
