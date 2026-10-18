"""Normalized ticket and change records for read-only planning tools.

Purpose: carry Jira text and Git references as data, never as instructions.
Milestone: 03
Status: IMPLEMENTED
Ownership: planning.models
Dependencies: Git change records and Pydantic v2.
Expected tests: source URLs, truncation flags, and untrusted content fields.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from qa_mcp_hub.adapters.git.base import ChangeSet, CodeHit
from qa_mcp_hub.core.enums import EpistemicStatus


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


class ImpactFinding(BaseModel):
    """One grounded observation about a changed path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str
    evidence: EpistemicStatus
    path: str
    symbol: str | None = None
    runtime_observed: Literal[False] = False


class ImpactReport(BaseModel):
    """Source-level impact. This is not a complete runtime blast radius."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_id: str
    paths: tuple[str, ...] = ()
    findings: tuple[ImpactFinding, ...] = ()
    unknown_relationships: tuple[str, ...] = ()
    complete_graph: Literal[False] = False
    untrusted_content: bool = True


class CoverageItem(BaseModel):
    """One requirement line and whether a draft mentions it. Tests are not run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement: str
    evidence: EpistemicStatus
    tests_executed: Literal[False] = False


class CoverageMap(BaseModel):
    """Draft overlap only. Nothing in this map is an executed test result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[CoverageItem, ...] = ()
    tests_executed: Literal[False] = False


class ScenarioDraft(BaseModel):
    """A reviewable suggestion. It is not an executable test or a workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    issue_key: str
    steps: tuple[str, ...] = ()
    executable: Literal[False] = False
    workflow_created: Literal[False] = False
    evidence: EpistemicStatus
    unknowns: tuple[str, ...] = ()
    coverage: CoverageMap = Field(default_factory=CoverageMap)
    untrusted_content: bool = True
