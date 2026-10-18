"""Explicit MCP component registration allowlist.

Purpose: register status, read-only provider, knowledge, and execution tools.
Milestone: 06
Status: IMPLEMENTED
Ownership: mcp.registration
Dependencies: standalone FastMCP 4.
Expected tests: exact discovery sets and accidental future-tool exposure audit.
"""

from fastmcp import FastMCP

from qa_mcp_hub.mcp.prompts import qa_hub_orientation
from qa_mcp_hub.mcp.resources import STATUS_RESOURCE_URI, hub_status_resource
from qa_mcp_hub.mcp.tools.execution import (
    explain_workflow_tool,
    get_test_run_tool,
    list_registered_suites_tool,
    list_workflows_tool,
    submit_test_run_tool,
)
from qa_mcp_hub.mcp.tools.knowledge import (
    find_implementation_tool,
    get_repository_changes_tool,
    read_document_tool,
    search_documents_tool,
    search_knowledge_tool,
    search_repository_code_tool,
    trace_cross_repo_flow_tool,
)
from qa_mcp_hub.mcp.tools.planning import (
    analyze_change_impact_tool,
    analyze_jira_ticket_tool,
    find_related_implementation_tool,
    generate_test_scenario_draft_tool,
)
from qa_mcp_hub.mcp.tools.system import hub_capabilities, hub_health


def register_milestone_00(server: FastMCP) -> None:
    """Register the complete and exclusive M00 MCP surface."""
    server.tool(hub_health, name="hub_health")
    server.tool(hub_capabilities, name="hub_capabilities")
    server.resource(
        STATUS_RESOURCE_URI,
        name="hub_status",
        description="Local Milestone 00 health and capability status.",
        mime_type="application/json",
    )(hub_status_resource)
    server.prompt(
        qa_hub_orientation,
        name="qa_hub_orientation",
        description="Orient a client to truthful QA Hub capability reporting.",
    )


def register_milestone_03(server: FastMCP) -> None:
    """Register read-only Git and Jira tools. Repository text is data."""
    server.tool(search_repository_code_tool, name="search_repository_code")
    server.tool(get_repository_changes_tool, name="get_repository_changes")
    server.tool(analyze_jira_ticket_tool, name="analyze_jira_ticket")
    server.tool(find_related_implementation_tool, name="find_related_implementation")


def register_milestone_04(server: FastMCP) -> None:
    """Register read-only documentation tools. Document text is data."""
    server.tool(search_documents_tool, name="search_documents")
    server.tool(read_document_tool, name="read_document")


def register_milestone_05(server: FastMCP) -> None:
    """Register local knowledge and planning tools. They do not execute tests."""
    server.tool(search_knowledge_tool, name="search_knowledge")
    server.tool(find_implementation_tool, name="find_implementation")
    server.tool(trace_cross_repo_flow_tool, name="trace_cross_repo_flow")
    server.tool(analyze_change_impact_tool, name="analyze_change_impact")
    server.tool(generate_test_scenario_draft_tool, name="generate_test_scenario_draft")


def register_milestone_06(server: FastMCP) -> None:
    """Register registered-suite tools. They do not accept a shell command."""
    server.tool(list_registered_suites_tool, name="list_registered_suites")
    server.tool(list_workflows_tool, name="list_workflows")
    server.tool(explain_workflow_tool, name="explain_workflow")
    server.tool(submit_test_run_tool, name="submit_test_run")
    server.tool(get_test_run_tool, name="get_test_run")
