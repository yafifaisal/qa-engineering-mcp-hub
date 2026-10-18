"""Jenkins read adapter.

Purpose: read job builds, status, bounded console text, and artifact names.
Milestone: 08
Status: IMPLEMENTED
Ownership: adapters.cicd.jenkins
Dependencies: Shared CI records and the read-only HTTP client.
Expected tests: build state, permission, crumb refusal, and parameter denial.
"""

import re
from datetime import datetime
from urllib.parse import urlsplit

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
from qa_mcp_hub.adapters.cicd.github_actions import basic_header
from qa_mcp_hub.adapters.git.base import ReadOnlyClient, json_object
from qa_mcp_hub.core.errors import ProviderRequestError

_JOB = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_TREE = "builds[number,result,building,url,description,changeSet[items[commitId,msg]]]"


class JenkinsAdapter:
    """Read one registered Jenkins job. Parameters stay on the approved list."""

    def __init__(
        self,
        client: ReadOnlyClient,
        *,
        account: str,
        token: str,
        base_url: str,
        job_name: str,
        http: httpx.Client | None = None,
    ) -> None:
        if _JOB.fullmatch(job_name) is None:
            raise ProviderRequestError(
                "invalid_repository",
                "Jenkins job name is invalid",
                status_code=0,
            )
        parts = urlsplit(base_url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not host or parts.username or parts.password:
            raise ProviderRequestError(
                "unapproved_host",
                "Jenkins URL is outside the configured host",
                status_code=0,
            )
        self._client = client
        self._account = account
        self._token = token
        self._origin = f"https://{host}"
        if parts.port is not None:
            self._origin = f"https://{host}:{parts.port}"
        self._host = host
        self._job = job_name
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
        """Return one bounded build page. A full page is marked truncated."""
        del now, secrets
        payload = json_object(
            self._client.get(
                f"{self._origin}/job/{self._job}/api/json",
                headers=self._headers(),
                params={"tree": _TREE},
            )
        )
        builds = payload.get("builds")
        if not isinstance(builds, list):
            raise ProviderRequestError(
                "invalid_response",
                "provider response had an unexpected shape",
                status_code=0,
            )
        runs = [
            self._summary(row, job_id, suite_ids, issue_pattern, revision)
            for row in builds[:20]
        ]
        return tuple(item for item in runs if item is not None), len(builds) >= 20

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
        """Read one build, a redacted console excerpt, and artifact names."""
        if not run_id.isdigit():
            raise ProviderRequestError(
                "invalid_response",
                "Jenkins build number is invalid",
                status_code=0,
            )
        payload = json_object(
            self._client.get(
                f"{self._origin}/job/{self._job}/{run_id}/api/json",
                headers=self._headers(),
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
                "artifacts": self._artifacts(payload, now),
            }
        )

    def trigger(self, parameters: dict[str, str]) -> httpx.Response:
        """POST one build. The caller must already hold approval."""
        if self._http is None:
            raise ProviderRequestError(
                "trigger_not_configured",
                "Jenkins trigger is not configured",
                status_code=0,
            )
        headers = self._headers()
        crumb = self._crumb()
        if crumb is not None:
            headers["Jenkins-Crumb"] = crumb
        url = f"{self._origin}/job/{self._job}/buildWithParameters"
        return post_once(
            self._http,
            url,
            headers=headers,
            form=parameters,
            allowed_host=self._host,
        )

    def _summary(
        self,
        row: object,
        job_id: str,
        suite_ids: tuple[str, ...],
        issue_pattern: str,
        revision: str | None,
    ) -> CiRun | None:
        if not isinstance(row, dict):
            raise ProviderRequestError(
                "invalid_response",
                "provider response had an unexpected shape",
                status_code=0,
            )
        number = row.get("number")
        if not isinstance(number, int):
            raise ProviderRequestError(
                "invalid_response",
                "provider response had an unexpected shape",
                status_code=0,
            )
        observed, message = _commit(row)
        if revision is not None and observed != revision:
            return None
        return CiRun(
            provider="jenkins",
            job_id=job_id,
            run_id=str(number),
            pipeline_status=_jenkins_state(row.get("result"), row.get("building")),
            revision=observed,
            repository=self._job,
            url=_safe_url(row.get("url")),
            suite_ids=suite_ids if observed is not None else (),
            issue_keys=issue_keys(message, issue_pattern),
            log_incomplete=True,
        )

    def _log(self, run_id: str, secrets: tuple[str, ...]) -> tuple[str, bool, bool]:
        try:
            response = self._client.get(
                f"{self._origin}/job/{self._job}/{run_id}/consoleText",
                headers=self._headers(),
            )
        except ProviderRequestError as exc:
            if exc.code in {"not_found", "permission_denied"}:
                return "", False, True
            raise
        return prepare_log(response.text, secrets=secrets, incomplete=False)

    def _artifacts(
        self, payload: dict[str, object], now: datetime
    ) -> tuple[CiArtifact, ...]:
        raw = payload.get("artifacts")
        if not isinstance(raw, list):
            return ()
        artifacts: list[CiArtifact] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("fileName")
            if not isinstance(name, str) or not name:
                continue
            expired = artifact_expired(item.get("expired"), None, now)
            artifacts.append(
                CiArtifact(name=name, expired=expired, available=not expired, url="")
            )
        return tuple(artifacts)

    def _crumb(self) -> str | None:
        try:
            payload = json_object(
                self._client.get(
                    f"{self._origin}/crumbIssuer/api/json",
                    headers=self._headers(),
                )
            )
        except ProviderRequestError as exc:
            if exc.code == "not_found":
                return None
            raise
        crumb = payload.get("crumb")
        if not isinstance(crumb, str) or not crumb:
            raise ProviderRequestError(
                "invalid_response",
                "Jenkins crumb response was incomplete",
                status_code=0,
            )
        return crumb

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": basic_header(self._account, self._token),
            "Accept": "application/json",
        }


def _jenkins_state(result: object, building: object) -> PipelineState:
    if building is True:
        return PipelineState.RUNNING
    if result is None:
        return PipelineState.QUEUED
    if result == "SUCCESS":
        return PipelineState.SUCCEEDED
    if result in {"FAILURE", "UNSTABLE"}:
        return PipelineState.FAILED
    if result in {"ABORTED", "NOT_BUILT"}:
        return PipelineState.CANCELLED
    return PipelineState.UNKNOWN


def _commit(row: dict[str, object]) -> tuple[str | None, str]:
    change = row.get("changeSet")
    items = change.get("items") if isinstance(change, dict) else None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        return None, ""
    first = items[0]
    message = first.get("msg")
    return observed_revision(first.get("commitId")), message if isinstance(
        message, str
    ) else ""


def _safe_url(value: object) -> str:
    if isinstance(value, str) and value.startswith("https://"):
        return value
    return ""
