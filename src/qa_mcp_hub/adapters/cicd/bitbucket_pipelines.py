"""Bitbucket Pipelines read adapter.

Purpose: read pipeline definitions' execution metadata, logs, and artifacts.
Milestone: 08
Status: IMPLEMENTED
Ownership: adapters.cicd.bitbucket_pipelines
Dependencies: Shared CI records and the read-only HTTP client.
Expected tests: run state, pagination, permission, expiry, and revision match.
"""

from datetime import datetime

import httpx

from qa_mcp_hub.adapters.cicd.base import (
    CiArtifact,
    CiRun,
    PipelineState,
    artifact_expired,
    issue_keys,
    observed_revision,
    post_once,
    prepare_log,
)
from qa_mcp_hub.adapters.git.base import (
    ReadOnlyClient,
    json_object,
    validate_repository_slug,
)
from qa_mcp_hub.core.errors import ProviderRequestError

_HOST = "api.bitbucket.org"


class BitbucketPipelinesAdapter:
    """Read Bitbucket Cloud pipeline runs for one repository."""

    def __init__(
        self,
        client: ReadOnlyClient,
        *,
        token: str,
        repository: str,
        ref: str = "",
        http: httpx.Client | None = None,
    ) -> None:
        workspace, name = validate_repository_slug(repository)
        self._client = client
        self._token = token
        self._repository = repository
        self._workspace = workspace
        self._name = name
        self._ref = ref
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
        """Return at most two pages of pipeline executions."""
        del now, secrets
        response = self._client.get(
            self._collection_url(),
            headers=self._headers(),
            params={"pagelen": 20, "page": 1, "sort": "-created_on"},
        )
        payload = json_object(response)
        values = _values(payload)
        truncated = False
        following = payload.get("next")
        if isinstance(following, str) and following:
            second = self._client.get(following, headers=self._headers())
            second_payload = json_object(second)
            values.extend(_values(second_payload))
            truncated = isinstance(second_payload.get("next"), str)
        runs: list[CiRun | None] = []
        for row in values:
            if not isinstance(row, dict):
                raise ProviderRequestError(
                    "invalid_response",
                    "provider response had an unexpected shape",
                    status_code=0,
                )
            runs.append(self._summary(row, job_id, suite_ids, issue_pattern, revision))
        return tuple(item for item in runs if item is not None), truncated

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
        """Read one pipeline, its first step log, and declared artifacts."""
        payload = json_object(
            self._client.get(
                f"{self._collection_url()}/{run_id}", headers=self._headers()
            )
        )
        run = self._summary(payload, job_id, suite_ids, issue_pattern, None)
        if run is None:
            raise ProviderRequestError(
                "invalid_response",
                "provider response had an unexpected shape",
                status_code=0,
            )
        excerpt, truncated, incomplete = self._log(run_id, secrets)
        return run.model_copy(
            update={
                "log_excerpt": excerpt,
                "log_truncated": truncated,
                "log_incomplete": incomplete,
                "artifacts": self._artifacts(run_id, now),
            }
        )

    def trigger(self, *, ref: str) -> httpx.Response:
        """POST one pipeline run. The caller must already hold approval."""
        if self._http is None:
            raise ProviderRequestError(
                "trigger_not_configured",
                "pipeline trigger is not configured",
                status_code=0,
            )
        return post_once(
            self._http,
            self._collection_url() + "/",
            headers={**self._headers(), "Content-Type": "application/json"},
            body={
                "target": {
                    "type": "pipeline_ref_target",
                    "ref_type": "branch",
                    "ref_name": ref,
                }
            },
            allowed_host=_HOST,
        )

    def _summary(
        self,
        row: dict[str, object],
        job_id: str,
        suite_ids: tuple[str, ...],
        issue_pattern: str,
        revision: str | None,
    ) -> CiRun | None:
        target = row.get("target")
        commit = target.get("commit") if isinstance(target, dict) else None
        commit_hash = commit.get("hash") if isinstance(commit, dict) else None
        message = commit.get("message") if isinstance(commit, dict) else ""
        observed = observed_revision(commit_hash)
        if revision is not None and observed != revision:
            return None
        identifier = row.get("uuid")
        if not isinstance(identifier, str) or not identifier:
            raise ProviderRequestError(
                "invalid_response",
                "provider response had an unexpected shape",
                status_code=0,
            )
        text = message if isinstance(message, str) else ""
        return CiRun(
            provider="bitbucket_pipelines",
            job_id=job_id,
            run_id=identifier.strip("{}"),
            pipeline_status=_bitbucket_state(row.get("state")),
            revision=observed,
            repository=self._repository,
            url=_safe_url(row.get("links")),
            suite_ids=suite_ids if observed is not None else (),
            issue_keys=issue_keys(text, issue_pattern),
            log_incomplete=True,
        )

    def _log(self, run_id: str, secrets: tuple[str, ...]) -> tuple[str, bool, bool]:
        steps = json_object(
            self._client.get(
                f"{self._collection_url()}/{run_id}/steps/",
                headers=self._headers(),
            )
        )
        values = _values(steps)
        if not values:
            return "", False, True
        step = values[0]
        step_id = step.get("uuid") if isinstance(step, dict) else None
        if not isinstance(step_id, str):
            return "", False, True
        try:
            response = self._client.get(
                f"{self._collection_url()}/{run_id}/steps/{step_id}/log",
                headers=self._headers(),
            )
        except ProviderRequestError as exc:
            if exc.code in {"not_found", "permission_denied", "unapproved_host"}:
                return "", False, True
            raise
        return prepare_log(response.text, secrets=secrets, incomplete=False)

    def _artifacts(self, run_id: str, now: datetime) -> tuple[CiArtifact, ...]:
        steps = json_object(
            self._client.get(
                f"{self._collection_url()}/{run_id}/steps/",
                headers=self._headers(),
            )
        )
        artifacts: list[CiArtifact] = []
        for step in _values(steps):
            if not isinstance(step, dict):
                continue
            declared = step.get("artifacts")
            if not isinstance(declared, list):
                continue
            for item in declared:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if not isinstance(name, str) or not name:
                    continue
                expired = artifact_expired(
                    item.get("expired"), item.get("expires_at"), now
                )
                artifacts.append(
                    CiArtifact(
                        name=name,
                        expired=expired,
                        available=not expired,
                        url="",
                    )
                )
        return tuple(artifacts)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}

    def _collection_url(self) -> str:
        return (
            f"https://{_HOST}/2.0/repositories/{self._workspace}/{self._name}/pipelines"
        )


def _bitbucket_state(value: object) -> PipelineState:
    if not isinstance(value, dict):
        return PipelineState.UNKNOWN
    name = value.get("name")
    if name in {"PENDING", "PARSING"}:
        return PipelineState.QUEUED
    if name == "IN_PROGRESS":
        return PipelineState.RUNNING
    result = value.get("result")
    result_name = result.get("name") if isinstance(result, dict) else None
    if result_name == "SUCCESSFUL":
        return PipelineState.SUCCEEDED
    if result_name in {"FAILED", "ERROR"}:
        return PipelineState.FAILED
    if result_name in {"STOPPED"}:
        return PipelineState.CANCELLED
    return PipelineState.UNKNOWN


def _values(payload: dict[str, object]) -> list[object]:
    value = payload.get("values")
    if not isinstance(value, list):
        raise ProviderRequestError(
            "invalid_response",
            "provider response had an unexpected shape",
            status_code=0,
        )
    return value


def _safe_url(links: object) -> str:
    if not isinstance(links, dict):
        return ""
    self_link = links.get("self")
    href = self_link.get("href") if isinstance(self_link, dict) else None
    if isinstance(href, str) and href.startswith("https://"):
        return href
    return ""
