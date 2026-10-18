"""Implemented local introspection tools.

Purpose: expose deterministic health and capability facts without external calls.
Milestone: 00
Status: IMPLEMENTED
Ownership: mcp.tools.system
Dependencies: Pydantic settings and capability catalog.
Expected tests: direct calls plus in-memory and stdio MCP invocation.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from qa_mcp_hub import __version__
from qa_mcp_hub.config import load_settings
from qa_mcp_hub.core.capabilities import CapabilityCatalog, list_capabilities


class HealthStatus(BaseModel):
    """Typed local-process readiness response."""

    model_config = ConfigDict(frozen=True)

    status: Literal["healthy"]
    service: str
    version: str
    transport: Literal["stdio"]


def hub_health() -> HealthStatus:
    """Return local server readiness; do not probe future providers."""
    settings = load_settings()
    return HealthStatus(
        status="healthy",
        service=settings.server_name,
        version=__version__,
        transport=settings.transport,
    )


def hub_capabilities() -> CapabilityCatalog:
    """Return implemented and planned capabilities without overstating support."""
    return list_capabilities()
