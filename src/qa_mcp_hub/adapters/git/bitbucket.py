"""Read-only Bitbucket Cloud and Data Center adapter.

Purpose: read repositories, files, pull requests, and diffs for the edition
named by the connection deployment.
Milestone: 03
Status: IMPLEMENTED
Ownership: Bitbucket-specific Git API translation and edition routing.
Dependencies: Git adapter base and the configured deployment variant.
Expected tests: cloud versus data center routing, auth, and missing search.
"""

import base64
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
    bound_text,
    json_object,
    validate_git_ref,
    validate_repository_path,
    validate_repository_slug,
)
from qa_mcp_hub.auth.models import AuthKind
from qa_mcp_hub.config.models import DeploymentKind
from qa_mcp_hub.core.context import ExecutionContext
from qa_mcp_hub.core.enums import EpistemicStatus, OperationStatus
from qa_mcp_hub.core.errors import ProviderRequestError, UnsupportedCapabilityError
from qa_mcp_hub.core.results import Pagination, SourceReference, ToolResult


class BitbucketAdapter:
    """Bitbucket Cloud or a configured Data Center host."""

    def __init__(
        self,
        *,
        api_root: str,
        deployment: DeploymentKind,
        account: str | None,
        auth_kind: AuthKind,
        secret: SecretStr,
        client: ReadOnlyClient,
    ) -> None:
        self.api_root = api_root.rstrip("/")
        self.deployment = deployment
        self.account = account
        self.auth_kind = auth_kind
        self._secret = secret
        self._http = client
        self._cloud = deployment is not DeploymentKind.SELF_MANAGED

    def read_repository(self, context: ExecutionContext) -> ToolResult:
        """Read the repository named by ``context.subject``."""
        record = self.fetch_repository(_required(context.subject))
        return ToolResult(
            status=OperationStatus.success,
            epistemic=EpistemicStatus.verified,
            summary=record.name,
            source=SourceReference(
                provider="bitbucket",
                repository_id=record.repository,
                revision=record.revision,
            ),
        )

    def list_changes(self, context: ExecutionContext, page: Pagination) -> ToolResult:
        """List one page of commits on the default branch."""
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
                provider="bitbucket",
                repository_id=repository,
                revision=commits[0] if commits else snapshot.revision,
            ),
        )

    def fetch_repository(self, repository: str) -> RepositorySnapshot:
        """Read repository metadata and the default-branch commit."""
        payload = json_object(
            self._http.get(self._repo(repository), headers=self._headers())
        )
        if self._cloud:
            branch = _text(_nested(payload, "mainbranch", "name"))
            url = _text(_link(payload, "html")) or self._repo(repository)
            name = _text(payload.get("full_name")) or repository
        else:
            branch = _text(_nested(payload, "defaultBranch", "displayId")) or _text(
                _nested(payload, "defaultBranch", "id")
            )
            url = _text(_link(payload, "self")) or self._repo(repository)
            project = (
                _text(_nested(payload, "project", "key")) or repository.split("/")[0]
            )
            slug = _text(payload.get("slug")) or repository.split("/")[-1]
            name = f"{project}/{slug}"
            if branch and branch.startswith("refs/heads/"):
                branch = branch.removeprefix("refs/heads/")
        revision = self.resolve_commit(repository, branch) if branch else None
        return RepositorySnapshot(
            provider="bitbucket",
            repository=repository,
            name=name,
            default_branch=branch,
            revision=revision,
            url=url,
        )

    def list_commits(
        self, repository: str, ref: str, page: Pagination
    ) -> tuple[tuple[str, ...], bool]:
        """Return one page of commit hashes."""
        safe_ref = validate_git_ref(ref)
        if self._cloud:
            response = self._http.get(
                f"{self._repo(repository)}/commits/{quote(safe_ref, safe='')}",
                headers=self._headers(),
                params=_cloud_page(page),
            )
            payload = json_object(response)
            values = payload.get("values")
            commits = (
                [
                    str(item["hash"])
                    for item in values
                    if isinstance(values, list)
                    and isinstance(item, dict)
                    and _sha(item.get("hash"))
                ]
                if isinstance(values, list)
                else []
            )
            return tuple(commits), isinstance(payload.get("next"), str)
        response = self._http.get(
            f"{self._repo(repository)}/commits",
            headers=self._headers(),
            params={"until": safe_ref, **_dc_page(page)},
        )
        payload = json_object(response)
        values = payload.get("values")
        commits = (
            [
                str(item["id"])
                for item in values
                if isinstance(values, list)
                and isinstance(item, dict)
                and _sha(item.get("id"))
            ]
            if isinstance(values, list)
            else []
        )
        return tuple(commits), payload.get("isLastPage") is False

    def read_file(self, repository: str, path: str, ref: str) -> CodeHit:
        """Read one file at a resolved commit."""
        safe_path = validate_repository_path(path)
        revision = self.resolve_commit(repository, ref)
        if self._cloud:
            file_url = (
                f"{self._repo(repository)}/src/{quote(revision, safe='')}"
                f"/{quote(safe_path, safe='/')}"
            )
            response = self._http.get(
                file_url,
                headers={**self._headers(), "Accept": "text/plain"},
            )
            text, truncated = bound_text(response.text)
            return CodeHit(
                provider="bitbucket",
                repository=repository,
                path=safe_path,
                revision=revision,
                url=str(response.url),
                untrusted_content=text,
                content_truncated=truncated,
            )
        payload = json_object(
            self._http.get(
                f"{self._repo(repository)}/browse/{quote(safe_path, safe='/')}",
                headers=self._headers(),
                params={"at": revision},
            )
        )
        lines = _nested(payload, "lines", "lines") if False else payload.get("lines")
        text = ""
        if isinstance(lines, list):
            text = "\n".join(
                str(item.get("text", "")) for item in lines if isinstance(item, dict)
            )
        bounded, truncated = bound_text(text)
        return CodeHit(
            provider="bitbucket",
            repository=repository,
            path=safe_path,
            revision=revision,
            url=self._repo(repository),
            untrusted_content=bounded,
            content_truncated=truncated or payload.get("isLastPage") is False,
        )

    def search_code(
        self, repository: str, query: str, ref: str | None, page: Pagination
    ) -> tuple[tuple[CodeHit, ...], bool]:
        """Search code. Hits without a commit SHA are omitted."""
        revision = self.resolve_commit(
            repository,
            ref or self.fetch_repository(repository).default_branch or "HEAD",
        )
        if self._cloud:
            workspace = validate_repository_slug(repository)[0]
            response = self._http.get(
                f"{self.api_root}/workspaces/{quote(workspace, safe='')}/search/code",
                headers=self._headers(),
                params={
                    "search_query": f"repo:{repository} {_query(query)}",
                    **_cloud_page(page),
                },
            )
            payload = json_object(response)
            return _cloud_hits(payload.get("values"), repository, revision), isinstance(
                payload.get("next"), str
            )
        project, slug = validate_repository_slug(repository)
        try:
            response = self._http.get(
                f"{self.api_root}/rest/search/latest/search",
                headers=self._headers(),
                params={
                    "query": _query(query),
                    "project": project,
                    "repo": slug,
                    **_dc_page(page),
                },
            )
        except ProviderRequestError as exc:
            if exc.code == "not_found":
                raise UnsupportedCapabilityError(
                    "bitbucket", "search_code", implemented=False
                ) from exc
            raise
        payload = json_object(response)
        hits = _dc_hits(
            payload.get("code", payload.get("values")), repository, revision
        )
        return hits, payload.get("isLastPage") is False

    def compare(self, repository: str, base: str, head: str) -> ChangeSet:
        """Compare two refs after resolving both to commit hashes."""
        base_sha = self.resolve_commit(repository, base)
        head_sha = self.resolve_commit(repository, head)
        if self._cloud:
            spec = f"{quote(base_sha, safe='')}..{quote(head_sha, safe='')}"
            response = self._http.get(
                f"{self._repo(repository)}/diffstat/{spec}",
                headers=self._headers(),
            )
            payload = json_object(response)
            files = _cloud_diffstat(payload.get("values"), head_sha)
            return ChangeSet(
                provider="bitbucket",
                repository=repository,
                remote_base_sha=base_sha,
                remote_head_sha=head_sha,
                source_url=self._repo(repository),
                files=files,
                truncated=isinstance(payload.get("next"), str),
            )
        changes = self._http.get(
            f"{self._repo(repository)}/changes",
            headers=self._headers(),
            params={"since": base_sha, "until": head_sha},
        )
        payload = json_object(changes)
        return ChangeSet(
            provider="bitbucket",
            repository=repository,
            remote_base_sha=base_sha,
            remote_head_sha=head_sha,
            source_url=self._repo(repository),
            files=_dc_changes(payload.get("values"), head_sha),
            truncated=payload.get("isLastPage") is False,
        )

    def pull_request_changes(self, repository: str, number: int) -> ChangeSet:
        """Read one pull request and its changed files."""
        if number < 1:
            raise ProviderRequestError(
                "invalid_reference", "pull request number is invalid", status_code=0
            )
        if self._cloud:
            payload = json_object(
                self._http.get(
                    f"{self._repo(repository)}/pullrequests/{number}",
                    headers=self._headers(),
                )
            )
            revision = _sha(_nested(payload, "source", "commit", "hash"))
            base = _sha(_nested(payload, "destination", "commit", "hash")) or revision
            if revision is None or base is None:
                raise ProviderRequestError(
                    "missing_revision",
                    "pull request did not include a commit hash",
                    status_code=0,
                )
            diffstat = json_object(
                self._http.get(
                    f"{self._repo(repository)}/pullrequests/{number}/diffstat",
                    headers=self._headers(),
                )
            )
            return ChangeSet(
                provider="bitbucket",
                repository=repository,
                remote_base_sha=base,
                remote_head_sha=revision,
                source_url=_text(_link(payload, "html")) or self._repo(repository),
                files=_cloud_diffstat(diffstat.get("values"), revision),
                truncated=isinstance(diffstat.get("next"), str),
            )
        payload = json_object(
            self._http.get(
                f"{self._repo(repository)}/pull-requests/{number}",
                headers=self._headers(),
            )
        )
        revision = _sha(_nested(payload, "fromRef", "latestCommit"))
        base = _sha(_nested(payload, "toRef", "latestCommit")) or revision
        if revision is None or base is None:
            raise ProviderRequestError(
                "missing_revision",
                "pull request did not include a commit hash",
                status_code=0,
            )
        changes = json_object(
            self._http.get(
                f"{self._repo(repository)}/pull-requests/{number}/changes",
                headers=self._headers(),
            )
        )
        return ChangeSet(
            provider="bitbucket",
            repository=repository,
            remote_base_sha=base,
            remote_head_sha=revision,
            source_url=_text(_link(payload, "self")) or self._repo(repository),
            files=_dc_changes(changes.get("values"), revision),
            truncated=changes.get("isLastPage") is False,
        )

    def list_pull_requests(
        self, repository: str, page: Pagination
    ) -> tuple[tuple[PullRequestSummary, ...], bool]:
        """List pull requests for one page."""
        if self._cloud:
            response = self._http.get(
                f"{self._repo(repository)}/pullrequests",
                headers=self._headers(),
                params={"state": "OPEN", **_cloud_page(page)},
            )
            payload = json_object(response)
            values = payload.get("values")
            records = []
            if isinstance(values, list):
                for item in values:
                    if not isinstance(item, dict):
                        continue
                    records.append(
                        PullRequestSummary(
                            provider="bitbucket",
                            number=str(item.get("id", "")),
                            title=_text(item.get("title")) or "",
                            state=_text(item.get("state")) or "unknown",
                            revision=_sha(_nested(item, "source", "commit", "hash")),
                            url=_text(_link(item, "html")) or self._repo(repository),
                        )
                    )
            return tuple(records), isinstance(payload.get("next"), str)
        response = self._http.get(
            f"{self._repo(repository)}/pull-requests",
            headers=self._headers(),
            params=_dc_page(page),
        )
        payload = json_object(response)
        values = payload.get("values")
        records = []
        if isinstance(values, list):
            for item in values:
                if not isinstance(item, dict):
                    continue
                records.append(
                    PullRequestSummary(
                        provider="bitbucket",
                        number=str(item.get("id", "")),
                        title=_text(item.get("title")) or "",
                        state=_text(item.get("state")) or "unknown",
                        revision=_sha(_nested(item, "fromRef", "latestCommit")),
                        url=_text(_link(item, "self")) or self._repo(repository),
                    )
                )
        return tuple(records), payload.get("isLastPage") is False

    def resolve_commit(self, repository: str, ref: str) -> str:
        """Return the immutable hash for a branch or commit reference."""
        safe_ref = validate_git_ref(ref)
        if self._cloud:
            payload = json_object(
                self._http.get(
                    f"{self._repo(repository)}/commit/{quote(safe_ref, safe='')}",
                    headers=self._headers(),
                )
            )
            revision = _sha(payload.get("hash"))
        else:
            payload = json_object(
                self._http.get(
                    f"{self._repo(repository)}/commits/{quote(safe_ref, safe='')}",
                    headers=self._headers(),
                )
            )
            revision = _sha(payload.get("id"))
        if revision is None:
            raise ProviderRequestError(
                "missing_revision",
                "provider response did not include a commit hash",
                status_code=0,
            )
        return revision

    def _repo(self, repository: str) -> str:
        first, second = validate_repository_slug(repository)
        if self._cloud:
            return (
                f"{self.api_root}/repositories/"
                f"{quote(first, safe='')}/{quote(second, safe='')}"
            )
        return (
            f"{self.api_root}/rest/api/1.0/projects/"
            f"{quote(first, safe='')}/repos/{quote(second, safe='')}"
        )

    def _headers(self) -> dict[str, str]:
        if self.auth_kind is AuthKind.oauth:
            raise ProviderRequestError(
                "oauth_not_implemented",
                "OAuth provider flow is NOT_IMPLEMENTED.",
                status_code=0,
            )
        if self.auth_kind is AuthKind.api_token and self._cloud:
            if not self.account:
                raise ProviderRequestError(
                    "account_required",
                    "bitbucket cloud api token requires an account",
                    status_code=0,
                )
            raw = f"{self.account}:{self._secret.get_secret_value()}".encode()
            encoded = base64.b64encode(raw).decode("ascii")
            return {"Authorization": f"Basic {encoded}", "Accept": "application/json"}
        return bearer_headers(self._secret)


def open_bitbucket(
    *,
    base_url: str | None,
    deployment: DeploymentKind,
    account: str | None,
    auth_kind: AuthKind,
    secret: SecretStr,
    http_client: httpx.Client,
) -> BitbucketAdapter:
    """Open the Cloud or Data Center adapter named by deployment."""
    if deployment is DeploymentKind.SELF_MANAGED:
        if not base_url:
            raise ProviderRequestError(
                "base_url_required",
                "self-managed connection requires base_url",
                status_code=0,
            )
        root = base_url.rstrip("/")
    else:
        root = "https://api.bitbucket.org/2.0"
    host = root.removeprefix("https://").split("/", 1)[0]
    return BitbucketAdapter(
        api_root=root,
        deployment=deployment,
        account=account,
        auth_kind=auth_kind,
        secret=secret,
        client=ReadOnlyClient(http_client, allowed_host=host),
    )


def _required(subject: str | None) -> str:
    if not subject:
        raise ProviderRequestError(
            "repository_required", "repository is required", status_code=0
        )
    return subject


def _cloud_page(page: Pagination) -> dict[str, str | int]:
    params: dict[str, str | int] = {"pagelen": page.limit}
    if page.cursor:
        if not page.cursor.isdigit():
            raise ProviderRequestError(
                "invalid_cursor", "page cursor is invalid", status_code=0
            )
        params["page"] = page.cursor
    return params


def _dc_page(page: Pagination) -> dict[str, str | int]:
    params: dict[str, str | int] = {"limit": page.limit}
    if page.cursor:
        if not page.cursor.isdigit():
            raise ProviderRequestError(
                "invalid_cursor", "page cursor is invalid", status_code=0
            )
        params["start"] = page.cursor
    return params


def _query(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > 200:
        raise ProviderRequestError(
            "invalid_query", "search query is invalid", status_code=0
        )
    return cleaned


def _cloud_hits(values: object, repository: str, revision: str) -> tuple[CodeHit, ...]:
    if not isinstance(values, list):
        return ()
    hits: list[CodeHit] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        file_info = item.get("file")
        path = _text(file_info.get("path")) if isinstance(file_info, dict) else None
        if path is None:
            continue
        snippet, truncated = bound_text(_text(item.get("content_matches")) or "")
        hits.append(
            CodeHit(
                provider="bitbucket",
                repository=repository,
                path=path,
                revision=revision,
                url=_text(_link(item, "self")) or "",
                untrusted_content=snippet,
                content_truncated=truncated,
            )
        )
    return tuple(hits)


def _dc_hits(values: object, repository: str, revision: str) -> tuple[CodeHit, ...]:
    if not isinstance(values, list):
        return ()
    hits: list[CodeHit] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        path = _text(item.get("file")) or _text(item.get("path"))
        item_revision = _sha(item.get("commitId")) or revision
        if path is None or item_revision is None:
            continue
        snippet, truncated = bound_text(_text(item.get("hitContext")) or "")
        hits.append(
            CodeHit(
                provider="bitbucket",
                repository=repository,
                path=path,
                revision=item_revision,
                url=path,
                untrusted_content=snippet,
                content_truncated=truncated,
            )
        )
    return tuple(hits)


def _cloud_diffstat(values: object, revision: str) -> tuple[ChangeFile, ...]:
    if not isinstance(values, list):
        return ()
    files: list[ChangeFile] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        new = item.get("new")
        old = item.get("old")
        path = None
        if isinstance(new, dict):
            path = _text(new.get("path"))
        if path is None and isinstance(old, dict):
            path = _text(old.get("path"))
        if path is None:
            continue
        files.append(
            ChangeFile(
                path=path,
                status=_text(item.get("status")) or "modified",
                revision=revision,
                url=path,
            )
        )
    return tuple(files)


def _dc_changes(values: object, revision: str) -> tuple[ChangeFile, ...]:
    if not isinstance(values, list):
        return ()
    files: list[ChangeFile] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        path_info = item.get("path")
        path = (
            _text(path_info.get("toString"))
            if isinstance(path_info, dict)
            else _text(path_info)
        )
        if path is None:
            continue
        files.append(
            ChangeFile(
                path=path,
                status=_text(item.get("type")) or "MODIFY",
                revision=revision,
                url=path,
            )
        )
    return tuple(files)


def _link(payload: dict[str, object], name: str) -> str | None:
    links = payload.get("links")
    if not isinstance(links, dict):
        return None
    value = links.get(name)
    if isinstance(value, dict):
        href = value.get("href")
        return href if isinstance(href, str) else None
    if isinstance(value, list) and value and isinstance(value[0], dict):
        href = value[0].get("href")
        return href if isinstance(href, str) else None
    return None


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


def _nested(payload: dict[str, object], *keys: str) -> object:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
