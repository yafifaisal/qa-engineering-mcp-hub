"""Local and remote repository records used by the registry.

Purpose: describe an approved repository without reading its contents.
Milestone: 02
Status: IMPLEMENTED
Ownership: repositories.models
Dependencies: Pydantic v2, provider models, and normalized path contracts.
Expected tests: validation, serialization, identity stability, and path normalization.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from qa_mcp_hub.core.enums import IndexingPermission


class RepositoryKind(StrEnum):
    """How a repository definition identifies its source."""

    local = "local"
    remote = "remote"
    linked = "linked"


class GitMetadata(BaseModel):
    """Read-only local Git facts. Remote URLs have userinfo removed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    branch: str | None
    detached: bool
    remote_url: str | None
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    dirty: bool


class DiscoveredRepository(BaseModel):
    """A local Git directory found inside an approved root and not yet registered."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    suggested_id: str
    display_name: str


class ValidationIssue(BaseModel):
    """One sanitized reason a repository definition is not usable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class RepositoryValidation(BaseModel):
    """Validation outcome. A remote definition never claims a successful API call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_id: str
    ok: bool
    issues: tuple[ValidationIssue, ...] = ()
    metadata: GitMetadata | None = None
    provider_status: str
    protected_patterns: tuple[str, ...] = ()


class IndexPlan(BaseModel):
    """A handoff record for Milestone 05. Creating it does not index files."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_id: str
    revision: str | None
    permission: IndexingPermission
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    status: str = "NOT_EXECUTED"
    reason: str
