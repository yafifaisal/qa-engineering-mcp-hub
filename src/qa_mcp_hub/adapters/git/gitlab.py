"""Read-only GitLab REST adapter.

Purpose: read projects, files, merge requests, and diffs from GitLab.com or a
configured self-managed GitLab host.
Milestone: 03
Status: IMPLEMENTED
Ownership: GitLab-specific API translation.
Dependencies: Git adapter base and source-reference models.
Expected tests: project encoding, pagination, permissions, and SHA integrity.
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


class GitLabAdapter:
    """GitLab.com or an explicitly configured GitLab host."""

    def __init__(
        self,
        *,
        api_root: str,
        deployment: DeploymentKind,
        secret: SecretStr,
        client: ReadOnlyClient,
    ) -> None:
        self.api_root = api_root.rstrip("/")
        self.deployment = deployment
        self._secret = secret
        self._http = client

    def read_repository(self, context: ExecutionContext) -> ToolResult:
        """Read the project named by ``context.subject``."""
        record = self.fetch_repository(_required(context.subject))
        return ToolResult(
            status=OperationStatus.success,
            epistemic=EpistemicStatus.verified,
            summary=record.name,
            source=SourceReference(
                provider="gitlab",
                repository_id=record.repository,
                revision=record.revision,
            ),
        )

    def list_changes(self, context: ExecutionContext, page: Pagination) -> ToolResult:
        """List one page of commits on the project's default branch."""
        repository = _required(context.subject)
        snapshot = self.fetch_repository(repository)
        ref = snapshot.default_branch or "HEAD"
        commits, truncated = self.list_commits(repository, ref, page)
        suffix = " (truncated)" if truncated else ""
        return ToolResult(
            status=OperationStatus.success,
            epistemic=EpistemicStatus.verified,
            summary=f"{len(commits)} commits{suffix}",
            source=SourceReference(
                provider="gitlab",
                repository_id=repository,
                revision=commits[0] if commits else snapshot.revision,
            ),
        )

    def fetch_repository(self, repository: str) -> RepositorySnapshot:
        """Read project metadata and the default-branch commit."""
        project = self._project(repository)
        payload = json_object(self._http.get(project, headers=self._headers()))
        branch = _text(payload.get("default_branch"))
        revision = None
        if branch:
            revision = self.resolve_commit(repository, branch)
        path = _text(payload.get("path_with_namespace")) or repository
        return RepositorySnapshot(
            provider="gitlab",
            repository=path,
            name=_text(payload.get("name")) or path,
            default_branch=branch,
            revision=revision,
            url=_text(payload.get("web_url")) or project,
        )

    def list_commits(
        self, repository: str, ref: str, page: Pagination
    ) -> tuple[tuple[str, ...], bool]:
        """Return one page of commit SHAs."""
        response = self._http.get(
            f"{self._project(repository)}/repository/commits",
            headers=self._headers(),
            params={"ref_name": validate_git_ref(ref), **_page_params(page)},
        )
        commits = [
            str(item["id"])
            for item in json_list(response)
            if isinstance(item, dict) and _sha(item.get("id"))
        ]
        return tuple(commits), next_page(response) is not None

    def read_file(self, repository: str, path: str, ref: str) -> CodeHit:
        """Read one file at a resolved commit."""
        safe_path = validate_repository_path(path)
        revision = self.resolve_commit(repository, ref)
        payload = json_object(
            self._http.get(
                f"{self._project(repository)}/repository/files/"
                f"{quote(safe_path, safe='')}",
                headers=self._headers(),
                params={"ref": revision},
            )
        )
        text, truncated = _decode(payload.get("content"), payload.get("encoding"))
        return CodeHit(
            provider="gitlab",
            repository=repository,
            path=_text(payload.get("file_path")) or safe_path,
            revision=revision,
            url=_text(payload.get("web_url")) or self._project(repository),
            untrusted_content=text,
            content_truncated=truncated,
        )

    def search_code(
        self, repository: str, query: str, ref: str | None, page: Pagination
    ) -> tuple[tuple[CodeHit, ...], bool]:
        """Search blobs and pin every hit to the resolved branch commit."""
        revision = self.resolve_commit(
            repository,
            ref or self.fetch_repository(repository).default_branch or "HEAD",
        )
        response = self._http.get(
            f"{self._project(repository)}/search",
            headers=self._headers(),
            params={
                "scope": "blobs",
                "search": _query(query),
                "ref": revision,
                **_page_params(page),
            },
        )
        hits: list[CodeHit] = []
        for item in json_list(response):
            if not isinstance(item, dict) or not _text(item.get("path")):
                continue
            snippet, truncated = bound_text(_text(item.get("data")) or "")
            hits.append(
                CodeHit(
                    provider="gitlab",
                    repository=repository,
                    path=str(item["path"]),
                    revision=revision,
                    url=self._project(repository),
                    untrusted_content=snippet,
                    content_truncated=truncated,
                )
            )
        return tuple(hits), next_page(response) is not None

    def compare(self, repository: str, base: str, head: str) -> ChangeSet:
        """Compare two refs after resolving both to commit SHAs."""
        base_sha = self.resolve_commit(repository, base)
        head_sha = self.resolve_commit(repository, head)
        payload = json_object(
            self._http.get(
                f"{self._project(repository)}/repository/compare",
                headers=self._headers(),
                params={"from": base_sha, "to": head_sha},
            )
        )
        files = _diff_files(payload.get("diffs"), head_sha)
        return ChangeSet(
            provider="gitlab",
            repository=repository,
            remote_base_sha=base_sha,
            remote_head_sha=head_sha,
            source_url=_text(payload.get("web_url")) or self._project(repository),
            files=files,
            truncated=payload.get("compare_timeout") is True,
        )

    def pull_request_changes(self, repository: str, number: int) -> ChangeSet:
        """Read one merge request and its diffs, pinned to the head SHA."""
        if number < 1:
            raise ProviderRequestError(
                "invalid_reference", "merge request number is invalid", status_code=0
            )
        payload = json_object(
            self._http.get(
                f"{self._project(repository)}/merge_requests/{number}",
                headers=self._headers(),
            )
        )
        revision = _sha(payload.get("sha"))
        if revision is None:
            raise ProviderRequestError(
                "missing_revision",
                "merge request did not include a commit SHA",
                status_code=0,
            )
        diffs = json_list(
            self._http.get(
                f"{self._project(repository)}/merge_requests/{number}/diffs",
                headers=self._headers(),
            )
        )
        base = _sha(_nested(payload, "diff_refs", "base_sha")) or revision
        return ChangeSet(
            provider="gitlab",
            repository=repository,
            remote_base_sha=base,
            remote_head_sha=revision,
            source_url=_text(payload.get("web_url")) or self._project(repository),
            files=_diff_files(diffs, revision),
        )

    def list_pull_requests(
        self, repository: str, page: Pagination
    ) -> tuple[tuple[PullRequestSummary, ...], bool]:
        """List merge requests for one page."""
        response = self._http.get(
            f"{self._project(repository)}/merge_requests",
            headers=self._headers(),
            params={"scope": "all", **_page_params(page)},
        )
        records = []
        for item in json_list(response):
            if not isinstance(item, dict):
                continue
            records.append(
                PullRequestSummary(
                    provider="gitlab",
                    number=str(item.get("iid", "")),
                    title=_text(item.get("title")) or "",
                    state=_text(item.get("state")) or "unknown",
                    revision=_sha(item.get("sha")),
                    url=_text(item.get("web_url")) or self._project(repository),
                )
            )
        return tuple(records), next_page(response) is not None

    def resolve_commit(self, repository: str, ref: str) -> str:
        """Return the immutable SHA for a branch or commit reference."""
        payload = json_object(
            self._http.get(
                f"{self._project(repository)}/repository/commits/"
                f"{quote(validate_git_ref(ref), safe='')}",
                headers=self._headers(),
            )
        )
        revision = _sha(payload.get("id"))
        if revision is None:
            raise ProviderRequestError(
                "missing_revision",
                "provider response did not include a commit SHA",
                status_code=0,
            )
        return revision

    def _project(self, repository: str) -> str:
        segments = validate_repository_slug(repository, maximum_segments=10)
        encoded = quote("/".join(segments), safe="")
        return f"{self.api_root}/projects/{encoded}"

    def _headers(self) -> dict[str, str]:
        return bearer_headers(self._secret)


def open_gitlab(
    *,
    base_url: str | None,
    deployment: DeploymentKind,
    secret: SecretStr,
    http_client: httpx.Client,
) -> GitLabAdapter:
    """Open a read-only GitLab adapter. Cloud without a URL uses gitlab.com."""
    configured = (base_url or "https://gitlab.com").rstrip("/")
    api_root = configured if configured.endswith("/api/v4") else f"{configured}/api/v4"
    host = configured.removeprefix("https://").split("/", 1)[0]
    return GitLabAdapter(
        api_root=api_root,
        deployment=deployment,
        secret=secret,
        client=ReadOnlyClient(http_client, allowed_host=host),
    )


def _required(subject: str | None) -> str:
    if not subject:
        raise ProviderRequestError(
            "repository_required", "repository is required", status_code=0
        )
    return subject


def _page_params(page: Pagination) -> dict[str, str | int]:
    params: dict[str, str | int] = {"per_page": page.limit}
    if page.cursor:
        if not page.cursor.isdigit():
            raise ProviderRequestError(
                "invalid_cursor", "page cursor is invalid", status_code=0
            )
        params["page"] = page.cursor
    return params


def _query(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > 200:
        raise ProviderRequestError(
            "invalid_query", "search query is invalid", status_code=0
        )
    return cleaned


def _diff_files(items: object, revision: str) -> tuple[ChangeFile, ...]:
    if not isinstance(items, list):
        return ()
    files: list[ChangeFile] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        path = _text(item.get("new_path")) or _text(item.get("old_path"))
        if path is None:
            continue
        patch, truncated = bound_patch(_text(item.get("diff")))
        status = "deleted" if item.get("deleted_file") else "modified"
        if item.get("new_file"):
            status = "added"
        files.append(
            ChangeFile(
                path=path,
                status=status,
                revision=revision,
                url=path,
                patch=patch,
                patch_truncated=truncated,
            )
        )
    return tuple(files)


def _decode(content: object, encoding: object) -> tuple[str, bool]:
    if not isinstance(content, str) or encoding != "base64":
        return "", True
    import base64

    try:
        text = base64.b64decode(content).decode("utf-8")
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
        and 7 <= len(value) <= 64
        and all(char in "0123456789abcdef" for char in value)
    ):
        return value
    return None


def _nested(payload: dict[str, object], key: str, child: str) -> object:
    value = payload.get(key)
    if isinstance(value, dict):
        return value.get(child)
    return None
