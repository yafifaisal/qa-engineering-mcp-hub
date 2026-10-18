"""Stdio server entry point.

Purpose: run the FastMCP application over the sole approved M00 transport.
Milestone: 00
Status: IMPLEMENTED
Ownership: server.stdio_transport
Dependencies: FastMCP application factory.
Expected tests: subprocess stdio discovery/invocation and clean shutdown.
"""

from qa_mcp_hub.app import mcp
from qa_mcp_hub.mcp.tools.system import (
    HealthStatus,
    hub_capabilities,
    hub_health,
)

__all__ = ["HealthStatus", "hub_capabilities", "hub_health", "mcp", "serve"]


def serve() -> None:
    """Start stdio; protocol output is the only content written to stdout."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    serve()
