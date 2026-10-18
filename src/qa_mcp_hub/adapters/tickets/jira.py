"""Read-only Jira Cloud and Data Center adapter.

Purpose: search and read issues, comments, and links without treating ticket
text as instructions.
Milestone: 03
Status: IMPLEMENTED
Ownership: Jira-specific ticket API translation.
Dependencies: Read-only HTTP policy and ticket result models.
Expected tests: cloud versus data center, ADF, permissions, and pagination.
"""

import base64
import re
from datetime import datetime

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr

from qa_mcp_hub.adapters.git.base import ReadOnlyClient, bound_text, json_object
from qa_mcp_hub.auth.models import AuthKind
from qa_mcp_hub.config.models import DeploymentKind
from qa_mcp_hub.core.context import ExecutionContext
from qa_mcp_hub.core.enums import EpistemicStatus, OperationStatus
from qa_mcp_hub.core.errors import ProviderRequestError
from qa_mcp_hub.core.results import Pagination, SourceReference, ToolResult

_ISSUE_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
_HEADING = re.compile(r"h[1-6]\.\s*acceptance criteria", re.IGNORECASE)


class JiraComment(BaseModel):
    """One comment. The body is untrusted ticket text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    author: str | None
    created_at: datetime | None
    untrusted_body: str
    body_truncated: bool = False


class JiraIssueRecord(BaseModel):
    """A normalized issue. Description and comments are untrusted data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    url: str
    summary: str
    issue_type: str | None
    status: str | None
    labels: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    untrusted_description: str = ""
    description_truncated: bool = False
    acceptance_criteria: str = ""
    updated_at: datetime | None = None
    comments: tuple[JiraComment, ...] = ()
    comments_status: str = "not_requested"
    linked_issue_keys: tuple[str, ...] = ()
    unknown_custom_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    truncated: bool = False


class JiraSearchPage(BaseModel):
    """One page of issue keys plus an explicit truncation flag."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issues: tuple[JiraIssueRecord, ...]
    next_cursor: str | None = None
    truncated: bool = False


class JiraAdapter:
    """Jira Cloud uses REST v3. A self-managed connection uses REST v2."""

    def __init__(
        self,
        *,
        base_url: str,
        deployment: DeploymentKind,
        account: str | None,
        auth_kind: AuthKind,
        secret: SecretStr,
        client: ReadOnlyClient,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.deployment = deployment
        self.account = account
        self.auth_kind = auth_kind
        self._secret = secret
        self._http = client
        self._api = "3" if deployment is not DeploymentKind.SELF_MANAGED else "2"

    def read_issue(self, context: ExecutionContext) -> ToolResult:
        """Read the issue named by ``context.subject``."""
        record = self.fetch_issue(_issue_key(context.subject))
        return ToolResult(
            status=OperationStatus.success,
            epistemic=EpistemicStatus.verified,
            summary=record.key,
            source=SourceReference(
                provider="jira",
                revision=record.updated_at.isoformat() if record.updated_at else None,
            ),
        )

    def fetch_issue(
        self, issue_key: str, *, include_comments: bool = True
    ) -> JiraIssueRecord:
        """Read one issue, its comments, and its links."""
        key = _issue_key(issue_key)
        payload = json_object(
            self._http.get(
                f"{self._root()}/issue/{key}",
                headers=self._headers(),
                params={"fields": "*all"},
            )
        )
        catalog = self._field_catalog()
        return _record_from_issue(
            payload,
            self.base_url,
            catalog,
            comments=self._comments(key) if include_comments else None,
        )

    def search(self, jql: str, page: Pagination) -> JiraSearchPage:
        """Run one page of JQL. The query is sent as data, not as instructions."""
        cleaned = " ".join(jql.split())
        if not cleaned or len(cleaned) > 500:
            raise ProviderRequestError(
                "invalid_query", "issue query is invalid", status_code=0
            )
        if self._api == "3":
            body: dict[str, object] = {
                "jql": cleaned,
                "maxResults": page.limit,
                "fields": ["summary", "status", "issuetype", "updated"],
            }
            if page.cursor:
                body["nextPageToken"] = page.cursor
            payload = json_object(
                self._http.read_post(
                    f"{self._root()}/search/jql",
                    headers=self._headers(),
                    body=body,
                )
            )
            token = payload.get("nextPageToken")
            cursor = token if isinstance(token, str) and token else None
        else:
            params: dict[str, object] = {
                "jql": cleaned,
                "maxResults": page.limit,
                "fields": ["summary", "status", "issuetype", "updated"],
            }
            if page.cursor:
                if not page.cursor.isdigit():
                    raise ProviderRequestError(
                        "invalid_cursor", "page cursor is invalid", status_code=0
                    )
                params["startAt"] = int(page.cursor)
            payload = json_object(
                self._http.read_post(
                    f"{self._root()}/search",
                    headers=self._headers(),
                    body=params,
                )
            )
            start = payload.get("startAt")
            total = payload.get("total")
            max_results = payload.get("maxResults")
            cursor = None
            if (
                isinstance(start, int)
                and isinstance(total, int)
                and isinstance(max_results, int)
                and start + max_results < total
            ):
                cursor = str(start + max_results)
        issues = payload.get("issues")
        records: list[JiraIssueRecord] = []
        if isinstance(issues, list):
            for item in issues:
                if isinstance(item, dict):
                    records.append(
                        _record_from_issue(item, self.base_url, {}, comments=None)
                    )
        return JiraSearchPage(
            issues=tuple(records),
            next_cursor=cursor,
            truncated=cursor is not None,
        )

    def _comments(self, key: str) -> tuple[tuple[JiraComment, ...], str]:
        try:
            payload = json_object(
                self._http.get(
                    f"{self._root()}/issue/{key}/comment",
                    headers=self._headers(),
                    params={"maxResults": 50},
                )
            )
        except ProviderRequestError as exc:
            if exc.code == "permission_denied":
                return (), "permission_denied"
            raise
        raw = payload.get("comments")
        comments: list[JiraComment] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                body, truncated = bound_text(adf_to_text(item.get("body")))
                author = item.get("author")
                comments.append(
                    JiraComment(
                        author=_text(author.get("displayName"))
                        if isinstance(author, dict)
                        else None,
                        created_at=_time(item.get("created")),
                        untrusted_body=body,
                        body_truncated=truncated,
                    )
                )
        total = payload.get("total")
        status = (
            "truncated" if isinstance(total, int) and total > len(comments) else "read"
        )
        return tuple(comments), status

    def _field_catalog(self) -> dict[str, str]:
        try:
            payload = self._http.get(f"{self._root()}/field", headers=self._headers())
        except ProviderRequestError as exc:
            if exc.code in {"permission_denied", "not_found"}:
                return {}
            raise
        try:
            values = payload.json()
        except ValueError:
            return {}
        catalog: dict[str, str] = {}
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    name = item.get("name")
                    catalog[item["id"]] = name if isinstance(name, str) else item["id"]
        return catalog

    def _root(self) -> str:
        return f"{self.base_url}/rest/api/{self._api}"

    def _headers(self) -> dict[str, str]:
        if self.auth_kind is AuthKind.oauth:
            raise ProviderRequestError(
                "oauth_not_implemented",
                "OAuth provider flow is NOT_IMPLEMENTED.",
                status_code=0,
            )
        secret = self._secret.get_secret_value()
        if self._api == "3" and self.auth_kind is AuthKind.api_token:
            if not self.account:
                raise ProviderRequestError(
                    "account_required",
                    "jira cloud api token requires an account email",
                    status_code=0,
                )
            encoded = base64.b64encode(f"{self.account}:{secret}".encode()).decode(
                "ascii"
            )
            return {"Authorization": f"Basic {encoded}", "Accept": "application/json"}
        return {"Authorization": f"Bearer {secret}", "Accept": "application/json"}


def open_jira(
    *,
    base_url: str | None,
    deployment: DeploymentKind,
    account: str | None,
    auth_kind: AuthKind,
    secret: SecretStr,
    http_client: httpx.Client,
) -> JiraAdapter:
    """Open a Jira adapter. Cloud without a URL cannot guess a tenant host."""
    if not base_url:
        raise ProviderRequestError(
            "base_url_required",
            "jira connection requires base_url",
            status_code=0,
        )
    host = base_url.removeprefix("https://").split("/", 1)[0]
    return JiraAdapter(
        base_url=base_url.rstrip("/"),
        deployment=deployment,
        account=account,
        auth_kind=auth_kind,
        secret=secret,
        client=ReadOnlyClient(http_client, allowed_host=host),
    )


def adf_to_text(value: object) -> str:
    """Flatten Atlassian document JSON or wiki markup into plain text."""
    if isinstance(value, str):
        return _wiki_to_text(value)
    if isinstance(value, dict):
        return _walk_adf(value).strip()
    return ""


def _record_from_issue(
    payload: dict[str, object],
    base_url: str,
    catalog: dict[str, str],
    *,
    comments: tuple[tuple[JiraComment, ...], str] | None,
) -> JiraIssueRecord:
    key = _text(payload.get("key")) or "UNKNOWN"
    fields = payload.get("fields")
    field_map = fields if isinstance(fields, dict) else {}
    description, description_truncated = bound_text(
        adf_to_text(field_map.get("description"))
    )
    acceptance = _acceptance(field_map, description, catalog)
    unknown = tuple(
        name
        for name in field_map
        if name.startswith("customfield_") and name not in catalog
    )
    warnings: list[str] = []
    if unknown:
        warnings.append("unknown custom fields were omitted")
    labels = _strings(field_map.get("labels"))
    components = _component_names(field_map.get("components"))
    links = _link_keys(field_map.get("issuelinks"))
    comment_records: tuple[JiraComment, ...] = ()
    comment_status = "not_requested"
    if comments is not None:
        comment_records, comment_status = comments
        if comment_status == "permission_denied":
            warnings.append("comments were not authorized")
        if comment_status == "truncated":
            warnings.append("comments were truncated")
    return JiraIssueRecord(
        key=key,
        url=f"{base_url.rstrip('/')}/browse/{key}",
        summary=_text(field_map.get("summary")) or "",
        issue_type=_text(_child(field_map.get("issuetype"), "name")),
        status=_text(_child(field_map.get("status"), "name")),
        labels=labels,
        components=components,
        untrusted_description=description,
        description_truncated=description_truncated,
        acceptance_criteria=acceptance,
        updated_at=_time(field_map.get("updated")),
        comments=comment_records,
        comments_status=comment_status,
        linked_issue_keys=links,
        unknown_custom_fields=unknown,
        warnings=tuple(warnings),
        truncated=description_truncated or comment_status == "truncated",
    )


def _acceptance(
    fields: dict[str, object], plain_description: str, catalog: dict[str, str]
) -> str:
    for field_id, name in catalog.items():
        if "acceptance" in name.lower() and field_id in fields:
            return adf_to_text(fields[field_id]).strip()
    lines = plain_description.splitlines()
    collecting = False
    collected: list[str] = []
    for line in lines:
        if _HEADING.search(line) or line.strip().lower() == "acceptance criteria":
            collecting = True
            continue
        if collecting and line.startswith("#"):
            break
        if collecting:
            collected.append(line)
    return "\n".join(collected).strip()


def _walk_adf(node: dict[str, object]) -> str:
    node_type = node.get("type")
    if node_type == "text" and isinstance(node.get("text"), str):
        return str(node["text"])
    content = node.get("content")
    if not isinstance(content, list):
        return ""
    parts = [_walk_adf(child) for child in content if isinstance(child, dict)]
    joiner = "\n" if node_type in {"doc", "paragraph", "heading", "listItem"} else ""
    return joiner.join(part for part in parts if part)


def _wiki_to_text(value: str) -> str:
    text = re.sub(r"\{code(?::[^}]*)?\}", "", value, flags=re.IGNORECASE)
    text = re.sub(r"\{noformat\}", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\{panel(?::[^}]*)?\}", "", text, flags=re.IGNORECASE)
    text = text.replace("{panel}", "")
    return text


def _issue_key(value: str | None) -> str:
    if value is None or _ISSUE_KEY.fullmatch(value) is None:
        raise ProviderRequestError(
            "invalid_issue", "issue key is invalid", status_code=0
        )
    return value


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _component_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names: list[str] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return tuple(names)


def _link_keys(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    keys: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        for side in ("outwardIssue", "inwardIssue"):
            linked = item.get(side)
            if isinstance(linked, dict) and isinstance(linked.get("key"), str):
                keys.append(linked["key"])
    return tuple(keys)


def _child(value: object, key: str) -> object:
    if isinstance(value, dict):
        return value.get(key)
    return None


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
