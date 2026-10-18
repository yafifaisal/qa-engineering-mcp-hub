"""Map requirement lines to draft scenario text.

Purpose: show which requirement lines a draft mentions, without running tests.
Milestone: 05
Status: IMPLEMENTED
Ownership: planning.coverage_mapper
Dependencies: Planning models.
Expected tests: missing coverage, text overlap, and no executed-test claim.
"""

from qa_mcp_hub.core.enums import EpistemicStatus
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
