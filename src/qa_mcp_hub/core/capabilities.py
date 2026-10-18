"""Truthful Milestone 00 capability catalog.

Purpose: distinguish callable local features from planned milestone ownership.
Milestone: 00
Status: IMPLEMENTED
Ownership: core.capability_catalog
Dependencies: Pydantic v2.
Expected tests: unit catalog assertions and MCP/CLI discovery tests.
"""

from pydantic import BaseModel, ConfigDict


class CapabilityCatalog(BaseModel):
    """Immutable implemented-versus-planned capability response."""

    model_config = ConfigDict(frozen=True)

    implemented: tuple[str, ...]
    planned: tuple[str, ...]


def list_capabilities() -> CapabilityCatalog:
    """Return the fixed M00 catalog without probing future integrations."""
    return CapabilityCatalog(
        implemented=(
            "hub_health",
            "hub_capabilities",
            "qa-hub://status",
            "qa_hub_orientation",
        ),
        planned=(
            "profiles_and_credentials",
            "github_gitlab_bitbucket",
            "jira_confluence_google_docs",
            "bruno_postman",
            "postgresql_mysql_kafka",
            "bitbucket_pipelines_github_actions_jenkins",
            "xray_testrail_spreadsheet",
            "qa_evidence_and_release",
        ),
    )
