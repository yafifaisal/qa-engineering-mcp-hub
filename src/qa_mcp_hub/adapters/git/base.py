"""Shared read-only HTTP policy and normalized Git records.

Purpose: page, time out, and retry safe reads without trusting repository text.
Milestone: 03
Status: IMPLEMENTED
Ownership: Shared Git adapter mechanics, excluding vendor endpoint details.
Dependencies: Provider contracts, HTTP policy, and source-reference models.
Expected tests: pagination, error mapping, redirects, and source grounding.
"""

import re
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from qa_mcp_hub.core.errors import ProviderRequestError
from qa_mcp_hub.core.retry import RetryableError, RetryPolicy, decide_retry

_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_PATCH_LIMIT = 4000
_TEXT_LIMIT = 8000


class CodeHit(BaseModel):
    """A code reference. ``untrusted_content`` is data, not an instruction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    repository: str
    path: str
    revision: str = Field(pattern=r"^[0-9a-f]{7,64}$")
    url: str
    untrusted_content: str = ""
    content_truncated: bool = False


class ChangeFile(BaseModel):
    """One changed path pinned to the remote head commit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    status: str
    revision: str
    url: str
    patch: str | None = None
    patch_truncated: bool = False


class ChangeSet(BaseModel):
    """Remote changes. Local checkout state is recorded separately."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    repository: str
    remote_base_sha: str
    remote_head_sha: str
    source_url: str
    files: tuple[ChangeFile, ...] = ()
    truncated: bool = False
    local_head_sha: str | None = None
    local_dirty: bool | None = None
    revisions_differ: bool | None = None


class RepositorySnapshot(BaseModel):
    """Repository metadata pinned to the default-branch commit when known."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    repository: str
    name: str
    default_branch: str | None
    revision: str | None
    url: str


class PullRequestSummary(BaseModel):
    """A pull or merge request pinned to its head commit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    number: str
    title: str
    state: str
    revision: str | None
    url: str


def validate_repository_slug(
    value: str, *, maximum_segments: int = 2
) -> tuple[str, ...]:
    """Accept owner/name segments and reject traversal or credential-bearing URLs."""
    if "://" in value or "@" in value or "\\" in value or "\x00" in value:
        raise ProviderRequestError(
            "invalid_repository",
            "repository name is invalid",
            status_code=0,
        )
    segments = tuple(part for part in value.strip("/").split("/") if part)
    if not 2 <= len(segments) <= maximum_segments:
        raise ProviderRequestError(
            "invalid_repository",
            "repository name is invalid",
            status_code=0,
        )
    if any(
        _SEGMENT.fullmatch(part) is None or part in {".", ".."} for part in segments
    ):
        raise ProviderRequestError(
            "invalid_repository",
            "repository name is invalid",
            status_code=0,
        )
    return segments


def validate_git_ref(value: str) -> str:
    """Accept a branch or commit reference and reject traversal."""
    if (
        _REF.fullmatch(value) is None
        or ".." in value.split("/")
        or value.startswith(("-", "/"))
        or "//" in value
    ):
        raise ProviderRequestError(
            "invalid_reference",
            "branch or revision reference is invalid",
            status_code=0,
        )
    return value


def validate_repository_path(value: str) -> str:
    """Accept a relative file path inside a repository."""
    normalized = value.replace("\\", "/").lstrip("/")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if (
        not parts
        or ".." in parts
        or normalized.startswith("/")
        or "\x00" in value
        or ":" in normalized
    ):
        raise ProviderRequestError(
            "invalid_path",
            "repository path is invalid",
            status_code=0,
        )
    return "/".join(parts)


def bound_text(value: str, limit: int = _TEXT_LIMIT) -> tuple[str, bool]:
    """Shorten provider text and report when the returned value is incomplete."""
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def bound_patch(value: str | None) -> tuple[str | None, bool]:
    """Shorten a diff without treating it as instructions."""
    if value is None:
        return None, False
    text, truncated = bound_text(value, _PATCH_LIMIT)
    return text, truncated


class ReadOnlyClient:
    """HTTPS client that retries only safe read failures and ignores response bodies."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        allowed_host: str,
        policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._allowed_host = allowed_host.lower().rstrip(".")
        self._policy = policy or RetryPolicy()
        self._sleeper = sleeper or (lambda _delay: None)

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str | int] | None = None,
    ) -> httpx.Response:
        """Perform one read, following only same-host redirects."""
        return self._send("GET", url, headers=headers, params=params, body=None)

    def read_post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: dict[str, object],
    ) -> httpx.Response:
        """Perform one idempotent read that a provider exposes only as POST."""
        return self._send("POST", url, headers=headers, params=None, body=body)

    def _send(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str | int] | None,
        body: dict[str, object] | None,
    ) -> httpx.Response:
        current = url
        current_method = method
        for _redirect in range(3):
            self._check_url(current)
            response = self._with_retry(
                current_method, current, headers=headers, params=params, body=body
            )
            if response.status_code not in {301, 302, 303, 307, 308}:
                self._raise_for_status(response)
                return response
            location = response.headers.get("location")
            if not location:
                raise ProviderRequestError(
                    "invalid_redirect",
                    "provider redirect is missing a destination",
                    status_code=response.status_code,
                )
            self._check_url(location)
            current = location
            current_method = "GET" if response.status_code == 303 else method
            params = None
            body = None if current_method == "GET" else body
        raise ProviderRequestError(
            "invalid_redirect",
            "provider redirect limit was reached",
            status_code=310,
        )

    def _with_retry(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str | int] | None,
        body: dict[str, object] | None,
    ) -> httpx.Response:
        attempt = 1
        while True:
            try:
                response = self._client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=body,
                    follow_redirects=False,
                )
            except httpx.HTTPError as exc:
                raise ProviderRequestError(
                    "provider_unreachable",
                    "provider request failed",
                    status_code=0,
                ) from exc
            if response.status_code not in {429, 503}:
                return response
            decision = decide_retry(
                self._policy,
                attempt=attempt,
                operation_is_safe=True,
                error=RetryableError("provider asked for a retry"),
            )
            if not decision.should_retry:
                return response
            self._sleeper(_retry_delay(response, decision.delay_seconds))
            attempt += 1

    def _check_url(self, url: str) -> None:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        if (
            parts.scheme != "https"
            or host != self._allowed_host
            or parts.username is not None
            or parts.password is not None
        ):
            raise ProviderRequestError(
                "unapproved_host",
                "provider URL is outside the configured host",
                status_code=0,
            )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        code = response.status_code
        if code < 400:
            return
        if code == 401:
            message = "provider authentication failed"
            error_code = "authentication_failed"
        elif code == 403:
            message = "provider permission was denied"
            error_code = "permission_denied"
        elif code == 404:
            message = "provider resource was not found"
            error_code = "not_found"
        elif code in {429, 503}:
            message = "provider rate limit was reached"
            error_code = "rate_limited"
        else:
            message = "provider request failed"
            error_code = "provider_http"
        raise ProviderRequestError(error_code, message, status_code=code)


def json_object(response: httpx.Response) -> dict[str, object]:
    """Decode a JSON object. Failure does not include the response body."""
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderRequestError(
            "invalid_response",
            "provider response was not valid JSON",
            status_code=response.status_code,
        ) from exc
    if not isinstance(payload, dict):
        raise ProviderRequestError(
            "invalid_response",
            "provider response had an unexpected shape",
            status_code=response.status_code,
        )
    return payload


def json_list(response: httpx.Response) -> list[object]:
    """Decode a JSON list without echoing its contents on failure."""
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderRequestError(
            "invalid_response",
            "provider response was not valid JSON",
            status_code=response.status_code,
        ) from exc
    if not isinstance(payload, list):
        raise ProviderRequestError(
            "invalid_response",
            "provider response had an unexpected shape",
            status_code=response.status_code,
        )
    return payload


def header_value(response: httpx.Response, name: str) -> str | None:
    """Return one response header value."""
    raw = response.headers.get(name)
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.strip()


def next_page(response: httpx.Response) -> str | None:
    """Read a page token from GitHub Link or GitLab next-page headers."""
    gitlab_page = header_value(response, "x-next-page")
    if gitlab_page and gitlab_page.isdigit():
        return gitlab_page
    link = header_value(response, "link")
    if link is None:
        return None
    for part in link.split(","):
        if 'rel="next"' not in part:
            continue
        matched = re.search(r"[?&]page=(\d+)", part)
        if matched:
            return matched.group(1)
    return None


def bearer_headers(secret: SecretStr) -> dict[str, str]:
    """Build a bearer header. Callers must not log the returned mapping."""
    return {
        "Authorization": f"Bearer {secret.get_secret_value()}",
        "Accept": "application/json",
    }


def _retry_delay(response: httpx.Response, fallback: float) -> float:
    raw = header_value(response, "retry-after")
    if raw and raw.isdigit():
        return min(float(raw), 30.0)
    return fallback
