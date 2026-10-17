"""In-memory MCP calls exercise protocol registration, not just Python functions."""

import pytest
from fastmcp import Client

from qa_mcp_hub.server import mcp


@pytest.mark.asyncio
async def test_mcp_tool_discovery_and_invocation() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools}
        assert {"hub_health", "hub_capabilities"} <= names

        health = await client.call_tool("hub_health", {})
        assert not health.is_error
        assert health.structured_content is not None
        assert health.structured_content["status"] == "healthy"
        assert health.structured_content["version"] == "0.1.0"

        catalog = await client.call_tool("hub_capabilities", {})
        assert not catalog.is_error
        assert catalog.structured_content is not None
        assert "profiles_and_credentials" in catalog.structured_content["planned"]
