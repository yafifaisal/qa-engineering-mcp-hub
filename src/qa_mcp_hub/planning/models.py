"""Normalized ticket and change records for read-only planning tools.

Purpose: carry Jira text and Git references as data, never as instructions.
Milestone: 03
Status: IMPLEMENTED
Ownership: planning.models
Dependencies: Git change records and Pydantic v2.
Expected tests: source URLs, truncation flags, and untrusted content fields.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from qa_mcp_hub.adapters.git.base import ChangeSet, CodeHit


class CodeSearchResult(BaseModel):
    """Code hits pinned to a commit. Snippets are untrusted repository text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    repository: str
    revision: str
    hits: tuple[CodeHit, ...] = ()
    truncated: bool = False
    untrusted_content: bool = True


class TicketAnalysis(BaseModel):
    """One Jira issue. Description, criteria, and comments are untrusted data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    url: str
    summary: str
    issue_type: str | None
    status: str | None
    labels: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    untrusted_description: str = ""
    description_truncated: bool = False
    acceptance_criteria: str = ""
    updated_at: datetime | None = None
    comment_count: int = 0
    comments_status: str = "not_requested"
    linked_issue_keys: tuple[str, ...] = ()
    unknown_custom_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    truncated: bool = False
    untrusted_content: bool = True


class RelatedImplementation(BaseModel):
    """Code references found by searching the issue key, not the description."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_key: str
    issue_url: str
    repository: str
    revision: str | None
    hits: tuple[CodeHit, ...] = ()
    changes: ChangeSet | None = None
    warnings: tuple[str, ...] = ()
    untrusted_content: bool = True
