"""Read-only GitHub REST adapter.

Purpose: read repository metadata, files, search hits, and pull-request diffs.
Milestone: 03
Status: IMPLEMENTED
Ownership: GitHub-specific API translation.
Dependencies: Git adapter base, source references, and execution context.
Expected tests: authentication, pagination, missing resources, and SHA integrity.
"""

from urllib.parse import quote

import httpx
from pydantic import SecretStr

from qa_mcp_hub.adapters.git.base import (
    ChangeFile,
    ChangeSet,
    CodeHit,
    PullRequestSummary,
    ReadOnlyClient,
    RepositorySnapshot,
    bearer_headers,
    bound_patch,
    bound_text,
    json_list,
    json_object,
    next_page,
    validate_git_ref,
    validate_repository_path,
    validate_repository_slug,
)
from qa_mcp_hub.config.models import DeploymentKind
from qa_mcp_hub.core.context import ExecutionContext
from qa_mcp_hub.core.enums import EpistemicStatus, OperationStatus
from qa_mcp_hub.core.errors import ProviderRequestError
from qa_mcp_hub.core.results import Pagination, SourceReference, ToolResult

_API_VERSION = "2022-11-28"


class GitHubAdapter:
    """GitHub Cloud or an explicitly configured GitHub Enterprise host."""

    def __init__(
        self,
        *,
        base_url: str,
        deployment: DeploymentKind,
        secret: SecretStr,
        client: ReadOnlyClient,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.deployment = deployment
        self._secret = secret
        self._http = client

    def read_repository(self, context: ExecutionContext) -> ToolResult:
        """Read the repository named by ``context.subject``."""
        if not context.subject:
            raise ProviderRequestError(
                "repository_required", "repository is required", status_code=0
            )
        record = self.fetch_repository(context.subject)
        return ToolResult(
            status=OperationStatus.success,
            epistemic=EpistemicStatus.verified,
            summary=record.name,
            source=SourceReference(
                provider="github",
                repository_id=record.repository,
                revision=record.revision,
            ),
        )

    def list_changes(self, context: ExecutionContext, page: Pagination) -> ToolResult:
        """List commits for ``context.subject`` on its default branch."""
        if not context.subject:
            raise ProviderRequestError(
                "repository_required", "repository is required", status_code=0
            )
        snapshot = self.fetch_repository(context.subject)
        ref = snapshot.default_branch or "HEAD"
        commits, truncated = self.list_commits(context.subject, ref, page)
        suffix = " (truncated)" if truncated else ""
        return ToolResult(
            status=OperationStatus.success,
            epistemic=EpistemicStatus.verified,
            summary=f"{len(commits)} commits{suffix}",
            source=SourceReference(
                provider="github",
                repository_id=context.subject,
                revision=commits[0] if commits else snapshot.revision,
            ),
        )

    def fetch_repository(self, repository: str) -> RepositorySnapshot:
        """Read repository metadata and the default-branch commit."""
        owner, name = validate_repository_slug(repository)
        payload = json_object(
            self._http.get(self._repo(owner, name), headers=self._headers())
        )
        branch = _text(payload.get("default_branch"))
        revision = None
        if branch:
            branch_name = quote(validate_git_ref(branch), safe="")
            branch_payload = json_object(
                self._http.get(
                    f"{self._repo(owner, name)}/branches/{branch_name}",
                    headers=self._headers(),
                )
            )
            commit = branch_payload.get("commit")
            if isinstance(commit, dict):
                revision = _sha(commit.get("sha"))
        return RepositorySnapshot(
            provider="github",
            repository=f"{owner}/{name}",
            name=_text(payload.get("full_name")) or f"{owner}/{name}",
            default_branch=branch,
            revision=revision,
            url=_text(payload.get("html_url")) or self._repo(owner, name),
        )

    def list_commits(
        self, repository: str, ref: str, page: Pagination
    ) -> tuple[tuple[str, ...], bool]:
        """Return commit SHAs for one page."""
        owner, name = validate_repository_slug(repository)
        response = self._http.get(
            f"{self._repo(owner, name)}/commits",
            headers=self._headers(),
            params={"sha": validate_git_ref(ref), **_page_params(page)},
        )
        commits: list[str] = []
        for item in json_list(response):
            if isinstance(item, dict) and _sha(item.get("sha")):
                commits.append(str(item["sha"]))
        return tuple(commits), next_page(response) is not None

    def read_file(self, repository: str, path: str, ref: str) -> CodeHit:
        """Read one file at a resolved commit."""
        owner, name = validate_repository_slug(repository)
        safe_path = validate_repository_path(path)
        revision = self.resolve_commit(repository, ref)
        response = self._http.get(
            f"{self._repo(owner, name)}/contents/{quote(safe_path, safe='/')}",
            headers=self._headers(),
            params={"ref": revision},
        )
        payload = json_object(response)
        if payload.get("type") != "file":
            raise ProviderRequestError(
                "not_a_file", "repository path is not a file", status_code=0
            )
        text, truncated = _decode_content(
            payload.get("content"), payload.get("encoding")
        )
        return CodeHit(
            provider="github",
            repository=f"{owner}/{name}",
            path=safe_path,
            revision=revision,
            url=_text(payload.get("html_url")) or self._repo(owner, name),
            untrusted_content=text,
            content_truncated=truncated,
        )

    def search_code(
        self, repository: str, query: str, ref: str | None, page: Pagination
    ) -> tuple[tuple[CodeHit, ...], bool]:
        """Search code. Snippets are untrusted data and each hit has a commit SHA."""
        owner, name = validate_repository_slug(repository)
        revision = self.resolve_commit(
            repository,
            ref or self.fetch_repository(repository).default_branch or "HEAD",
        )
        safe_query = _search_query(query)
        response = self._http.get(
            f"{self.base_url}/search/code",
            headers={
                **self._headers(),
                "Accept": "application/vnd.github.text-match+json",
            },
            params={
                "q": f"repo:{owner}/{name} {safe_query}",
                **_page_params(page),
            },
        )
        payload = json_object(response)
        items = payload.get("items")
        hits: list[CodeHit] = []
        if isinstance(items, list):
            for item in items:
                hit = _search_hit(item, f"{owner}/{name}", revision)
                if hit is not None:
                    hits.append(hit)
        incomplete = payload.get("incomplete_results") is True
        return tuple(hits), incomplete or next_page(response) is not None

    def compare(self, repository: str, base: str, head: str) -> ChangeSet:
        """Compare two refs after resolving both to commit SHAs."""
        owner, name = validate_repository_slug(repository)
        base_sha = self.resolve_commit(repository, base)
        head_sha = self.resolve_commit(repository, head)
        spec = f"{quote(base_sha, safe='')}...{quote(head_sha, safe='')}"
        response = self._http.get(
            f"{self._repo(owner, name)}/compare/{spec}",
            headers=self._headers(),
        )
        payload = json_object(response)
        files = _change_files(payload.get("files"), head_sha)
        total = payload.get("total_commits")
        listed = payload.get("commits")
        truncated = (
            isinstance(total, int) and isinstance(listed, list) and total > len(listed)
        ) or next_page(response) is not None
        return ChangeSet(
            provider="github",
            repository=f"{owner}/{name}",
            remote_base_sha=base_sha,
            remote_head_sha=head_sha,
            source_url=_text(payload.get("html_url")) or self._repo(owner, name),
            files=files,
            truncated=truncated,
        )

    def pull_request_changes(self, repository: str, number: int) -> ChangeSet:
        """Read changed files for one pull request, pinned to its head SHA."""
        owner, name = validate_repository_slug(repository)
        if number < 1:
            raise ProviderRequestError(
                "invalid_reference", "pull request number is invalid", status_code=0
            )
        payload = json_object(
            self._http.get(
                f"{self._repo(owner, name)}/pulls/{number}",
                headers=self._headers(),
            )
        )
        head = payload.get("head")
        revision = _sha(head.get("sha")) if isinstance(head, dict) else None
        if revision is None:
            raise ProviderRequestError(
                "missing_revision",
                "pull request did not include a commit SHA",
                status_code=0,
            )
        files_response = self._http.get(
            f"{self._repo(owner, name)}/pulls/{number}/files",
            headers=self._headers(),
            params={"per_page": 100},
        )
        return ChangeSet(
            provider="github",
            repository=f"{owner}/{name}",
            remote_base_sha=_sha(_nested(payload, "base", "sha")) or revision,
            remote_head_sha=revision,
            source_url=_text(payload.get("html_url")) or self._repo(owner, name),
            files=_change_files(json_list(files_response), revision),
            truncated=next_page(files_response) is not None,
        )

    def list_pull_requests(
        self, repository: str, page: Pagination
    ) -> tuple[tuple[PullRequestSummary, ...], bool]:
        """List pull requests for one page."""
        owner, name = validate_repository_slug(repository)
        response = self._http.get(
            f"{self._repo(owner, name)}/pulls",
            headers=self._headers(),
            params={"state": "all", **_page_params(page)},
        )
        records: list[PullRequestSummary] = []
        for item in json_list(response):
            if not isinstance(item, dict):
                continue
            head = item.get("head")
            records.append(
                PullRequestSummary(
                    provider="github",
                    number=str(item.get("number", "")),
                    title=_text(item.get("title")) or "",
                    state=_text(item.get("state")) or "unknown",
                    revision=_sha(head.get("sha")) if isinstance(head, dict) else None,
                    url=_text(item.get("html_url")) or self._repo(owner, name),
                )
            )
        return tuple(records), next_page(response) is not None

    def resolve_commit(self, repository: str, ref: str) -> str:
        """Return the immutable SHA for a branch or commit reference."""
        owner, name = validate_repository_slug(repository)
        revision_name = quote(validate_git_ref(ref), safe="")
        payload = json_object(
            self._http.get(
                f"{self._repo(owner, name)}/commits/{revision_name}",
                headers=self._headers(),
            )
        )
        revision = _sha(payload.get("sha"))
        if revision is None:
            raise ProviderRequestError(
                "missing_revision",
                "provider response did not include a commit SHA",
                status_code=0,
            )
        return revision

    def _repo(self, owner: str, name: str) -> str:
        return f"{self.base_url}/repos/{quote(owner, safe='')}/{quote(name, safe='')}"

    def _headers(self) -> dict[str, str]:
        return {
            **bearer_headers(self._secret),
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
        }


def _page_params(page: Pagination) -> dict[str, str | int]:
    params: dict[str, str | int] = {"per_page": page.limit}
    if page.cursor:
        if not page.cursor.isdigit():
            raise ProviderRequestError(
                "invalid_cursor", "page cursor is invalid", status_code=0
            )
        params["page"] = page.cursor
    return params


def _search_query(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > 200 or any(char in cleaned for char in "\x00"):
        raise ProviderRequestError(
            "invalid_query", "search query is invalid", status_code=0
        )
    return cleaned


def _search_hit(item: object, repository: str, revision: str) -> CodeHit | None:
    if not isinstance(item, dict):
        return None
    path = _text(item.get("path"))
    if path is None:
        return None
    snippet = ""
    matches = item.get("text_matches")
    if isinstance(matches, list) and matches and isinstance(matches[0], dict):
        snippet = _text(matches[0].get("fragment")) or ""
    text, truncated = bound_text(snippet)
    return CodeHit(
        provider="github",
        repository=repository,
        path=path,
        revision=revision,
        url=_text(item.get("html_url")) or "",
        untrusted_content=text,
        content_truncated=truncated,
    )


def _change_files(items: object, revision: str) -> tuple[ChangeFile, ...]:
    if not isinstance(items, list):
        return ()
    files: list[ChangeFile] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        path = _text(item.get("filename"))
        if path is None:
            continue
        patch, truncated = bound_patch(_text(item.get("patch")))
        files.append(
            ChangeFile(
                path=path,
                status=_text(item.get("status")) or "modified",
                revision=revision,
                url=_text(item.get("blob_url")) or "",
                patch=patch,
                patch_truncated=truncated,
            )
        )
    return tuple(files)


def _decode_content(content: object, encoding: object) -> tuple[str, bool]:
    if not isinstance(content, str) or encoding != "base64":
        return "", True
    import base64

    try:
        raw = base64.b64decode(content, validate=False)
        text = raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return "", True
    return bound_text(text)


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _sha(value: object) -> str | None:
    if (
        isinstance(value, str)
        and len(value) >= 7
        and all(c in "0123456789abcdef" for c in value)
    ):
        return value
    return None


def _nested(payload: dict[str, object], key: str, child: str) -> object:
    value = payload.get(key)
    if isinstance(value, dict):
        return value.get(child)
    return None


def open_github(
    *,
    base_url: str | None,
    deployment: DeploymentKind,
    secret: SecretStr,
    http_client: httpx.Client,
) -> GitHubAdapter:
    """Open a read-only GitHub adapter for one connection."""
    root = (base_url or "https://api.github.com").rstrip("/")
    host = root.removeprefix("https://").split("/", 1)[0]
    return GitHubAdapter(
        base_url=root,
        deployment=deployment,
        secret=secret,
        client=ReadOnlyClient(http_client, allowed_host=host),
    )
