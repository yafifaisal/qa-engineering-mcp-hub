"""Explicit MCP component registration allowlist.

Purpose: register only Milestone 00 tools, resources, and prompts.
Milestone: 00
Status: IMPLEMENTED
Ownership: mcp.registration
Dependencies: standalone FastMCP 4.
Expected tests: exact discovery sets and accidental future-tool exposure audit.
"""

from fastmcp import FastMCP

from qa_mcp_hub.mcp.prompts import qa_hub_orientation
from qa_mcp_hub.mcp.resources import STATUS_RESOURCE_URI, hub_status_resource
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
