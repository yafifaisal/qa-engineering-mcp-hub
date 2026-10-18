"""Truthful local capability catalog through Milestone 11.

The catalog distinguishes registered tools from work that is not published.

Purpose: separate callable local capabilities from planned provider work.
Milestone: 06
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
            "list_registered_suites",
            "list_workflows",
            "explain_workflow",
            "submit_test_run",
            "get_test_run",
            "list_registered_assertions",
            "run_database_assertion",
            "find_kafka_event",
            "verify_e2e_workflow",
            "list_pipeline_runs",
            "get_pipeline_status",
            "get_pipeline_artifacts",
            "prepare_pipeline_trigger",
            "search_test_cases",
            "compare_test_cases",
            "preview_test_case_import",
            "export_test_cases",
            "prepare_result_publication",
            "generate_evidence",
            "validate_evidence_completeness",
            "prepare_evidence_publication",
            "publish_approved_evidence",
            "assess_release_readiness",
            "generate_release_report",
            "community_package",
        ),
        planned=(),
    )
