#!/usr/bin/env python3
"""Smoke-test the installed package and its MCP registry.

Purpose: verify the community package version and the registered tool inventory.
Milestone: 11
Status: IMPLEMENTED
Ownership: scripts.install_smoke_test
Dependencies: installed QA Hub package and FastMCP.
Expected tests: invoked from both the project and an isolated wheel environment.
"""

from __future__ import annotations

import asyncio

from fastmcp import Client

from qa_mcp_hub import __version__
from qa_mcp_hub.app import mcp
from qa_mcp_hub.mcp.registry import REGISTERED_TOOL_NAMES


async def check_protocol() -> None:
    """Assert the registered component inventory through an MCP client."""
    async with Client(mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
        resources = {str(item.uri) for item in await client.list_resources()}
        prompts = {prompt.name for prompt in await client.list_prompts()}
        if tools != set(REGISTERED_TOOL_NAMES):
            raise RuntimeError(f"unexpected tools: {sorted(tools)}")
        if resources != {"qa-hub://status"}:
            raise RuntimeError(f"unexpected resources: {sorted(resources)}")
        if prompts != {"qa_hub_orientation"}:
            raise RuntimeError(f"unexpected prompts: {sorted(prompts)}")


def main() -> int:
    """Run package and protocol smoke checks."""
    if __version__ != "0.1.0":
        raise RuntimeError(f"unexpected version: {__version__}")
    asyncio.run(check_protocol())
    print(f"qa-engineering-mcp-hub {__version__} smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
