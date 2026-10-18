"""Reviewable scenario suggestions grounded in indexed sources.

Purpose: draft steps a person can review. Drafts are not executable tests.
Milestone: 05
Status: IMPLEMENTED
Ownership: planning.scenario_builder
Dependencies: Knowledge search, impact findings, and the coverage mapper.
Expected tests: provenance, unknowns, and the refusal to create a workflow.
"""

from qa_mcp_hub.core.enums import EpistemicStatus
from qa_mcp_hub.planning.coverage_mapper import map_coverage
from qa_mcp_hub.planning.models import ScenarioDraft


def generate_test_scenario_draft(
    issue_key: str,
    requirements: list[str] | None = None,
    profile: str | None = None,
) -> ScenarioDraft:
    """Draft review steps from issue-key mentions. No workflow file is written."""
    from qa_mcp_hub.knowledge.service import open_engine

    engine = open_engine()
    try:
        report = engine.find_implementation(issue_key, profile)
        steps = [
            "Read each cited source before treating it as behavior.",
            "Do not execute this draft. It is not a registered test.",
        ]
        unknowns = list(report.warnings)
        if report.relationship is EpistemicStatus.unknown:
            unknowns.append("no indexed source mentions this issue key")
        for mention in report.mentions[:5]:
            citation = mention.citation
            steps.append(
                "Check "
                f"{citation.path} lines {citation.start_line}-{citation.end_line} "
                f"at revision {citation.revision}."
            )
        if report.ticket_read is EpistemicStatus.unknown:
            unknowns.append("jira issue body was not read for this draft")
        evidence = (
            EpistemicStatus.inferred if report.mentions else EpistemicStatus.unknown
        )
        return ScenarioDraft(
            title=f"Review sources that mention {issue_key}",
            issue_key=issue_key,
            steps=tuple(steps),
            evidence=evidence,
            unknowns=tuple(dict.fromkeys(unknowns)),
            coverage=map_coverage(tuple(requirements or ()), tuple(steps)),
        )
    finally:
        engine.close()
