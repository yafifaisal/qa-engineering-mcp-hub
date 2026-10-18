"""Read-only Confluence Cloud and Data Center adapter.

Purpose: search authorized spaces and read page text with version and URL.
Milestone: 04
Status: IMPLEMENTED
Ownership: Confluence-specific documentation API translation.
Dependencies: Read-only HTTP policy and document citation models.
Expected tests: Cloud versus Data Center, storage text, and permissions.
"""

import re
from collections.abc import Callable
from datetime import UTC, datetime
from html import unescape
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from qa_mcp_hub.adapters.git.base import (
    ReadOnlyClient,
    bearer_headers,
    bound_text,
    json_object,
)
from qa_mcp_hub.auth.models import AuthKind
from qa_mcp_hub.config.models import DeploymentKind
from qa_mcp_hub.core.context import ExecutionContext
from qa_mcp_hub.core.enums import EpistemicStatus, OperationStatus
from qa_mcp_hub.core.errors import ProviderRequestError
from qa_mcp_hub.core.results import Pagination, SourceReference, ToolResult
from qa_mcp_hub.knowledge.models import (
    DocumentCache,
    DocumentCitation,
    DocumentRecord,
    DocumentSearchResult,
)

_SPACE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_PAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")
_MACRO = re.compile(r"<ac:(?:structured-macro|image|task-list)\b", re.IGNORECASE)


class ConfluenceAdapter:
    """Confluence Cloud uses the /wiki prefix. Data Center does not."""

    def __init__(
        self,
        *,
        base_url: str,
        deployment: DeploymentKind,
        account: str | None,
        auth_kind: AuthKind,
        secret: SecretStr,
        client: ReadOnlyClient,
        cache: DocumentCache | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.deployment = deployment
        self.account = account
        self.auth_kind = auth_kind
        self._secret = secret
        self._http = client
        self._cloud = deployment is not DeploymentKind.SELF_MANAGED
        self._cache = cache or DocumentCache()
        self._clock = clock or (lambda: datetime.now(UTC))

    def read_document(self, context: ExecutionContext) -> ToolResult:
        """Read the page named by ``context.subject``."""
        record = self.fetch_page(_page_id(context.subject))
        return ToolResult(
            status=OperationStatus.success,
            epistemic=EpistemicStatus.verified,
            summary=record.citation.title or record.citation.document_id,
            source=SourceReference(
                provider="confluence",
                revision=record.citation.revision,
                path=record.citation.url,
            ),
        )

    def search(
        self, query: str, spaces: tuple[str, ...], page: Pagination
    ) -> DocumentSearchResult:
        """Search pages in the named spaces. The query is not sent as CQL."""
        if not spaces:
            raise ProviderRequestError(
                "space_required",
                "an authorized Confluence space is required",
                status_code=0,
            )
        cql = _cql(query, spaces)
        params: dict[str, str | int] = {"cql": cql, "limit": page.limit}
        if page.cursor:
            if not page.cursor.isdigit():
                raise ProviderRequestError(
                    "invalid_cursor", "page cursor is invalid", status_code=0
                )
            params["start"] = int(page.cursor)
        payload = json_object(
            self._http.get(self._search_url(), headers=self._headers(), params=params)
        )
        results = payload.get("results")
        hits: list[DocumentCitation] = []
        if isinstance(results, list):
            for item in results:
                citation = _search_hit(item, self.base_url, self._now())
                if citation is not None:
                    hits.append(citation)
        size = payload.get("size")
        start_raw = payload.get("start")
        start = start_raw if isinstance(start_raw, int) else 0
        truncated = isinstance(size, int) and size >= page.limit
        next_cursor = str(start + page.limit) if truncated else None
        return DocumentSearchResult(
            provider="confluence",
            hits=tuple(hits),
            truncated=truncated or _has_next(payload),
            next_cursor=next_cursor,
        )

    def fetch_page(self, page_id: str) -> DocumentRecord:
        """Read one page. Storage markup becomes plain text."""
        safe_id = _page_id(page_id)
        cached = self._cache.get(f"confluence:{safe_id}")
        if cached is not None and cached.status == "read":
            return cached
        try:
            payload = json_object(
                self._http.get(
                    f"{self._content_root()}/{quote(safe_id, safe='')}",
                    headers=self._headers(),
                    params={"expand": "body.storage,version,space"},
                )
            )
        except ProviderRequestError as exc:
            return _failure(safe_id, self.base_url, exc, self._now())
        record = _record_from_page(payload, self.base_url, self._now())
        if record.citation.revision:
            self._cache.put(f"confluence:{safe_id}", record)
        return record

    def _search_url(self) -> str:
        prefix = "/wiki" if self._cloud else ""
        return f"{self.base_url}{prefix}/rest/api/search"

    def _content_root(self) -> str:
        prefix = "/wiki" if self._cloud else ""
        return f"{self.base_url}{prefix}/rest/api/content"

    def _headers(self) -> dict[str, str]:
        if self.auth_kind is AuthKind.oauth:
            return bearer_headers(self._secret)
        if self._cloud and self.auth_kind is AuthKind.api_token:
            if not self.account:
                raise ProviderRequestError(
                    "account_required",
                    "confluence cloud api token requires an account email",
                    status_code=0,
                )
            import base64

            raw = f"{self.account}:{self._secret.get_secret_value()}".encode()
            encoded = base64.b64encode(raw).decode("ascii")
            return {"Authorization": f"Basic {encoded}", "Accept": "application/json"}
        return bearer_headers(self._secret)

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("confluence clock must return an aware datetime")
        return now


def open_confluence(
    *,
    base_url: str | None,
    deployment: DeploymentKind,
    account: str | None,
    auth_kind: AuthKind,
    secret: SecretStr,
    http_client: httpx.Client,
) -> ConfluenceAdapter:
    """Open a Confluence adapter. A site host is required."""
    if not base_url:
        raise ProviderRequestError(
            "base_url_required",
            "confluence connection requires base_url",
            status_code=0,
        )
    host = base_url.removeprefix("https://").split("/", 1)[0]
    return ConfluenceAdapter(
        base_url=base_url.rstrip("/"),
        deployment=deployment,
        account=account,
        auth_kind=auth_kind,
        secret=secret,
        client=ReadOnlyClient(http_client, allowed_host=host),
    )


def storage_to_text(value: str) -> tuple[str, tuple[str, ...]]:
    """Flatten storage markup. Macros are omitted rather than executed."""
    warnings: list[str] = []
    if _MACRO.search(value):
        warnings.append("unsupported content was omitted")
        value = _MACRO.sub(" ", value)
    text = re.sub(r"<[^>]+>", " ", value)
    collapsed = " ".join(unescape(text).split())
    return collapsed, tuple(warnings)


def _cql(query: str, spaces: tuple[str, ...]) -> str:
    phrase = " ".join(query.split())
    if not phrase or len(phrase) > 200 or any(char in phrase for char in "\"'\\"):
        raise ProviderRequestError(
            "invalid_query", "search query is invalid", status_code=0
        )
    keys = " OR ".join(f'space = "{_space_key(space)}"' for space in spaces)
    return f'type = page AND ({keys}) AND text ~ "{phrase}"'


def _space_key(value: str) -> str:
    if _SPACE.fullmatch(value) is None:
        raise ProviderRequestError(
            "invalid_space", "space key is invalid", status_code=0
        )
    return value


def _page_id(value: str | None) -> str:
    if value is None or _PAGE.fullmatch(value) is None:
        raise ProviderRequestError(
            "invalid_document", "document id is invalid", status_code=0
        )
    return value


def _search_hit(
    item: object, base_url: str, retrieved_at: datetime
) -> DocumentCitation | None:
    if not isinstance(item, dict):
        return None
    content = item.get("content")
    if not isinstance(content, dict):
        return None
    document_id = content.get("id")
    if not isinstance(document_id, str):
        return None
    raw_title = content.get("title")
    title = raw_title if isinstance(raw_title, str) else document_id
    space = None
    space_info = content.get("space")
    if isinstance(space_info, dict) and isinstance(space_info.get("key"), str):
        space = space_info["key"]
    url = item.get("url")
    link = f"{base_url}/wiki"
    if isinstance(url, str) and url.startswith("https://"):
        link = url
    return DocumentCitation(
        provider="confluence",
        document_id=document_id,
        title=title,
        url=link,
        revision=None,
        retrieved_at=retrieved_at,
        space=space,
    )


def _record_from_page(
    payload: dict[str, object], base_url: str, retrieved_at: datetime
) -> DocumentRecord:
    document_id = str(payload.get("id") or "")
    raw_title = payload.get("title")
    title = raw_title if isinstance(raw_title, str) else document_id
    version = payload.get("version")
    revision = None
    if isinstance(version, dict) and version.get("number") is not None:
        revision = str(version["number"])
    space = None
    space_info = payload.get("space")
    if isinstance(space_info, dict) and isinstance(space_info.get("key"), str):
        space = space_info["key"]
    links = payload.get("_links")
    webui = ""
    if isinstance(links, dict) and isinstance(links.get("webui"), str):
        webui = str(links["webui"])
    url = f"{base_url}/wiki{webui}" if webui else f"{base_url}/wiki"
    body = payload.get("body")
    storage = body.get("storage") if isinstance(body, dict) else None
    value = storage.get("value") if isinstance(storage, dict) else None
    warnings: tuple[str, ...] = ()
    text = ""
    truncated = False
    status = "read"
    if not isinstance(value, str):
        warnings = ("page body was missing",)
        status = "unsupported"
    else:
        plain, warnings = storage_to_text(value)
        text, truncated = bound_text(plain)
    return DocumentRecord(
        citation=DocumentCitation(
            provider="confluence",
            document_id=document_id,
            title=title,
            url=url,
            revision=revision,
            retrieved_at=retrieved_at,
            space=space,
        ),
        untrusted_text=text,
        text_truncated=truncated,
        status=status,  # type: ignore[arg-type]
        warnings=warnings,
    )


def _failure(
    page_id: str, base_url: str, exc: ProviderRequestError, retrieved_at: datetime
) -> DocumentRecord:
    if exc.code == "not_found":
        status = "removed"
        warning = "document was removed"
    elif exc.code == "permission_denied":
        status = "inaccessible"
        warning = "document was not authorized"
    elif exc.code == "oauth_expired":
        raise exc
    else:
        raise exc
    return DocumentRecord(
        citation=DocumentCitation(
            provider="confluence",
            document_id=page_id,
            title=page_id,
            url=base_url,
            retrieved_at=retrieved_at,
        ),
        status=status,  # type: ignore[arg-type]
        warnings=(warning,),
    )


def _has_next(payload: dict[str, object]) -> bool:
    links = payload.get("_links")
    return isinstance(links, dict) and isinstance(links.get("next"), str)
