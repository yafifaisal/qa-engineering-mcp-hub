"""FastMCP application factory.

Purpose: construct a fresh server with the explicit Milestone 00 registry.
Milestone: 00
Status: IMPLEMENTED
Ownership: app.fastmcp_factory
Dependencies: standalone FastMCP and the local registry.
Expected tests: exact component discovery on both in-memory and stdio transports.
"""

from fastmcp import FastMCP

from qa_mcp_hub.mcp.registry import register_milestone_00


def create_app() -> FastMCP:
    """Create a FastMCP server containing only implemented M00 components."""
    server = FastMCP("QA Engineering MCP Hub")
    register_milestone_00(server)
    return server


mcp = create_app()
