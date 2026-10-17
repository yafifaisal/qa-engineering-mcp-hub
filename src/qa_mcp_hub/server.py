"""Standalone FastMCP server with read-only introspection tools."""

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict

from qa_mcp_hub import __version__
from qa_mcp_hub.capabilities import CapabilityCatalog, list_capabilities
from qa_mcp_hub.config import HubSettings

mcp = FastMCP("QA Engineering MCP Hub")


class HealthStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: str
    service: str
    version: str


@mcp.tool
def hub_health() -> HealthStatus:
    """Check server readiness; does not test future third-party integrations."""
    settings = HubSettings()
    return HealthStatus(
        status="healthy", service=settings.server_name, version=__version__
    )


@mcp.tool
def hub_capabilities() -> CapabilityCatalog:
    """List working versus future capabilities without overstating support."""
    return list_capabilities()


def serve() -> None:
    """Start the MCP stdio transport; stdout is reserved for MCP protocol."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    serve()
