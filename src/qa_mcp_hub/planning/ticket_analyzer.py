"""Turn a Jira issue record into a planning analysis.

Purpose: keep acceptance criteria and comments as data for a person to read.
Milestone: 03
Status: IMPLEMENTED
Ownership: planning.ticket_analyzer
Dependencies: Jira records and planning models.
Expected tests: acceptance criteria, unknown fields, and comment permission state.
"""

from qa_mcp_hub.adapters.tickets.jira import JiraIssueRecord
from qa_mcp_hub.planning.models import TicketAnalysis


def analyze_issue(record: JiraIssueRecord) -> TicketAnalysis:
    """Copy provider fields without sending the description to a model."""
    return TicketAnalysis(
        key=record.key,
        url=record.url,
        summary=record.summary,
        issue_type=record.issue_type,
        status=record.status,
        labels=record.labels,
        components=record.components,
        untrusted_description=record.untrusted_description,
        description_truncated=record.description_truncated,
        acceptance_criteria=record.acceptance_criteria,
        updated_at=record.updated_at,
        comment_count=len(record.comments),
        comments_status=record.comments_status,
        linked_issue_keys=record.linked_issue_keys,
        unknown_custom_fields=record.unknown_custom_fields,
        warnings=record.warnings,
        truncated=record.truncated,
    )
