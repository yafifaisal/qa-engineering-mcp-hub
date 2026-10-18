"""Offline HTTP contracts for Confluence and Google Docs."""

from datetime import UTC, datetime

import httpx
import pytest
import respx
from pydantic import SecretStr

from qa_mcp_hub.adapters.documentation.confluence import (
    ConfluenceAdapter,
    storage_to_text,
)
from qa_mcp_hub.adapters.documentation.google_docs import (
    GoogleDocsAdapter,
    extract_document_text,
)
from qa_mcp_hub.adapters.git.base import ReadOnlyClient
from qa_mcp_hub.auth.models import AuthKind
from qa_mcp_hub.auth.oauth import refresh_google_access_token
from qa_mcp_hub.config.models import DeploymentKind
from qa_mcp_hub.core.errors import ProviderRequestError
from qa_mcp_hub.core.results import Pagination
from qa_mcp_hub.knowledge.models import DocumentCache

SECRET = SecretStr("qa_mcp_pat_value")
REFRESH = SecretStr("qa_mcp_refresh_value")
CLIENT_SECRET = SecretStr("qa_mcp_client_secret")
NOW = datetime(2026, 10, 18, tzinfo=UTC)
DOC_ID = "1abcdefghijklmnopqrstu"


def _confluence(
    deployment: DeploymentKind, base: str
) -> tuple[ConfluenceAdapter, httpx.Client]:
    client = httpx.Client()
    host = base.removeprefix("https://")
    adapter = ConfluenceAdapter(
        base_url=base,
        deployment=deployment,
        account="qa@example.com",
        auth_kind=AuthKind.api_token,
        secret=SECRET,
        client=ReadOnlyClient(client, allowed_host=host, sleeper=lambda _delay: None),
        clock=lambda: NOW,
        cache=DocumentCache(clock=lambda: NOW),
    )
    return adapter, client


def test_confluence_cloud_search_and_storage_text() -> None:
    adapter, client = _confluence(DeploymentKind.CLOUD, "https://example.atlassian.net")
    page = {
        "id": "123",
        "title": "Login",
        "space": {"key": "QA"},
        "version": {"number": 4},
        "_links": {"webui": "/spaces/QA/pages/123/Login"},
        "body": {
            "storage": {
                "value": (
                    "<p>user can sign in</p>"
                    '<ac:structured-macro ac:name="code"></ac:structured-macro>'
                )
            }
        },
    }
    with respx.mock:
        respx.get("https://example.atlassian.net/wiki/rest/api/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "size": 20,
                    "start": 0,
                    "results": [
                        {
                            "content": {"id": "123", "title": "Login"},
                            "url": "https://example.atlassian.net/wiki/spaces/QA/pages/123",
                        }
                    ],
                    "_links": {"next": "/wiki/rest/api/search?start=20"},
                },
            )
        )
        respx.get("https://example.atlassian.net/wiki/rest/api/content/123").mock(
            return_value=httpx.Response(200, json=page)
        )
        found = adapter.search("sign in", ("QA",), Pagination(limit=20))
        record = adapter.fetch_page("123")
        again = adapter.fetch_page("123")
    client.close()
    assert found.truncated is True
    assert found.hits[0].url.startswith("https://example.atlassian.net/")
    assert record.citation.revision == "4"
    assert record.citation.retrieved_at == NOW
    assert "user can sign in" in record.untrusted_text
    assert record.untrusted_content is True
    assert "unsupported content was omitted" in record.warnings
    assert again.citation.revision == "4"
    plain, warnings = storage_to_text("<p>only text</p>")
    assert plain == "only text"
    assert warnings == ()


def test_confluence_data_center_permission_and_removal() -> None:
    adapter, client = _confluence(
        DeploymentKind.SELF_MANAGED, "https://confluence.example.invalid"
    )
    with respx.mock:
        denied = respx.get(
            "https://confluence.example.invalid/rest/api/content/10"
        ).mock(return_value=httpx.Response(403))
        removed = respx.get(
            "https://confluence.example.invalid/rest/api/content/11"
        ).mock(return_value=httpx.Response(404))
        inaccessible = adapter.fetch_page("10")
        missing = adapter.fetch_page("11")
        assert denied.called
        assert removed.called
    client.close()
    assert inaccessible.status == "inaccessible"
    assert missing.status == "removed"
    assert adapter._content_root().endswith("/rest/api/content")
    with pytest.raises(ProviderRequestError) as caught:
        adapter.search("login", (), Pagination())
    assert caught.value.code == "space_required"


def test_confluence_rate_limit_retries() -> None:
    client = httpx.Client()
    slept: list[float] = []
    adapter = ConfluenceAdapter(
        base_url="https://example.atlassian.net",
        deployment=DeploymentKind.CLOUD,
        account="qa@example.com",
        auth_kind=AuthKind.api_token,
        secret=SECRET,
        client=ReadOnlyClient(
            client, allowed_host="example.atlassian.net", sleeper=slept.append
        ),
        clock=lambda: NOW,
    )
    with respx.mock:
        route = respx.get("https://example.atlassian.net/wiki/rest/api/search").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(200, json={"results": [], "size": 0, "start": 0}),
            ]
        )
        page = adapter.search("login", ("QA",), Pagination())
    client.close()
    assert page.hits == ()
    assert slept == [0.0]
    assert route.call_count == 2


def test_google_docs_structure_and_deleted_file() -> None:
    client = httpx.Client()
    adapter = GoogleDocsAdapter(
        auth_kind=AuthKind.api_token,
        account=None,
        secret=SECRET,
        client_secret=None,
        docs_client=ReadOnlyClient(client, allowed_host="docs.googleapis.com"),
        drive_client=ReadOnlyClient(client, allowed_host="www.googleapis.com"),
        token_client=client,
        clock=lambda: NOW,
        cache=DocumentCache(clock=lambda: NOW),
    )
    document = {
        "documentId": DOC_ID,
        "title": "Login",
        "revisionId": "rev1",
        "body": {
            "content": [
                {
                    "paragraph": {
                        "paragraphStyle": {"namedStyleType": "HEADING_1"},
                        "elements": [{"textRun": {"content": "Sign in\n"}}],
                    }
                },
                {
                    "paragraph": {
                        "elements": [{"textRun": {"content": "user can sign in\n"}}]
                    }
                },
                {
                    "table": {
                        "tableRows": [
                            {
                                "tableCells": [
                                    {
                                        "content": [
                                            {
                                                "paragraph": {
                                                    "elements": [
                                                        {"textRun": {"content": "a\n"}}
                                                    ]
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                },
                {"equation": {}},
            ]
        },
    }
    with respx.mock:
        respx.get(f"https://docs.googleapis.com/v1/documents/{DOC_ID}").mock(
            return_value=httpx.Response(200, json=document)
        )
        respx.get("https://docs.googleapis.com/v1/documents/missingdoc12").mock(
            return_value=httpx.Response(404)
        )
        record = adapter.fetch_document(DOC_ID)
        removed = adapter.fetch_document("missingdoc12")
    client.close()
    assert "[heading] Sign in" in record.untrusted_text
    assert "[paragraph] user can sign in" in record.untrusted_text
    assert "[table] a" in record.untrusted_text
    assert record.citation.revision == "rev1"
    assert "unsupported structure was omitted" in record.warnings
    assert removed.status == "removed"
    text, warnings = extract_document_text({})
    assert text == ""
    assert warnings == ("document body was missing",)


def test_google_oauth_refresh_hides_refresh_token_and_rejects_scope() -> None:
    client = httpx.Client()
    adapter = GoogleDocsAdapter(
        auth_kind=AuthKind.oauth,
        account="qa-client",
        secret=REFRESH,
        client_secret=CLIENT_SECRET,
        docs_client=ReadOnlyClient(client, allowed_host="docs.googleapis.com"),
        drive_client=ReadOnlyClient(client, allowed_host="www.googleapis.com"),
        token_client=client,
        clock=lambda: NOW,
    )
    with respx.mock:
        token = respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "qa_mcp_access_value",
                    "expires_in": 3600,
                    "scope": (
                        "https://www.googleapis.com/auth/documents.readonly "
                        "https://www.googleapis.com/auth/drive.metadata.readonly"
                    ),
                },
            )
        )
        respx.get("https://www.googleapis.com/drive/v3/files").mock(
            return_value=httpx.Response(
                200,
                json={
                    "nextPageToken": "next-page",
                    "files": [
                        {
                            "id": DOC_ID,
                            "name": "Login",
                            "webViewLink": (
                                "https://docs.google.com/document/d/" + DOC_ID
                            ),
                            "modifiedTime": "2026-10-18T00:00:00.000Z",
                        }
                    ],
                },
            )
        )
        found = adapter.search("Login", Pagination())
    client.close()
    assert token.called
    assert found.truncated is True
    assert found.hits[0].document_id == DOC_ID
    dumped = found.model_dump_json()
    assert "qa_mcp_refresh_value" not in dumped
    assert "qa_mcp_client_secret" not in dumped
    narrow = httpx.Client()
    with respx.mock:
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "qa_mcp_access_value",
                    "expires_in": 60,
                    "scope": "https://www.googleapis.com/auth/drive.metadata.readonly",
                },
            )
        )
        with pytest.raises(ProviderRequestError) as scope:
            refresh_google_access_token(
                refresh_token=REFRESH,
                client_id="qa-client",
                client_secret=CLIENT_SECRET,
                http_client=narrow,
                clock=lambda: NOW,
            )
    narrow.close()
    assert scope.value.code == "insufficient_scope"
    assert "qa_mcp_refresh_value" not in scope.value.message


def test_google_token_endpoint_expired_grant() -> None:
    client = httpx.Client()
    with respx.mock:
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(400, text="qa_mcp_refresh_value")
        )
        with pytest.raises(ProviderRequestError) as caught:
            refresh_google_access_token(
                refresh_token=REFRESH,
                client_id="qa-client",
                client_secret=CLIENT_SECRET,
                http_client=client,
                clock=lambda: NOW,
            )
    client.close()
    assert caught.value.code == "oauth_expired"
    assert "qa_mcp_refresh_value" not in caught.value.message
