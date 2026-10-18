"""Explicit MCP component registration allowlist.

Purpose: register Milestone 00 status tools and Milestone 03 read-only tools.
Milestone: 03
Status: IMPLEMENTED
Ownership: mcp.registration
Dependencies: standalone FastMCP 4.
Expected tests: exact discovery sets and accidental future-tool exposure audit.
"""

from fastmcp import FastMCP

from qa_mcp_hub.mcp.prompts import qa_hub_orientation
from qa_mcp_hub.mcp.resources import STATUS_RESOURCE_URI, hub_status_resource
from qa_mcp_hub.mcp.tools.knowledge import (
    get_repository_changes_tool,
    read_document_tool,
    search_documents_tool,
    search_repository_code_tool,
)
from qa_mcp_hub.mcp.tools.planning import (
    analyze_jira_ticket_tool,
    find_related_implementation_tool,
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
