"""Policy-aware suite and workflow execution.

Purpose: preview an approved workflow, then run only its API suites.
Milestone: 06
Status: IMPLEMENTED
Ownership: workflows.service
Dependencies: Registry, planner, executor, and the execution store.
Expected tests: authorization, dry runs, cancellation, and results.
"""

import os
import shutil
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from qa_mcp_hub.config.loader import load_config
from qa_mcp_hub.config.models import HubConfig
from qa_mcp_hub.config.paths import default_config_dir
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.runners.execution_context import ExecutionContext
from qa_mcp_hub.runners.job_manager import JobManager
from qa_mcp_hub.runners.polling import poll_until
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.suites.models import SuiteCatalog, SuiteDefinition
from qa_mcp_hub.suites.registry import catalog_for, load_suite_registry, suite_by_id
from qa_mcp_hub.workflows.executor import queued_record, run_api_workflow
from qa_mcp_hub.workflows.matcher import match_workflows, suggest_candidates
from qa_mcp_hub.workflows.models import (
    ExecutionRecord,
    RunReceipt,
    StepKind,
    WorkflowCandidate,
    WorkflowDefinition,
    WorkflowExplanation,
    WorkflowStep,
)
from qa_mcp_hub.workflows.planner import explain_definition
from qa_mcp_hub.workflows.registry import load_workflows, workflow_by_id
from qa_mcp_hub.workflows.state_machine import is_terminal

SecretValues = dict[str, str]


class ExecutionService:
    """Registered-suite execution for one open store."""

    def __init__(
        self,
        store: ExecutionStore,
        *,
        clock: Callable[[], datetime] | None = None,
        config_loader: Callable[[], HubConfig] | None = None,
        id_factory: Callable[[], str] | None = None,
        secrets: Callable[[str], str] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._config_loader = config_loader or load_config
        self._ids = id_factory or (lambda: uuid.uuid4().hex)
        self._secrets = secrets
        self._jobs = JobManager(1)
        self._concurrency: dict[str, JobManager] = {}

    def close(self) -> None:
        """Wait for background jobs."""
        for manager in self._concurrency.values():
            manager.join(2)
        self._jobs.join(2)

    def list_suites(self, profile: str | None = None) -> SuiteCatalog:
        """List registered suites and collections at their paths."""
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        return catalog_for(_workspace(config, profile_id), profile_id)

    def list_workflows(
        self,
        profile: str | None = None,
        *,
        issue_key: str | None = None,
        changed_paths: tuple[str, ...] = (),
    ) -> tuple[tuple[WorkflowDefinition, ...], tuple[WorkflowCandidate, ...]]:
        """List registered workflows and unapproved suggestions."""
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        workspace = _workspace(config, profile_id)
        workflows = load_workflows(workspace)
        document = load_suite_registry(workspace)
        candidates = suggest_candidates(
            document.suites, issue_key=issue_key, changed_paths=changed_paths
        )
        return workflows, candidates

    def explain(
        self,
        workflow_id: str,
        profile: str | None = None,
        *,
        environment: str | None = None,
    ) -> WorkflowExplanation:
        """Preview one workflow. No process is started."""
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        workspace = _workspace(config, profile_id)
        workflow = workflow_by_id(load_workflows(workspace), workflow_id)
        suites = {item.id: item for item in load_suite_registry(workspace).suites}
        return explain_definition(
            workflow,
            suites,
            report_path=self._store.path.parent / "preview-report.json",
            environment=environment,
        )

    def match(
        self,
        profile: str | None = None,
        *,
        issue_key: str | None = None,
        changed_paths: tuple[str, ...] = (),
    ) -> tuple[WorkflowDefinition, ...]:
        """Rank approved workflows. An empty result is a no-match."""
        workflows, _candidates = self.list_workflows(
            profile, issue_key=issue_key, changed_paths=changed_paths
        )
        return match_workflows(
            workflows, issue_key=issue_key, changed_paths=changed_paths
        )

    def submit(
        self,
        *,
        profile: str | None = None,
        workflow_id: str | None = None,
        suite_id: str | None = None,
        execute: bool = False,
        environment: str | None = None,
        wait: bool = True,
    ) -> RunReceipt:
        """Preview or execute. Execution requires an approved API-only workflow."""
        if (workflow_id is None) == (suite_id is None):
            raise HubError("run_target", "submit one workflow id or one suite id")
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        workspace = _workspace(config, profile_id)
        document = load_suite_registry(workspace)
        suites = {item.id: item for item in document.suites}
        workflow = _target_workflow(
            workspace, workflow_id=workflow_id, suite_id=suite_id
        )
        plan = explain_definition(
            workflow,
            suites,
            report_path=self._store.path.parent / "preview-report.json",
            environment=environment,
        )
        limits = _limits(config, profile_id)
        if not execute or limits[2] or plan.blocked_reason is not None:
            reason = plan.blocked_reason
            if not execute and reason is None:
                reason = None
            if limits[2] and execute:
                reason = "dry_run"
            return RunReceipt(executed=False, plan=plan, blocked_reason=reason)
        selected = _selected_suites(workflow, suites, document.implementation_status)
        _check_operation(selected, allow_mutations=limits[3])
        _check_environment(selected, environment)
        secrets = _resolve_secrets(selected, self._secrets)
        context = _context(
            self._ids(),
            profile_id,
            workflow,
            selected,
            environment,
            limits,
        )
        manager = self._manager(profile_id, limits[1])
        manager.register(context.execution_id)
        clock = self._clock()
        self._store.save(queued_record(context, clock))

        def action(ctx: ExecutionContext, event: threading.Event) -> None:
            record = run_api_workflow(
                ctx,
                tuple(selected),
                workspace=workspace,
                binaries=_binaries(),
                run_root=self._store.path.parent / "runs",
                secret_values=secrets,
                clock=clock,
                cancel=event,
            )
            self._store.save(record)

        manager.run(context, action, wait=wait)
        if not wait:
            return RunReceipt(
                executed=True,
                plan=plan,
                run=self._store.get(profile_id, context.execution_id),
            )
        return RunReceipt(
            executed=True,
            plan=plan,
            run=self._store.get(profile_id, context.execution_id),
        )

    def get_run(
        self,
        execution_id: str,
        profile: str | None = None,
        *,
        wait_seconds: float = 0,
    ) -> ExecutionRecord:
        """Read one profile-owned run. Waiting is bounded."""
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        if wait_seconds:
            poll_until(
                lambda: is_terminal(self._store.status_of(profile_id, execution_id)),
                timeout_seconds=wait_seconds,
                interval_seconds=0.05,
                max_attempts=100,
            )
        return self._store.get(profile_id, execution_id)

    def cancel(self, execution_id: str, profile: str | None = None) -> ExecutionRecord:
        """Cancel a non-terminal run. The stored row updates when the job stops."""
        config = self._config_loader()
        profile_id = _profile_id(config, profile)
        current = self._store.get(profile_id, execution_id)
        if is_terminal(current.status):
            raise HubError("terminal_state", f"{current.status.value} cannot change")
        manager = self._concurrency.get(profile_id)
        if manager is None or not manager.cancel(execution_id):
            raise HubError("unknown_execution", "execution is not running")
        poll_until(
            lambda: is_terminal(self._store.status_of(profile_id, execution_id)),
            timeout_seconds=5,
            interval_seconds=0.05,
            max_attempts=100,
        )
        return self._store.get(profile_id, execution_id)

    def _manager(self, profile_id: str, max_concurrency: int) -> JobManager:
        manager = self._concurrency.get(profile_id)
        if manager is None:
            manager = JobManager(max_concurrency)
            self._concurrency[profile_id] = manager
        return manager


def resolve_execution_path() -> Path:
    """Return the execution database path."""
    override = os.environ.get("QA_MCP_EXECUTION_PATH", "").strip()
    if override:
        return Path(override)
    return default_config_dir() / "executions" / "runs.sqlite"


def open_execution(
    *,
    config_loader: Callable[[], HubConfig] | None = None,
    secrets: Callable[[str], str] | None = None,
) -> ExecutionService:
    """Open the local execution store."""
    return ExecutionService(
        ExecutionStore(resolve_execution_path()),
        config_loader=config_loader,
        secrets=secrets,
    )


def list_registered_suites(
    profile: str | None = None,
    *,
    config_loader: Callable[[], HubConfig] | None = None,
) -> SuiteCatalog:
    """List suites for the active profile."""
    service = open_execution(config_loader=config_loader)
    try:
        return service.list_suites(profile)
    finally:
        service.close()


def list_workflow_catalog(
    profile: str | None = None,
    *,
    issue_key: str | None = None,
    changed_paths: tuple[str, ...] = (),
    config_loader: Callable[[], HubConfig] | None = None,
) -> tuple[tuple[WorkflowDefinition, ...], tuple[WorkflowCandidate, ...]]:
    """List workflows and unapproved candidates."""
    service = open_execution(config_loader=config_loader)
    try:
        return service.list_workflows(
            profile, issue_key=issue_key, changed_paths=changed_paths
        )
    finally:
        service.close()


def explain_workflow(
    workflow_id: str,
    profile: str | None = None,
    *,
    environment: str | None = None,
    config_loader: Callable[[], HubConfig] | None = None,
) -> WorkflowExplanation:
    """Preview a workflow."""
    service = open_execution(config_loader=config_loader)
    try:
        return service.explain(workflow_id, profile, environment=environment)
    finally:
        service.close()


def submit_test_run(
    *,
    workflow_id: str | None = None,
    suite_id: str | None = None,
    execute: bool = False,
    environment: str | None = None,
    profile: str | None = None,
    config_loader: Callable[[], HubConfig] | None = None,
    secrets: Callable[[str], str] | None = None,
) -> RunReceipt:
    """Preview or execute one registered target."""
    service = open_execution(config_loader=config_loader, secrets=secrets)
    try:
        return service.submit(
            profile=profile,
            workflow_id=workflow_id,
            suite_id=suite_id,
            execute=execute,
            environment=environment,
            wait=True,
        )
    finally:
        service.close()


def get_test_run(
    execution_id: str,
    profile: str | None = None,
    *,
    wait_seconds: float = 0,
    config_loader: Callable[[], HubConfig] | None = None,
) -> ExecutionRecord:
    """Read one persisted run."""
    service = open_execution(config_loader=config_loader)
    try:
        return service.get_run(execution_id, profile, wait_seconds=wait_seconds)
    finally:
        service.close()


def _profile_id(config: HubConfig, profile: str | None) -> str:
    selected = profile or config.active_profile
    if selected is None or selected not in config.profiles:
        raise HubError("profile_required", "an active profile is required")
    return selected


def _workspace(config: HubConfig, profile_id: str) -> Path:
    profile = config.profiles[profile_id]
    if profile.workspace_id is None:
        raise HubError("workspace_required", "profile has no QA workspace")
    for item in config.workspaces:
        if item.id == profile.workspace_id:
            return Path(item.path)
    raise HubError("workspace_required", "workspace reference is missing")


def _limits(config: HubConfig, profile_id: str) -> tuple[int, int, bool, bool]:
    base = config.execution
    overrides = config.profiles[profile_id].execution
    timeout = overrides.timeout_seconds or base.timeout_seconds
    concurrency = overrides.max_concurrency or base.max_concurrency
    dry_run = base.dry_run if overrides.dry_run is None else overrides.dry_run
    mutations = (
        base.allow_mutations
        if overrides.allow_mutations is None
        else overrides.allow_mutations
    )
    return timeout, concurrency, dry_run, mutations


def _target_workflow(
    workspace: Path,
    *,
    workflow_id: str | None,
    suite_id: str | None,
) -> WorkflowDefinition:
    if workflow_id is not None:
        return workflow_by_id(load_workflows(workspace), workflow_id)
    suite = suite_by_id(load_suite_registry(workspace), suite_id or "")
    return WorkflowDefinition(
        schema_version=1,
        id=f"suite-{suite.id}",
        name=suite.id,
        implementation_status="IMPLEMENTED",
        enabled=suite.enabled,
        approved=True,
        evidence_policy="api-only",
        steps=(
            WorkflowStep(
                id="run-suite",
                kind=StepKind.api_suite,
                target=suite.id,
                depends_on=(),
                assertion_ids=suite.assertion_ids,
            ),
        ),
    )


def _selected_suites(
    workflow: WorkflowDefinition,
    suites: dict[str, SuiteDefinition],
    registry_status: str,
) -> list[SuiteDefinition]:
    if registry_status != "IMPLEMENTED":
        raise HubError("registry_not_approved", "suite registry is not approved")
    if not workflow.approved or not workflow.enabled:
        raise HubError(
            "workflow_not_approved", "workflow is not approved for execution"
        )
    selected: list[SuiteDefinition] = []
    for step in workflow.steps:
        if step.kind is not StepKind.api_suite:
            raise HubError(
                "non_api_step_unavailable",
                "database and Kafka steps are unavailable until Milestone 07",
            )
        suite = suites[step.target]
        if not suite.enabled:
            raise HubError("suite_disabled", f"suite {suite.id} is disabled")
        selected.append(suite)
    return selected


def _check_operation(suites: list[SuiteDefinition], *, allow_mutations: bool) -> None:
    mutating = any(suite.allowed_operation == "mutate" for suite in suites)
    if mutating and not allow_mutations:
        raise HubError("mutations_disabled", "mutating suites are not allowed")


def _check_environment(suites: list[SuiteDefinition], environment: str | None) -> None:
    for suite in suites:
        if environment is not None and environment != suite.environment:
            raise HubError(
                "unsupported_environment",
                "requested environment is not registered for this suite",
            )


def _resolve_secrets(
    suites: list[SuiteDefinition], lookup: Callable[[str], str] | None
) -> SecretValues:
    resolved: SecretValues = {}
    for suite in suites:
        for binding in suite.credential_env:
            if lookup is None:
                raise HubError(
                    "credential_unavailable",
                    "credential resolver is not configured",
                )
            try:
                value = lookup(binding.reference)
            except HubError:
                raise
            except (OSError, ValueError, KeyError) as exc:
                raise HubError(
                    "credential_unavailable", "credential could not be resolved"
                ) from exc
            if not value:
                raise HubError(
                    "credential_unavailable", "credential could not be resolved"
                )
            resolved[binding.reference] = value
    return resolved


def _context(
    execution_id: str,
    profile_id: str,
    workflow: WorkflowDefinition,
    suites: list[SuiteDefinition],
    environment: str | None,
    limits: tuple[int, int, bool, bool],
) -> ExecutionContext:
    versions = tuple(dict.fromkeys(suite.version for suite in suites))
    return ExecutionContext(
        execution_id=execution_id,
        profile_id=profile_id,
        workflow_id=workflow.id,
        suite_ids=tuple(suite.id for suite in suites),
        suite_version=",".join(versions),
        source_revision=None,
        timeout_seconds=limits[0],
        environment=environment if environment is not None else suites[0].environment,
        allow_mutations=limits[3],
    )


def _binaries() -> dict[str, Path]:
    return {
        "bruno": _binary("QA_MCP_BRUNO_BIN", "bru"),
        "postman": _binary("QA_MCP_NEWMAN_BIN", "newman"),
    }


def _binary(env_name: str, program: str) -> Path:
    override = os.environ.get(env_name, "").strip()
    if override:
        return Path(override)
    found = shutil.which(program)
    if found is not None:
        return Path(found)
    return Path(program)
