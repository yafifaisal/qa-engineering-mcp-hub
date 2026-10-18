"""MCP discovery and invocation over in-memory and real stdio transports."""

import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from qa_mcp_hub import __version__
from qa_mcp_hub.mcp.registry import REGISTERED_TOOL_NAMES
from qa_mcp_hub.server import mcp

EXPECTED_TOOLS = set(REGISTERED_TOOL_NAMES)
EXPECTED_RESOURCES = {"qa-hub://status"}
EXPECTED_PROMPTS = {"qa_hub_orientation"}


@pytest.mark.asyncio
async def test_mcp_tool_discovery_and_invocation() -> None:
    async with Client(mcp) as client:
        assert client.server_info is not None
        assert client.server_info.name == "QA Engineering MCP Hub"
        assert client.server_info.version == __version__
        tools = await client.list_tools()
        names = {tool.name for tool in tools}
        assert names == EXPECTED_TOOLS

        health = await client.call_tool("hub_health", {})
        assert not health.is_error
        assert health.structured_content is not None
        assert health.structured_content["status"] == "healthy"
        assert health.structured_content["version"] == "0.1.0"
        assert health.structured_content["transport"] == "stdio"

        catalog = await client.call_tool("hub_capabilities", {})
        assert not catalog.is_error
        assert catalog.structured_content is not None
        implemented = catalog.structured_content["implemented"]
        planned = catalog.structured_content["planned"]
        assert "profiles_and_credentials" in implemented
        assert "interactive_setup" in implemented
        assert "search_repository_code" in implemented
        assert "search_documents" in implemented
        assert "search_knowledge" in implemented
        assert "generate_test_scenario_draft" in implemented
        assert "list_registered_suites" in implemented
        assert "submit_test_run" in implemented
        assert "verify_e2e_workflow" in implemented
        assert "postgresql_mysql_kafka" not in planned
        assert "bruno_postman" not in planned


@pytest.mark.asyncio
async def test_mcp_resource_and_prompt_availability() -> None:
    async with Client(mcp) as client:
        resources = await client.list_resources()
        assert {str(resource.uri) for resource in resources} == EXPECTED_RESOURCES
        content = await client.read_resource("qa-hub://status")
        payload = json.loads(content[0].text)
        assert payload["health"]["status"] == "healthy"
        assert payload["external_integrations"] == (
            "git_jira_docs_read_only_local_knowledge_registered_e2e_ci_read_test_cases_evidence"
        )

        prompts = await client.list_prompts()
        assert {prompt.name for prompt in prompts} == EXPECTED_PROMPTS
        rendered = await client.get_prompt("qa_hub_orientation")
        assert len(rendered.messages) == 1
        prompt_text = rendered.messages[0].content.text
        assert "credential references are implemented" in prompt_text
        assert "Milestone 03 read-only GitHub, GitLab, Bitbucket, and Jira" in (
            prompt_text
        )
        assert "Milestone 04 read-only Confluence and Google Docs" in prompt_text
        assert "Milestone 05 local knowledge" in prompt_text
        assert "Milestone 06 runs only registered Bruno and Newman" in prompt_text
        assert "Milestone 07 runs registered read-only database" in prompt_text
        assert "Milestone 08 reads registered" in prompt_text
        assert "Milestone 09 maps" in prompt_text
        assert "Milestone 10 collects evidence" in prompt_text
        assert "Milestone 11 packages the Community Edition" in prompt_text
        assert "does not publish" in prompt_text


@pytest.mark.asyncio
@pytest.mark.stdio
async def test_stdio_subprocess_protocol() -> None:
    project_root = Path(__file__).resolve().parents[2]
    entrypoint_name = "qa-mcp.exe" if sys.platform == "win32" else "qa-mcp"
    entrypoint = Path(sys.executable).with_name(entrypoint_name)
    assert entrypoint.is_file()
    transport = StdioTransport(
        command=str(entrypoint),
        args=["serve"],
        cwd=str(project_root),
        keep_alive=False,
    )
    async with Client(transport, timeout=10) as client:
        assert client.server_info is not None
        assert client.server_info.name == "QA Engineering MCP Hub"
        assert client.server_info.version == __version__
        assert {tool.name for tool in await client.list_tools()} == EXPECTED_TOOLS
        health = await client.call_tool("hub_health", {})
        assert health.structured_content is not None
        assert health.structured_content["status"] == "healthy"
        assert {
            str(resource.uri) for resource in await client.list_resources()
        } == EXPECTED_RESOURCES
        assert {
            prompt.name for prompt in await client.list_prompts()
        } == EXPECTED_PROMPTS
