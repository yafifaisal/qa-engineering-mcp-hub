"""MCP tools for registered CI/CD inspection.

Purpose: list runs, status, and artifact metadata without starting a pipeline.
Milestone: 08
Status: IMPLEMENTED
Ownership: mcp.tools.cicd
Dependencies: CI adapters, job registry, approvals, and the execution store.
Expected tests: provider states, permission, expiry, and disabled triggers.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from qa_mcp_hub.adapters.cicd.base import (
    CiRun,
    PipelineRunPage,
    RegisteredJob,
    TriggerPreview,
    TriggerReceipt,
    clean_parameters,
    load_jobs,
    load_mappings,
    parameter_digest,
    require_job,
    require_revision,
)
from qa_mcp_hub.adapters.cicd.bitbucket_pipelines import BitbucketPipelinesAdapter
from qa_mcp_hub.adapters.cicd.github_actions import GitHubActionsAdapter
from qa_mcp_hub.adapters.cicd.jenkins import JenkinsAdapter
from qa_mcp_hub.adapters.git.base import ReadOnlyClient
from qa_mcp_hub.auth.credential_resolver import CredentialResolver
from qa_mcp_hub.auth.credential_store import CredentialStore
from qa_mcp_hub.auth.environment_store import EnvironmentCredentialStore
from qa_mcp_hub.auth.keyring_store import KeyringCredentialStore
from qa_mcp_hub.auth.models import CredentialStoreKind
from qa_mcp_hub.config.loader import load_config
from qa_mcp_hub.config.models import ConnectionConfig, HubConfig
from qa_mcp_hub.core.approvals import ApprovalLedger
from qa_mcp_hub.core.errors import HubError, ProviderRequestError
from qa_mcp_hub.core.policies import authorize_pipeline_read, authorize_pipeline_trigger
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.verification.service import workspace_for
from qa_mcp_hub.workflows.service import resolve_execution_path

Adapter = GitHubActionsAdapter | BitbucketPipelinesAdapter | JenkinsAdapter
_HOSTS = {
    "github_actions": "api.github.com",
    "bitbucket_pipelines": "api.bitbucket.org",
}
_session_factory: Callable[[], tuple[httpx.Client, str]] | None = None


def install_ci_session(factory: Callable[[], tuple[httpx.Client, str]]) -> None:
    """Install a test session. Production tools resolve the configured credential."""
    global _session_factory
    _session_factory = factory


def clear_ci_session() -> None:
    """Remove a test session override."""
    global _session_factory
    _session_factory = None


def list_pipeline_runs_tool(
    job_id: str,
    revision: str | None = None,
    profile: str | None = None,
) -> PipelineRunPage:
    """List registered pipeline runs. A green pipeline is not a QA pass."""
    authorize_pipeline_read()
    page, profile_id = _inspect(job_id, revision, profile, run_id=None)
    _persist(profile_id, page.runs)
    return page


def get_pipeline_status_tool(
    job_id: str,
    run_id: str,
    profile: str | None = None,
) -> PipelineRunPage:
    """Read one run. ``assertion_status`` stays NOT_OBSERVED."""
    authorize_pipeline_read()
    page, profile_id = _inspect(job_id, None, profile, run_id=run_id)
    _persist(profile_id, page.runs)
    return page


def get_pipeline_artifacts_tool(
    job_id: str,
    run_id: str,
    profile: str | None = None,
) -> PipelineRunPage:
    """Return artifact metadata. Expired artifacts are not downloaded."""
    return get_pipeline_status_tool(job_id, run_id, profile)


def prepare_pipeline_trigger_tool(
    job_id: str,
    parameters: dict[str, str] | None = None,
    profile: str | None = None,
) -> TriggerPreview:
    """Preview a trigger. This tool never calls the provider trigger API."""
    config = load_config()
    profile_id, workspace = workspace_for(config, profile)
    job = require_job(load_jobs(workspace), job_id)
    cleaned = clean_parameters(job, parameters)
    decision = authorize_pipeline_trigger(
        allow_trigger=job.allow_trigger,
        mutations_allowed=_mutations(config, profile_id),
        confirmed=False,
        approval_valid=False,
    )
    return TriggerPreview(
        job_id=job.id,
        executed=False,
        trigger_enabled=decision.execute,
        reason=decision.reason,
        parameter_names=tuple(sorted(cleaned)),
    )


def dispatch_registered_trigger(
    job_id: str,
    *,
    parameters: dict[str, str] | None,
    ledger: ApprovalLedger,
    token: str,
    confirmed: bool,
    now: datetime,
    profile: str | None = None,
) -> TriggerReceipt:
    """Fire one approved trigger. This function is not an MCP tool.

    Providers do not offer an idempotent trigger, so a failed POST is not retried
    and the approval is spent before the request is sent.
    """
    config = load_config()
    profile_id, workspace = workspace_for(config, profile)
    job = require_job(load_jobs(workspace), job_id)
    cleaned = clean_parameters(job, parameters)
    decision = authorize_pipeline_trigger(
        allow_trigger=job.allow_trigger,
        mutations_allowed=_mutations(config, profile_id),
        confirmed=confirmed,
        approval_valid=True,
    )
    if not decision.execute:
        return TriggerReceipt(job_id=job.id, executed=False, reason=decision.reason)
    ledger.consume(
        token,
        job_id=job.id,
        parameter_digest=parameter_digest(cleaned),
        now=now,
    )
    _connection(config, profile_id, job)
    client, token_value = _open_session(config, _connection(config, profile_id, job))
    try:
        adapter = _adapter(
            job, _connection(config, profile_id, job), client, token_value
        )
        response = _dispatch(adapter, job, cleaned)
    finally:
        client.close()
    return TriggerReceipt(
        job_id=job.id,
        executed=True,
        reason="dispatch_accepted",
        provider_status=response.status_code,
    )


def _inspect(
    job_id: str,
    revision: str | None,
    profile: str | None,
    *,
    run_id: str | None,
) -> tuple[PipelineRunPage, str]:
    config = load_config()
    profile_id, workspace = workspace_for(config, profile)
    job = require_job(load_jobs(workspace), job_id)
    mapping = load_mappings(workspace).get(job_id)
    suites = mapping.suite_ids if mapping is not None else ()
    pattern = mapping.issue_pattern if mapping is not None else r"[A-Z][A-Z0-9]+-\d+"
    selected = require_revision(revision)
    connection = _connection(config, profile_id, job)
    client, token_value = _open_session(config, connection)
    try:
        adapter = _adapter(job, connection, client, token_value)
        observed_at = datetime.now(UTC)
        secret_values = (token_value,)
        if run_id is None:
            runs, truncated = adapter.list_runs(
                job_id=job.id,
                revision=selected,
                suite_ids=suites,
                issue_pattern=pattern,
                now=observed_at,
                secrets=secret_values,
            )
        else:
            runs = (
                adapter.read_run(
                    run_id,
                    job_id=job.id,
                    suite_ids=suites,
                    issue_pattern=pattern,
                    now=observed_at,
                    secrets=secret_values,
                ),
            )
            truncated = False
    finally:
        client.close()
    return PipelineRunPage(job_id=job.id, runs=runs, truncated=truncated), profile_id


def _persist(profile_id: str, runs: tuple[CiRun, ...]) -> None:
    store = ExecutionStore(resolve_execution_path())
    for run in runs:
        store.save_ci_observation(
            profile_id=profile_id,
            provider=run.provider,
            job_id=run.job_id,
            run_id=run.run_id,
            pipeline_status=run.pipeline_status.value,
            record_json=run.model_dump_json(),
        )


def _dispatch(
    adapter: Adapter, job: RegisteredJob, parameters: dict[str, str]
) -> httpx.Response:
    if isinstance(adapter, GitHubActionsAdapter):
        return adapter.trigger(ref=job.ref, parameters=parameters)
    if isinstance(adapter, BitbucketPipelinesAdapter):
        if parameters:
            raise HubError(
                "parameter_rejected", "Bitbucket trigger inputs are not registered"
            )
        return adapter.trigger(ref=job.ref)
    return adapter.trigger(parameters)


def _adapter(
    job: RegisteredJob, connection: ConnectionConfig, client: httpx.Client, token: str
) -> Adapter:
    host = _host(job, connection)
    reader = ReadOnlyClient(client, allowed_host=host)
    if job.provider == "github_actions":
        return GitHubActionsAdapter(
            reader,
            token=token,
            repository=job.repository,
            workflow=job.workflow,
            http=client,
        )
    if job.provider == "bitbucket_pipelines":
        return BitbucketPipelinesAdapter(
            reader,
            token=token,
            repository=job.repository,
            ref=job.ref,
            http=client,
        )
    if connection.account is None or connection.base_url is None:
        raise HubError("credential_missing", "Jenkins account or URL is missing")
    return JenkinsAdapter(
        reader,
        account=connection.account,
        token=token,
        base_url=connection.base_url,
        job_name=job.repository,
        http=client,
    )


def _host(job: RegisteredJob, connection: ConnectionConfig) -> str:
    fixed = _HOSTS.get(job.provider)
    if fixed is not None:
        return fixed
    if connection.base_url is None:
        raise HubError("connection_invalid", "Jenkins connection needs a base URL")
    host = urlsplit(connection.base_url).hostname
    if host is None:
        raise HubError("connection_invalid", "Jenkins connection needs a base URL")
    return host


def _connection(
    config: HubConfig, profile_id: str, job: RegisteredJob
) -> ConnectionConfig:
    profile = config.profiles[profile_id]
    if job.connection_id not in profile.connection_ids:
        raise ProviderRequestError(
            "unknown_connection",
            "connection is not in this profile",
            status_code=0,
        )
    match = next(
        (item for item in config.connections if item.id == job.connection_id),
        None,
    )
    if match is None or match.provider.value != job.provider:
        raise ProviderRequestError(
            "wrong_provider",
            "connection provider does not match the registered job",
            status_code=0,
        )
    return match


def _open_session(
    config: HubConfig, connection: ConnectionConfig
) -> tuple[httpx.Client, str]:
    del config
    if _session_factory is not None:
        return _session_factory()
    secret = _secret(connection)
    return httpx.Client(timeout=10.0), secret.get_secret_value()


def _secret(connection: ConnectionConfig) -> SecretStr:
    if connection.credential is None or connection.auth_kind.value == "oauth":
        raise ProviderRequestError(
            "credential_missing",
            "CI credential reference is missing",
            status_code=0,
        )
    reference = connection.credential
    stores = _stores(reference.store, reference.reference)
    if not stores:
        raise ProviderRequestError(
            "credential_missing",
            "CI credential store is not available",
            status_code=0,
        )
    try:
        resolved = CredentialResolver(stores).resolve(reference)
    except HubError as exc:
        raise ProviderRequestError(exc.code, exc.message, status_code=0) from exc
    return resolved.secret


def _stores(kind: CredentialStoreKind, name: str) -> list[CredentialStore]:
    if kind is CredentialStoreKind.environment:
        return [EnvironmentCredentialStore(allowed_names={name})]
    if kind is CredentialStoreKind.keyring:
        return [KeyringCredentialStore()]
    return []


def _mutations(config: HubConfig, profile_id: str) -> bool:
    override = config.profiles[profile_id].execution.allow_mutations
    if override is not None:
        return override
    return config.execution.allow_mutations
