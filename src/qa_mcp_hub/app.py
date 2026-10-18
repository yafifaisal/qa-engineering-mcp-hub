"""FastMCP application factory.

Purpose: construct a fresh server with the Milestone 00 and 03 registries.
Milestone: 03
Status: IMPLEMENTED
Ownership: app.fastmcp_factory
Dependencies: standalone FastMCP and the local registry.
Expected tests: exact component discovery on both in-memory and stdio transports.
"""

from fastmcp import FastMCP

from qa_mcp_hub import __version__
from qa_mcp_hub.config import HubSettings, load_settings
from qa_mcp_hub.mcp.registry import (
    register_milestone_00,
    register_milestone_03,
    register_milestone_04,
)


def create_app(settings: HubSettings | None = None) -> FastMCP:
    """Create a versioned FastMCP server from validated process settings."""
    effective_settings = settings if settings is not None else load_settings()
    server = FastMCP(effective_settings.server_name, version=__version__)
    register_milestone_00(server)
    register_milestone_03(server)
    register_milestone_04(server)
    return server


mcp = create_app()
