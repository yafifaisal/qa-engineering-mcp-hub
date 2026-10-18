"""MCP invocation of the read-only Git and Jira tools against mocked HTTP."""

import httpx
import pytest
import respx
from fastmcp import Client

from qa_mcp_hub.auth.models import (
    AuthKind,
    CredentialReference,
    CredentialScope,
    CredentialStoreKind,
)
from qa_mcp_hub.config.models import (
    ConnectionConfig,
    DeploymentKind,
    HubConfig,
    ProfileConfig,
)
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.planning import service
from qa_mcp_hub.server import mcp

SHA = "d" * 40


def _credential(
    connection_id: str,
    provider: ProviderKind,
    host: str,
    reference: str,
    kind: AuthKind,
    account: str,
) -> CredentialReference:
    return CredentialReference(
        store=CredentialStoreKind.environment,
        reference=reference,
        scope=CredentialScope(
            profile="lab",
            provider=provider,
            connection_id=connection_id,
            host=host,
            account=account,
        ),
        kind=kind,
    )


def _config() -> HubConfig:
    return HubConfig(
        schema_version=1,
        active_profile="lab",
        profiles={"lab": ProfileConfig(connection_ids=("github-lab", "jira-lab"))},
        connections=(
            ConnectionConfig(
                id="github-lab",
                provider=ProviderKind.github,
                deployment=DeploymentKind.CLOUD,
                base_url="https://api.github.com",
                account="qa-user",
                auth_kind=AuthKind.pat,
                credential=_credential(
                    "github-lab",
                    ProviderKind.github,
                    "api.github.com",
                    "QA_MCP_GITHUB_PAT",
                    AuthKind.pat,
                    "qa-user",
                ),
            ),
            ConnectionConfig(
                id="jira-lab",
                provider=ProviderKind.jira,
                deployment=DeploymentKind.CLOUD,
                base_url="https://example.atlassian.net",
                account="qa@example.com",
                auth_kind=AuthKind.api_token,
                credential=_credential(
                    "jira-lab",
                    ProviderKind.jira,
                    "example.atlassian.net",
                    "QA_MCP_JIRA_TOKEN",
                    AuthKind.api_token,
                    "qa@example.com",
                ),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_mcp_search_and_ticket_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_MCP_GITHUB_PAT", "qa_mcp_pat_value")
    monkeypatch.setenv("QA_MCP_JIRA_TOKEN", "qa_mcp_jira_value")
    monkeypatch.setattr(service, "load_config", lambda path=None: _config())
    issue = {
        "key": "QA-12",
        "fields": {
            "summary": "Sign in",
            "description": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "secret steps in the ticket"}
                        ],
                    }
                ],
            },
            "issuetype": {"name": "Story"},
            "status": {"name": "Open"},
            "updated": "2026-10-18T00:00:00+00:00",
        },
    }
    with respx.mock:
        respx.get("https://api.github.com/repos/acme/demo/commits/HEAD").mock(
            return_value=httpx.Response(200, json={"sha": SHA})
        )
        respx.get("https://api.github.com/repos/acme/demo").mock(
            return_value=httpx.Response(
                200,
                json={"full_name": "acme/demo", "default_branch": "main"},
            )
        )
        respx.get("https://api.github.com/repos/acme/demo/branches/main").mock(
            return_value=httpx.Response(200, json={"commit": {"sha": SHA}})
        )
        respx.get("https://api.github.com/repos/acme/demo/commits/main").mock(
            return_value=httpx.Response(200, json={"sha": SHA})
        )
        respx.get(url__regex=r"https://api.github.com/repos/acme/demo/compare/.*").mock(
            return_value=httpx.Response(
                200,
                json={
                    "html_url": "https://github.com/acme/demo/compare/main...main",
                    "files": [
                        {
                            "filename": "src/login.py",
                            "status": "modified",
                            "patch": "QA-12",
                        }
                    ],
                    "commits": [{"sha": SHA}],
                    "total_commits": 1,
                },
            )
        )
        search = respx.get("https://api.github.com/search/code").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "path": "src/login.py",
                            "html_url": "https://github.com/acme/demo/blob/main/src/login.py",
                            "text_matches": [{"fragment": "QA-12"}],
                        }
                    ]
                },
            )
        )
        respx.get("https://example.atlassian.net/rest/api/3/issue/QA-12").mock(
            return_value=httpx.Response(200, json=issue)
        )
        respx.get("https://example.atlassian.net/rest/api/3/field").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get("https://example.atlassian.net/rest/api/3/issue/QA-12/comment").mock(
            return_value=httpx.Response(200, json={"comments": [], "total": 0})
        )
        async with Client(mcp) as client:
            found = await client.call_tool(
                "find_related_implementation",
                {"issue_key": "QA-12", "repository": "acme/demo"},
            )
            changes = await client.call_tool(
                "get_repository_changes",
                {"repository": "acme/demo", "base": "main", "head": "main"},
            )
    assert found.is_error is False
    assert found.structured_content is not None
    assert found.structured_content["hits"][0]["revision"] == SHA
    assert found.structured_content["untrusted_content"] is True
    query = search.calls[0].request.url.params["q"]
    assert "QA-12" in query
    assert "secret steps" not in query
    assert changes.structured_content is not None
    assert changes.structured_content["remote_head_sha"] == SHA
    assert changes.structured_content["local_head_sha"] is None
