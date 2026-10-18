"""MCP tools for release readiness and reporting.

Purpose: recommend review readiness without approving a release.
Milestone: 10
Status: IMPLEMENTED
Ownership: mcp.tools.release
Dependencies: Release service.
Expected tests: critical defects and an unchanged review state.
"""

from qa_mcp_hub.release.models import ReleaseReport
from qa_mcp_hub.release.service import assess_release, generate_report


def assess_release_readiness_tool(
    execution_id: str, profile: str | None = None
) -> ReleaseReport:
    """Assess readiness. The QA review state is not changed."""
    return assess_release(execution_id, profile=profile)


def generate_release_report_tool(
    execution_id: str, profile: str | None = None
) -> ReleaseReport:
    """Write a release report. ``release_approved`` stays false."""
    return generate_report(execution_id, profile=profile)
