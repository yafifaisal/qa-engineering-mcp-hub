"""Truthful local capability catalog through Milestone 05.

The catalog distinguishes local knowledge tools and read-only provider tools
from providers that remain future work.

Purpose: separate callable local capabilities from planned provider work.
Milestone: 05
Status: IMPLEMENTED
Ownership: core.capabilities
Dependencies: Pydantic.
Expected tests: implemented local setup and planned provider identifiers.
"""

from pydantic import BaseModel, ConfigDict


class CapabilityCatalog(BaseModel):
    """Immutable implemented-versus-planned capability response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    implemented: tuple[str, ...]
    planned: tuple[str, ...]


def list_capabilities() -> CapabilityCatalog:
    """Return local capabilities without probing or claiming provider support."""
    return CapabilityCatalog(
        implemented=(
            "hub_health",
            "hub_capabilities",
            "qa-hub://status",
            "qa_hub_orientation",
            "profiles_and_credentials",
            "interactive_setup",
            "mcp_client_config_generation",
            "provider_contracts",
            "repository_registry",
            "search_repository_code",
            "get_repository_changes",
            "analyze_jira_ticket",
            "find_related_implementation",
            "search_documents",
            "read_document",
            "search_knowledge",
            "find_implementation",
            "trace_cross_repo_flow",
            "analyze_change_impact",
            "generate_test_scenario_draft",
        ),
        planned=(
            "bruno_postman",
            "postgresql_mysql_kafka",
            "bitbucket_pipelines_github_actions_jenkins",
            "xray_testrail_spreadsheet",
            "qa_evidence_and_release",
        ),
    )
