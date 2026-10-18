"""Read-only Google Docs adapter.

Purpose: discover Docs through Drive metadata and read document structure.
Milestone: 04
Status: IMPLEMENTED
Ownership: Google Docs API translation; general Drive browsing is out of scope.
Dependencies: OAuth refresh, read-only HTTP policy, and document citations.
Expected tests: structure extraction, expired tokens, scopes, and deletion.
"""

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import SecretStr

from qa_mcp_hub.adapters.git.base import ReadOnlyClient, bound_text, json_object
from qa_mcp_hub.auth.models import AuthKind
from qa_mcp_hub.auth.oauth import (
    GoogleAccessToken,
    google_drive_scope_present,
    refresh_google_access_token,
)
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

_DOC_ID = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
_DOCS_HOST = "docs.googleapis.com"
_DRIVE_HOST = "www.googleapis.com"
DOCS_READONLY_SCOPE = "https://www.googleapis.com/auth/documents.readonly"
DRIVE_METADATA_SCOPE = "https://www.googleapis.com/auth/drive.metadata.readonly"


class GoogleDocsAdapter:
    """Reads Docs API documents. Drive is used only to find Docs by name."""

    def __init__(
        self,
        *,
        auth_kind: AuthKind,
        account: str | None,
        secret: SecretStr,
        client_secret: SecretStr | None,
        docs_client: ReadOnlyClient,
        drive_client: ReadOnlyClient,
        token_client: httpx.Client,
        cache: DocumentCache | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.auth_kind = auth_kind
        self.account = account
        self._secret = secret
        self._client_secret = client_secret
        self._docs = docs_client
        self._drive = drive_client
        self._tokens = token_client
        self._cache = cache or DocumentCache()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._access: GoogleAccessToken | None = None

    def read_document(self, context: ExecutionContext) -> ToolResult:
        """Read the document named by ``context.subject``."""
        record = self.fetch_document(_document_id(context.subject))
        return ToolResult(
            status=OperationStatus.success,
            epistemic=EpistemicStatus.verified,
            summary=record.citation.title or record.citation.document_id,
            source=SourceReference(
                provider="google_docs",
                revision=record.citation.revision,
                path=record.citation.url,
            ),
        )

    def search(self, query: str, page: Pagination) -> DocumentSearchResult:
        """Find Google Docs by name. The query cannot address other Drive files."""
        if not google_drive_scope_present(self._token()):
            raise ProviderRequestError(
                "insufficient_scope",
                "google oauth token is missing the Drive metadata scope",
                status_code=0,
            )
        params: dict[str, str | int] = {
            "q": _drive_query(query),
            "pageSize": page.limit,
            "corpora": "user",
            "fields": "nextPageToken,files(id,name,webViewLink,modifiedTime,trashed)",
        }
        if page.cursor:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", page.cursor):
                raise ProviderRequestError(
                    "invalid_cursor", "page cursor is invalid", status_code=0
                )
            params["pageToken"] = page.cursor
        try:
            payload = json_object(
                self._drive.get(
                    "https://www.googleapis.com/drive/v3/files",
                    headers=self._headers(),
                    params=params,
                )
            )
        except ProviderRequestError as exc:
            _reraise_auth(exc)
            raise
        files = payload.get("files")
        hits: list[DocumentCitation] = []
        if isinstance(files, list):
            for item in files:
                citation = _file_hit(item, self._now())
                if citation is not None:
                    hits.append(citation)
        token = payload.get("nextPageToken")
        cursor = token if isinstance(token, str) and token else None
        return DocumentSearchResult(
            provider="google_docs",
            hits=tuple(hits),
            truncated=cursor is not None,
            next_cursor=cursor,
        )

    def fetch_document(self, document_id: str) -> DocumentRecord:
        """Read one document and flatten headings, paragraphs, and tables."""
        safe_id = _document_id(document_id)
        cached = self._cache.get(f"google_docs:{safe_id}")
        if cached is not None and cached.status == "read":
            return cached
        try:
            payload = json_object(
                self._docs.get(
                    f"https://docs.googleapis.com/v1/documents/{safe_id}",
                    headers=self._headers(),
                )
            )
        except ProviderRequestError as exc:
            return _failure(safe_id, exc, self._now())
        record = _record_from_document(payload, self._now())
        if record.citation.revision:
            self._cache.put(f"google_docs:{safe_id}", record)
        return record

    def _headers(self) -> dict[str, str]:
        token = self._token().access_token.get_secret_value()
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def _token(self) -> GoogleAccessToken:
        now = self._now()
        if self._access is not None and self._access.expires_at > now + timedelta(
            seconds=30
        ):
            return self._access
        if self.auth_kind is not AuthKind.oauth:
            self._access = GoogleAccessToken(
                access_token=self._secret,
                expires_at=now + timedelta(hours=1),
                scopes=(DOCS_READONLY_SCOPE, DRIVE_METADATA_SCOPE),
            )
            return self._access
        if not self.account or self._client_secret is None:
            raise ProviderRequestError(
                "credential_missing",
                "google oauth client credentials are missing",
                status_code=0,
            )
        self._access = refresh_google_access_token(
            refresh_token=self._secret,
            client_id=self.account,
            client_secret=self._client_secret,
            http_client=self._tokens,
            clock=self._now,
        )
        return self._access

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("google docs clock must return an aware datetime")
        return now


def open_google_docs(
    *,
    auth_kind: AuthKind,
    account: str | None,
    secret: SecretStr,
    client_secret: SecretStr | None,
    http_client: httpx.Client,
) -> GoogleDocsAdapter:
    """Open a Docs adapter bound to the official Google hosts."""
    return GoogleDocsAdapter(
        auth_kind=auth_kind,
        account=account,
        secret=secret,
        client_secret=client_secret,
        docs_client=ReadOnlyClient(http_client, allowed_host=_DOCS_HOST),
        drive_client=ReadOnlyClient(http_client, allowed_host=_DRIVE_HOST),
        token_client=http_client,
    )


def extract_document_text(body: object) -> tuple[str, tuple[str, ...]]:
    """Walk Docs structural elements. Unsupported nodes are named, not executed."""
    warnings: list[str] = []
    lines: list[str] = []
    content = body.get("content") if isinstance(body, dict) else None
    if not isinstance(content, list):
        return "", ("document body was missing",)
    for element in content:
        if not isinstance(element, dict):
            continue
        if "paragraph" in element:
            lines.extend(_paragraph_lines(element["paragraph"], warnings))
        elif "table" in element:
            lines.extend(_table_lines(element["table"], warnings))
        elif any(key in element for key in ("equation", "inlineObjectElement")):
            warnings.append("unsupported structure was omitted")
    text = "\n".join(line for line in lines if line)
    return text, tuple(dict.fromkeys(warnings))


def _paragraph_lines(paragraph: object, warnings: list[str]) -> list[str]:
    if not isinstance(paragraph, dict):
        return []
    style = paragraph.get("paragraphStyle")
    named = ""
    if isinstance(style, dict) and isinstance(style.get("namedStyleType"), str):
        named = style["namedStyleType"]
    pieces: list[str] = []
    elements = paragraph.get("elements")
    if isinstance(elements, list):
        for element in elements:
            if not isinstance(element, dict):
                continue
            run = element.get("textRun")
            if isinstance(run, dict) and isinstance(run.get("content"), str):
                pieces.append(run["content"].strip("\n"))
            elif "equation" in element or "inlineObjectElement" in element:
                warnings.append("unsupported structure was omitted")
    text = "".join(pieces).strip()
    if not text:
        return []
    if named.startswith("HEADING_"):
        return [f"[heading] {text}"]
    return [f"[paragraph] {text}"]


def _table_lines(table: object, warnings: list[str]) -> list[str]:
    if not isinstance(table, dict):
        return []
    rows = table.get("tableRows")
    if not isinstance(rows, list):
        warnings.append("unsupported structure was omitted")
        return []
    rendered: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cells = row.get("tableCells")
        values: list[str] = []
        if isinstance(cells, list):
            for cell in cells:
                content = cell.get("content") if isinstance(cell, dict) else None
                cell_text, cell_warnings = extract_document_text({"content": content})
                warnings.extend(cell_warnings)
                values.append(cell_text.replace("[paragraph] ", "").strip())
        if values:
            rendered.append("[table] " + " | ".join(values))
    return rendered


def _drive_query(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > 200 or any(char in cleaned for char in "'\\"):
        raise ProviderRequestError(
            "invalid_query", "search query is invalid", status_code=0
        )
    mime = "application/vnd.google-apps.document"
    return f"mimeType = '{mime}' and trashed = false and name contains '{cleaned}'"


def _document_id(value: str | None) -> str:
    if value is None or _DOC_ID.fullmatch(value) is None:
        raise ProviderRequestError(
            "invalid_document", "document id is invalid", status_code=0
        )
    return value


def _file_hit(item: object, retrieved_at: datetime) -> DocumentCitation | None:
    if not isinstance(item, dict) or item.get("trashed") is True:
        return None
    document_id = item.get("id")
    if not isinstance(document_id, str):
        return None
    raw_title = item.get("name")
    title = raw_title if isinstance(raw_title, str) else document_id
    link = item.get("webViewLink")
    fallback = f"https://docs.google.com/document/d/{document_id}"
    url = link if isinstance(link, str) else fallback
    modified_raw = item.get("modifiedTime")
    modified = modified_raw if isinstance(modified_raw, str) else None
    return DocumentCitation(
        provider="google_docs",
        document_id=document_id,
        title=title,
        url=url,
        revision=modified,
        retrieved_at=retrieved_at,
    )


def _record_from_document(
    payload: dict[str, object], retrieved_at: datetime
) -> DocumentRecord:
    document_id = str(payload.get("documentId") or "")
    raw_title = payload.get("title")
    title = raw_title if isinstance(raw_title, str) else document_id
    raw_revision = payload.get("revisionId")
    revision = raw_revision if isinstance(raw_revision, str) else None
    text, warnings = extract_document_text(payload.get("body"))
    bounded, truncated = bound_text(text)
    status = "unsupported" if "document body was missing" in warnings else "read"
    return DocumentRecord(
        citation=DocumentCitation(
            provider="google_docs",
            document_id=document_id,
            title=title,
            url=f"https://docs.google.com/document/d/{document_id}",
            revision=revision,
            retrieved_at=retrieved_at,
        ),
        untrusted_text=bounded,
        text_truncated=truncated,
        status=status,  # type: ignore[arg-type]
        warnings=warnings,
    )


def _failure(
    document_id: str, exc: ProviderRequestError, retrieved_at: datetime
) -> DocumentRecord:
    if exc.code == "not_found":
        status = "removed"
        warning = "document was removed"
    elif exc.code in {"permission_denied", "insufficient_scope"}:
        status = "inaccessible"
        warning = "document was not authorized"
    else:
        raise exc
    return DocumentRecord(
        citation=DocumentCitation(
            provider="google_docs",
            document_id=document_id,
            title=document_id,
            url=f"https://docs.google.com/document/d/{document_id}",
            retrieved_at=retrieved_at,
        ),
        status=status,  # type: ignore[arg-type]
        warnings=(warning,),
    )


def _reraise_auth(exc: ProviderRequestError) -> None:
    if exc.code in {"authentication_failed", "oauth_expired", "insufficient_scope"}:
        raise exc
