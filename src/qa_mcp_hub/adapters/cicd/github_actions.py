"""GitHub Actions read adapter.

Purpose: read workflow runs, jobs, logs, and artifact metadata.
Milestone: 08
Status: IMPLEMENTED
Ownership: adapters.cicd.github_actions
Dependencies: Shared CI records and the read-only HTTP client.
Expected tests: run state, pagination, permission, expiry, and redaction.
"""

import base64
from datetime import datetime

import httpx

from qa_mcp_hub.adapters.cicd.base import (
    CiArtifact,
    CiRun,
    PipelineState,
    artifact_expired,
    issue_keys,
    observed_revision,
    prepare_log,
)
from qa_mcp_hub.adapters.git.base import (
    ReadOnlyClient,
    json_object,
    next_page,
    validate_repository_slug,
)
from qa_mcp_hub.core.errors import ProviderRequestError

_HOST = "api.github.com"


class GitHubActionsAdapter:
    """Read one repository's Actions runs. Dispatch is a separate single POST."""

    def __init__(
        self,
        client: ReadOnlyClient,
        *,
        token: str,
        repository: str,
        workflow: str,
        http: httpx.Client | None = None,
    ) -> None:
        owner, name = validate_repository_slug(repository)
        self._client = client
        self._token = token
        self._repository = repository
        self._workflow = workflow
        self._owner = owner
        self._name = name
        self._http = http

    def list_runs(
        self,
        *,
        job_id: str,
        revision: str | None,
        suite_ids: tuple[str, ...],
        issue_pattern: str,
        now: datetime,
        secrets: tuple[str, ...] = (),
    ) -> tuple[tuple[CiRun, ...], bool]:
        """Return at most two pages of workflow runs."""
        first, truncated = self._pages()
        runs: list[CiRun] = []
        for item in first:
            row = _as_dict(item)
            observed = observed_revision(row.get("head_sha"))
            if revision is not None and observed != revision:
                continue
            runs.append(
                self._run(
                    row,
                    job_id=job_id,
                    suite_ids=suite_ids,
                    issue_pattern=issue_pattern,
                    now=now,
                    secrets=secrets,
                    with_details=False,
                )
            )
        return tuple(runs), truncated

    def read_run(
        self,
        run_id: str,
        *,
        job_id: str,
        suite_ids: tuple[str, ...],
        issue_pattern: str,
        now: datetime,
        secrets: tuple[str, ...] = (),
    ) -> CiRun:
        """Read one run, including bounded logs and artifact metadata."""
        payload = json_object(
            self._client.get(self._run_url(run_id), headers=self._headers())
        )
        return self._run(
            payload,
            job_id=job_id,
            suite_ids=suite_ids,
            issue_pattern=issue_pattern,
            now=now,
            secrets=secrets,
            with_details=True,
        )

    def trigger(self, *, ref: str, parameters: dict[str, str]) -> httpx.Response:
        """POST one workflow dispatch. The caller must already hold approval."""
        if self._http is None or not self._workflow:
            raise ProviderRequestError(
                "trigger_not_configured",
                "workflow dispatch is not configured",
                status_code=0,
            )
        from qa_mcp_hub.adapters.cicd.base import post_once

        url = (
            f"https://{_HOST}/repos/{self._owner}/{self._name}"
            f"/actions/workflows/{self._workflow}/dispatches"
        )
        return post_once(
            self._http,
            url,
            headers=self._headers(),
            body={"ref": ref, "inputs": parameters},
            allowed_host=_HOST,
        )

    def _pages(self) -> tuple[list[object], bool]:
        response = self._client.get(
            self._collection_url(),
            headers=self._headers(),
            params={"per_page": 20, "page": 1},
        )
        values = _values(json_object(response), "workflow_runs")
        truncated = False
        following = next_page(response)
        if following is not None and following.isdigit():
            second = self._client.get(
                self._collection_url(),
                headers=self._headers(),
                params={"per_page": 20, "page": int(following)},
            )
            values.extend(_values(json_object(second), "workflow_runs"))
            truncated = next_page(second) is not None
        return values, truncated

    def _run(
        self,
        row: dict[str, object],
        *,
        job_id: str,
        suite_ids: tuple[str, ...],
        issue_pattern: str,
        now: datetime,
        secrets: tuple[str, ...],
        with_details: bool,
    ) -> CiRun:
        run_id = _identifier(row.get("id"))
        message = row.get("display_title")
        text = message if isinstance(message, str) else ""
        excerpt = ""
        truncated = False
        incomplete = not with_details
        artifacts: tuple[CiArtifact, ...] = ()
        if with_details:
            excerpt, truncated, incomplete = self._log(run_id, secrets)
            artifacts = self._artifacts(run_id, now)
        revision = observed_revision(row.get("head_sha"))
        return CiRun(
            provider="github_actions",
            job_id=job_id,
            run_id=run_id,
            pipeline_status=_github_state(row.get("status"), row.get("conclusion")),
            revision=revision,
            repository=self._repository,
            url=_safe_url(row.get("html_url")),
            suite_ids=suite_ids if revision is not None else (),
            issue_keys=issue_keys(text, issue_pattern),
            log_excerpt=excerpt,
            log_truncated=truncated,
            log_incomplete=incomplete,
            artifacts=artifacts,
        )

    def _log(self, run_id: str, secrets: tuple[str, ...]) -> tuple[str, bool, bool]:
        jobs = json_object(
            self._client.get(
                f"{self._run_url(run_id)}/jobs",
                headers=self._headers(),
                params={"per_page": 20, "page": 1},
            )
        )
        rows = _values(jobs, "jobs")
        if not rows:
            return "", False, True
        job = _as_dict(rows[0])
        job_number = _identifier(job.get("id"))
        try:
            response = self._client.get(
                f"https://{_HOST}/repos/{self._owner}/{self._name}/actions/jobs/{job_number}/logs",
                headers=self._headers(),
            )
        except ProviderRequestError as exc:
            if exc.code in {"unapproved_host", "not_found", "permission_denied"}:
                return "", False, True
            raise
        return prepare_log(response.text, secrets=secrets, incomplete=False)

    def _artifacts(self, run_id: str, now: datetime) -> tuple[CiArtifact, ...]:
        payload = json_object(
            self._client.get(
                f"{self._run_url(run_id)}/artifacts", headers=self._headers()
            )
        )
        artifacts: list[CiArtifact] = []
        for item in _values(payload, "artifacts"):
            row = _as_dict(item)
            name = row.get("name")
            if not isinstance(name, str) or not name:
                continue
            expired = artifact_expired(row.get("expired"), row.get("expires_at"), now)
            size = row.get("size_in_bytes")
            artifacts.append(
                CiArtifact(
                    name=name,
                    expired=expired,
                    available=not expired,
                    size_bytes=size if isinstance(size, int) else None,
                    url="",
                )
            )
        return tuple(artifacts)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "qa-mcp-hub",
        }

    def _collection_url(self) -> str:
        root = f"https://{_HOST}/repos/{self._owner}/{self._name}/actions"
        if self._workflow:
            return f"{root}/workflows/{self._workflow}/runs"
        return f"{root}/runs"

    def _run_url(self, run_id: str) -> str:
        return f"https://{_HOST}/repos/{self._owner}/{self._name}/actions/runs/{run_id}"


def _github_state(status: object, conclusion: object) -> PipelineState:
    if status in {"queued", "waiting", "pending", "requested"}:
        return PipelineState.QUEUED
    if status == "in_progress":
        return PipelineState.RUNNING
    if conclusion == "success":
        return PipelineState.SUCCEEDED
    if conclusion in {"failure", "timed_out", "startup_failure"}:
        return PipelineState.FAILED
    if conclusion in {"cancelled", "skipped"}:
        return PipelineState.CANCELLED
    return PipelineState.UNKNOWN


def _values(payload: dict[str, object], key: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ProviderRequestError(
            "invalid_response",
            "provider response had an unexpected shape",
            status_code=0,
        )
    return value


def _as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProviderRequestError(
            "invalid_response",
            "provider response had an unexpected shape",
            status_code=0,
        )
    return value


def _identifier(value: object) -> str:
    if isinstance(value, int) and value > 0:
        return str(value)
    if isinstance(value, str) and value.isdigit():
        return value
    raise ProviderRequestError(
        "invalid_response",
        "provider response had an unexpected shape",
        status_code=0,
    )


def _safe_url(value: object) -> str:
    if isinstance(value, str) and value.startswith("https://"):
        return value
    return ""


def basic_header(account: str, token: str) -> str:
    """Build a Basic header without returning the decoded credential."""
    raw = f"{account}:{token}".encode()
    return "Basic " + base64.b64encode(raw).decode("ascii")
