"""Shared CI/CD records, job registry, and read-only normalization.

Purpose: translate provider runs into records that never claim a QA assertion.
Milestone: 08
Status: IMPLEMENTED
Ownership: adapters.cicd.base
Dependencies: Path allowlist, redaction, and the read-only HTTP client.
Expected tests: state mapping, registry rejection, redaction, and expiry.
"""

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path

import httpx
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from qa_mcp_hub.auth.redaction import redact_text
from qa_mcp_hub.core.errors import HubError, ProviderRequestError
from qa_mcp_hub.security.path_allowlist import resolve_within

_LOG_LIMIT = 2000
_FILE_LIMIT = 65536
_JOB_LIMIT = 50
_ISSUE = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_VALUE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class PipelineState(StrEnum):
    """Provider execution state. This is not a QA assertion result."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class CiArtifact(BaseModel):
    """Artifact metadata. The file body is not stored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    expired: bool
    available: bool
    size_bytes: int | None = None
    url: str = ""


class CiRun(BaseModel):
    """One normalized provider run. ``assertion_status`` stays unobserved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    job_id: str
    run_id: str
    pipeline_status: PipelineState
    assertion_status: str = "NOT_OBSERVED"
    revision: str | None = None
    repository: str
    url: str
    suite_ids: tuple[str, ...] = ()
    issue_keys: tuple[str, ...] = ()
    log_excerpt: str = ""
    log_truncated: bool = False
    log_incomplete: bool = False
    artifacts: tuple[CiArtifact, ...] = ()

    @field_validator("assertion_status")
    @classmethod
    def keep_assertion_unobserved(cls, value: str) -> str:
        """A pipeline record never supplies a QA assertion result."""
        if value != "NOT_OBSERVED":
            raise ValueError("pipeline records cannot claim an assertion status")
        return value


class PipelineRunPage(BaseModel):
    """A bounded page of runs for one registered job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    runs: tuple[CiRun, ...]
    truncated: bool = False


class JobParameter(BaseModel):
    """One input the registry allows a trigger to send."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    allowed_values: tuple[str, ...] = Field(min_length=1)


class RegisteredJob(BaseModel):
    """A CI job the workspace has approved for inspection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    provider: str
    connection_id: str
    repository: str
    workflow: str = ""
    ref: str = ""
    enabled: bool = False
    allow_trigger: bool = False
    parameters: tuple[JobParameter, ...] = ()


class PipelineMapping(BaseModel):
    """Suite association and the issue-key pattern for one job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    suite_ids: tuple[str, ...] = ()
    issue_pattern: str = r"[A-Z][A-Z0-9]+-\d+"


class TriggerPreview(BaseModel):
    """A trigger plan. This model cannot represent a completed remote call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    executed: bool = False
    trigger_enabled: bool
    reason: str
    parameter_names: tuple[str, ...] = ()


class TriggerReceipt(BaseModel):
    """The result of one guarded trigger attempt. It is not a pipeline status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    executed: bool
    reason: str
    provider_status: int | None = None


def require_revision(value: str | None) -> str | None:
    """Accept a full Git SHA or no revision filter."""
    if value is None or value == "":
        return None
    if _REVISION.fullmatch(value) is None:
        raise HubError("invalid_revision", "revision must be a 40-character Git SHA")
    return value


def observed_revision(value: object) -> str | None:
    """Keep a provider SHA only when it is a full 40-character hex value."""
    if not isinstance(value, str) or _REVISION.fullmatch(value) is None:
        return None
    return value


def issue_keys(text: str, pattern: str) -> tuple[str, ...]:
    """Return issue keys that appear in provider text and match the mapping."""
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise HubError("mapping_invalid", "issue pattern is invalid") from exc
    found: list[str] = []
    for match in _ISSUE.findall(text):
        if compiled.fullmatch(match) and match not in found:
            found.append(match)
    return tuple(found[:20])


def prepare_log(
    text: str, *, secrets: tuple[str, ...], incomplete: bool
) -> tuple[str, bool, bool]:
    """Redact and shorten a log. A shortened log is also incomplete."""
    redacted = redact_text(text, secrets=secrets)
    if len(redacted) <= _LOG_LIMIT:
        return redacted, False, incomplete
    return redacted[:_LOG_LIMIT], True, True


def clean_parameters(
    job: RegisteredJob, supplied: dict[str, str] | None
) -> dict[str, str]:
    """Accept only registered parameter names and registered values."""
    incoming = supplied or {}
    allowed = {item.name: set(item.allowed_values) for item in job.parameters}
    unknown = sorted(set(incoming) - set(allowed))
    if unknown:
        raise HubError("parameter_rejected", "job parameter is not registered")
    cleaned: dict[str, str] = {}
    for name, value in incoming.items():
        if value not in allowed[name] or _VALUE.fullmatch(value) is None:
            raise HubError(
                "parameter_rejected", "job parameter value is not registered"
            )
        cleaned[name] = value
    return cleaned


def parameter_digest(parameters: dict[str, str]) -> str:
    """Hash the exact parameter mapping an approval is allowed to send."""
    payload = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_jobs(workspace: Path) -> dict[str, RegisteredJob]:
    """Load the approved job registry from the QA workspace."""
    document = _load_yaml(workspace / "ci" / "registered-jobs.yaml", workspace)
    rows = document.get("jobs")
    if not isinstance(rows, list) or len(rows) > _JOB_LIMIT:
        raise HubError("job_registry_invalid", "job registry has an unexpected shape")
    jobs: dict[str, RegisteredJob] = {}
    for row in rows:
        try:
            job = RegisteredJob.model_validate(row)
        except ValidationError as exc:
            raise HubError(
                "job_registry_invalid", "job registry entry is invalid"
            ) from exc
        if job.id in jobs:
            raise HubError("duplicate_job", "job id is duplicated")
        if job.allow_trigger and not job.ref:
            raise HubError("job_registry_invalid", "a triggerable job needs a ref")
        jobs[job.id] = job
    return jobs


def load_mappings(workspace: Path) -> dict[str, PipelineMapping]:
    """Load suite and issue-key mappings for registered jobs."""
    path = workspace / "ci" / "pipeline-mappings.yaml"
    if not path.is_file():
        return {}
    document = _load_yaml(path, workspace)
    rows = document.get("mappings")
    if not isinstance(rows, list):
        raise HubError("mapping_invalid", "pipeline mappings have an unexpected shape")
    mappings: dict[str, PipelineMapping] = {}
    for row in rows:
        try:
            item = PipelineMapping.model_validate(row)
        except ValidationError as exc:
            raise HubError(
                "mapping_invalid", "pipeline mapping entry is invalid"
            ) from exc
        if item.job_id in mappings:
            raise HubError("duplicate_job", "pipeline mapping is duplicated")
        mappings[item.job_id] = item
    return mappings


def require_job(jobs: dict[str, RegisteredJob], job_id: str) -> RegisteredJob:
    """Return an enabled registered job."""
    job = jobs.get(job_id)
    if job is None:
        raise HubError("job_not_registered", "job is not in the approved registry")
    if not job.enabled:
        raise HubError("job_disabled", "job is registered but disabled")
    return job


def post_once(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, object] | None = None,
    form: dict[str, str] | None = None,
    allowed_host: str,
) -> httpx.Response:
    """Send one trigger request. A failure is not retried."""
    _check_https(url, allowed_host)
    try:
        response = client.request(
            "POST",
            url,
            headers=headers,
            json=body,
            data=form,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise ProviderRequestError(
            "provider_unreachable",
            "provider request failed",
            status_code=0,
        ) from exc
    if response.status_code in {301, 302, 303, 307, 308}:
        raise ProviderRequestError(
            "invalid_redirect",
            "trigger redirect was not followed",
            status_code=response.status_code,
        )
    if response.status_code >= 400:
        code = (
            "permission_denied"
            if response.status_code in {401, 403}
            else (
                "rate_limited"
                if response.status_code in {429, 503}
                else "provider_http"
            )
        )
        raise ProviderRequestError(
            code,
            "trigger request was not accepted",
            status_code=response.status_code,
        )
    return response


def _check_https(url: str, allowed_host: str) -> None:
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    if (
        parts.scheme != "https"
        or host != allowed_host.lower().rstrip(".")
        or parts.username is not None
        or parts.password is not None
    ):
        raise ProviderRequestError(
            "unapproved_host",
            "provider URL is outside the configured host",
            status_code=0,
        )


def _load_yaml(path: Path, workspace: Path) -> dict[str, object]:
    resolved = resolve_within(path, [workspace])
    if resolved.stat().st_size > _FILE_LIMIT:
        raise HubError("job_registry_invalid", "CI registry file is too large")
    loaded = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise HubError("job_registry_invalid", "CI registry file is not a mapping")
    return loaded


def artifact_expired(flag: object, expires_at: object, now: datetime) -> bool:
    """Honor an explicit expiry flag and a timestamp the provider already passed."""
    if flag is True:
        return True
    if not isinstance(expires_at, str) or not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    return parsed <= now
