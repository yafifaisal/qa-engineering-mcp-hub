"""Rank approved workflows and suggest unapproved candidates.

Purpose: match a ticket or a change set without approving anything.
Milestone: 06
Status: IMPLEMENTED
Ownership: workflows.matcher
Dependencies: Workflow and suite identities.
Expected tests: exact, ambiguous, and no-match results.
"""

from qa_mcp_hub.suites.models import SuiteDefinition
from qa_mcp_hub.workflows.models import WorkflowCandidate, WorkflowDefinition


def match_workflows(
    workflows: tuple[WorkflowDefinition, ...],
    *,
    issue_key: str | None,
    changed_paths: tuple[str, ...],
) -> tuple[WorkflowDefinition, ...]:
    """Return approved workflows that mention the key or a changed path."""
    ranked: list[tuple[int, WorkflowDefinition]] = []
    for workflow in workflows:
        if not workflow.approved:
            continue
        score = 0
        text = f"{workflow.id} {workflow.name} {workflow.description}"
        if issue_key and issue_key in text:
            score += 2
        for path in changed_paths:
            if path and path in text:
                score += 1
        if score:
            ranked.append((score, workflow))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    return tuple(item[1] for item in ranked)


def suggest_candidates(
    suites: tuple[SuiteDefinition, ...],
    *,
    issue_key: str | None,
    changed_paths: tuple[str, ...],
) -> tuple[WorkflowCandidate, ...]:
    """Suggest suites that overlap a change. Every suggestion stays unapproved."""
    if issue_key is None and not changed_paths:
        return ()
    candidates: list[WorkflowCandidate] = []
    for suite in suites:
        reason = _reason(suite, issue_key, changed_paths)
        if reason is None:
            continue
        candidates.append(WorkflowCandidate(id=f"candidate-{suite.id}", reason=reason))
    return tuple(candidates)


def _reason(
    suite: SuiteDefinition,
    issue_key: str | None,
    changed_paths: tuple[str, ...],
) -> str | None:
    if issue_key and issue_key.lower() in suite.id:
        return f"suite id overlaps {issue_key}; not approved"
    for path in changed_paths:
        if path and (path in suite.path or suite.path in path):
            return f"suite path overlaps {path}; not approved"
    return None
