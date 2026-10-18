"""Run an approved API workflow and persist its normalized record.

Purpose: order registered suites and refuse unavailable verification steps.
Milestone: 06
Status: IMPLEMENTED
Ownership: workflows.executor
Dependencies: Suite runner, state machine, and execution records.
Expected tests: ordering, failure, cancellation, and API-only evidence.
"""

import threading
from datetime import datetime
from pathlib import Path

from qa_mcp_hub.adapters.database.base import DatabaseReader
from qa_mcp_hub.adapters.streaming.kafka import TopicReader
from qa_mcp_hub.runners.execution_context import ExecutionContext
from qa_mcp_hub.runners.result_normalizer import NormalizedResult
from qa_mcp_hub.runners.suite_runner import SuiteRun, run_registered_suite
from qa_mcp_hub.suites.models import SuiteDefinition
from qa_mcp_hub.verification.database_assertions import run_database_assertion
from qa_mcp_hub.verification.invariant_engine import evaluate_invariant
from qa_mcp_hub.verification.kafka_assertions import run_kafka_assertion
from qa_mcp_hub.verification.models import AssertionDefinition, CheckResult
from qa_mcp_hub.workflows.models import (
    ApiOnlyEvidence,
    ExecutionRecord,
    ExecutionStatus,
    StepEvidence,
    StepKind,
    WorkflowDefinition,
)
from qa_mcp_hub.workflows.planner import execution_order
from qa_mcp_hub.workflows.state_machine import transition

_RANK = {
    ExecutionStatus.passed: 0,
    ExecutionStatus.inconclusive: 1,
    ExecutionStatus.failed: 2,
    ExecutionStatus.blocked: 3,
    ExecutionStatus.cancelled: 4,
    ExecutionStatus.timed_out: 5,
    ExecutionStatus.error: 6,
}


def run_api_workflow(
    context: ExecutionContext,
    suites: tuple[SuiteDefinition, ...],
    *,
    workspace: Path,
    binaries: dict[str, Path],
    run_root: Path,
    secret_values: dict[str, str],
    clock: datetime,
    cancel: threading.Event | None,
) -> ExecutionRecord:
    """Run each API suite. A failed step does not continue."""
    runs: list[SuiteRun] = []
    for suite in suites:
        if cancel is not None and cancel.is_set():
            runs.append(_cancelled(suite, workspace))
            break
        binary = binaries[suite.runner]
        runs.append(
            run_registered_suite(
                suite,
                workspace,
                binary=binary,
                run_directory=run_root / context.execution_id / suite.id,
                environment=context.environment,
                timeout_seconds=context.timeout_seconds,
                secret_values=_bindings(suite, secret_values),
                cancel=cancel,
            )
        )
        if runs[-1].normalized.status is not ExecutionStatus.passed:
            break
    combined = _combine(runs)
    process_started = not runs or runs[-1].resolved.argv != ("missing",)
    if runs and runs[-1].normalized.status in {
        ExecutionStatus.cancelled,
        ExecutionStatus.timed_out,
    }:
        process_started = False
    path = _path(combined.status, process_started=process_started)
    revision = next(
        (
            item.resolved.source_revision
            for item in runs
            if item.resolved.source_revision
        ),
        context.source_revision,
    )
    warnings = tuple(warning for item in runs for warning in item.normalized.warnings)
    excerpt = runs[-1].excerpt if runs else ""
    evidence = ApiOnlyEvidence(
        execution_id=context.execution_id,
        profile_id=context.profile_id,
        workflow_id=context.workflow_id,
        suite_ids=context.suite_ids,
        suite_version=context.suite_version,
        source_revision=revision,
        assertion_total=combined.assertion_total,
        assertion_failed=combined.assertion_failed,
        status=combined.status,
        runner_exit_code=combined.exit_code,
        runner_completed=combined.runner_completed,
    )
    return ExecutionRecord(
        execution_id=context.execution_id,
        profile_id=context.profile_id,
        workflow_id=context.workflow_id,
        suite_ids=context.suite_ids,
        suite_version=context.suite_version,
        source_revision=revision,
        status=combined.status,
        assertion_status=combined.assertion_status,
        runner_completed=combined.runner_completed,
        runner_exit_code=combined.exit_code,
        transitions=path,
        queued_at=clock,
        started_at=clock,
        finished_at=clock,
        evidence=evidence,
        excerpt=excerpt,
        warnings=warnings,
    )


def run_e2e_workflow(
    context: ExecutionContext,
    workflow: WorkflowDefinition,
    suites: tuple[SuiteDefinition, ...],
    assertions: dict[str, AssertionDefinition],
    *,
    workspace: Path,
    binaries: dict[str, Path],
    run_root: Path,
    secret_values: dict[str, str],
    clock: datetime,
    cancel: threading.Event | None,
    correlation: dict[str, str],
    approved_connections: dict[str, str],
    database_reader: DatabaseReader | None,
    kafka_reader: TopicReader | None,
) -> ExecutionRecord:
    """Run API steps, then registered database, Kafka, and business checks."""
    suite_by_target = {item.id: item for item in suites}
    api_runs: list[SuiteRun] = []
    steps: list[StepEvidence] = []
    observations: dict[str, str] = {}
    completed: dict[str, ExecutionStatus] = {}
    for step_id in execution_order(workflow):
        step = next(item for item in workflow.steps if item.id == step_id)
        if any(
            completed.get(dependency) is not ExecutionStatus.passed
            for dependency in step.depends_on
        ):
            steps.append(
                _step(context, step.id, step.kind.value, step.target, _skipped())
            )
            completed[step.id] = ExecutionStatus.inconclusive
            continue
        if step.kind is StepKind.api_suite:
            suite = suite_by_target[step.target]
            if cancel is not None and cancel.is_set():
                run = _cancelled(suite, workspace)
            else:
                run = run_registered_suite(
                    suite,
                    workspace,
                    binary=binaries[suite.runner],
                    run_directory=run_root / context.execution_id / suite.id,
                    environment=context.environment,
                    timeout_seconds=context.timeout_seconds,
                    secret_values=_bindings(suite, secret_values),
                    cancel=cancel,
                )
            api_runs.append(run)
            steps.append(
                _step(
                    context,
                    step.id,
                    step.kind.value,
                    step.target,
                    CheckResult(
                        assertion_id=step.target,
                        kind=step.kind.value,
                        status=run.normalized.status,
                        executed=True,
                        verified=run.normalized.status is ExecutionStatus.passed,
                        reason=run.normalized.status.value,
                    ),
                )
            )
            completed[step.id] = run.normalized.status
            continue
        assertion = assertions.get(step.target)
        if assertion is None:
            result = _missing(step.target, step.kind.value)
        elif step.kind in {StepKind.database_assertion, StepKind.business_assertion}:
            result = (
                evaluate_invariant(assertion, observations)
                if step.kind is StepKind.business_assertion
                else run_database_assertion(
                    assertion,
                    correlation,
                    reader=database_reader,
                    approved_connections=approved_connections,
                    cancel=None if cancel is None else cancel.is_set,
                )
            )
        else:
            result = run_kafka_assertion(
                assertion,
                correlation,
                reader=kafka_reader,
                approved_connections=approved_connections,
            )
        if step.kind is not StepKind.business_assertion:
            prefix = "kafka" if step.kind is StepKind.kafka_assertion else "database"
            for key, value in result.observations:
                observations[
                    f"{prefix}.{assertion.id if assertion else step.target}.{key}"
                ] = value
        steps.append(_step(context, step.id, step.kind.value, step.target, result))
        completed[step.id] = result.status
    return _e2e_record(context, api_runs, steps, clock)


def queued_record(context: ExecutionContext, clock: datetime) -> ExecutionRecord:
    """Persist a queued run before a background job starts."""
    evidence = ApiOnlyEvidence(
        execution_id=context.execution_id,
        profile_id=context.profile_id,
        workflow_id=context.workflow_id,
        suite_ids=context.suite_ids,
        suite_version=context.suite_version,
        source_revision=context.source_revision,
        assertion_total=0,
        assertion_failed=0,
        status=ExecutionStatus.queued,
        runner_exit_code=None,
        runner_completed=False,
    )
    return ExecutionRecord(
        execution_id=context.execution_id,
        profile_id=context.profile_id,
        workflow_id=context.workflow_id,
        suite_ids=context.suite_ids,
        suite_version=context.suite_version,
        source_revision=context.source_revision,
        status=ExecutionStatus.queued,
        assertion_status=ExecutionStatus.inconclusive,
        runner_completed=False,
        runner_exit_code=None,
        transitions=(ExecutionStatus.queued.value,),
        queued_at=clock,
        started_at=None,
        finished_at=None,
        evidence=evidence,
    )


def _bindings(suite: SuiteDefinition, values: dict[str, str]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for binding in suite.credential_env:
        if binding.reference in values:
            selected[binding.name] = values[binding.reference]
    return selected


def _cancelled(suite: SuiteDefinition, workspace: Path) -> SuiteRun:
    from qa_mcp_hub.suites.models import ResolvedSuite

    resolved = ResolvedSuite(
        suite=suite,
        collection_path=str(workspace / suite.path),
        working_directory=str(workspace / suite.path),
        source_revision=None,
        argv=("cancelled",),
    )
    normalized = NormalizedResult(
        status=ExecutionStatus.cancelled,
        assertion_status=ExecutionStatus.inconclusive,
        runner_completed=False,
        exit_code=None,
        assertion_total=0,
        assertion_failed=0,
    )
    return SuiteRun(resolved, normalized, "")


def _combine(runs: list[SuiteRun]) -> NormalizedResult:
    if not runs:
        return NormalizedResult(
            status=ExecutionStatus.error,
            assertion_status=ExecutionStatus.inconclusive,
            runner_completed=False,
            exit_code=None,
            assertion_total=0,
            assertion_failed=0,
        )
    status = max(
        (item.normalized.status for item in runs),
        key=lambda item: _RANK[item],
    )
    assertion = max(
        (item.normalized.assertion_status for item in runs),
        key=lambda item: _RANK[item],
    )
    return NormalizedResult(
        status=status,
        assertion_status=assertion,
        runner_completed=all(item.normalized.runner_completed for item in runs),
        exit_code=runs[-1].normalized.exit_code,
        assertion_total=sum(item.normalized.assertion_total for item in runs),
        assertion_failed=sum(item.normalized.assertion_failed for item in runs),
        warnings=tuple(
            warning for item in runs for warning in item.normalized.warnings
        ),
    )


def _path(final: ExecutionStatus, *, process_started: bool) -> tuple[str, ...]:
    current = ExecutionStatus.queued
    observed = [current.value]
    current = transition(current, ExecutionStatus.running)
    observed.append(current.value)
    if final in {ExecutionStatus.timed_out, ExecutionStatus.cancelled} or (
        final is ExecutionStatus.error and not process_started
    ):
        current = transition(current, final)
        observed.append(current.value)
        return tuple(observed)
    current = transition(current, ExecutionStatus.verifying)
    observed.append(current.value)
    current = transition(current, final)
    observed.append(current.value)
    return tuple(observed)


def _e2e_record(
    context: ExecutionContext,
    api_runs: list[SuiteRun],
    steps: list[StepEvidence],
    clock: datetime,
) -> ExecutionRecord:
    """Combine API and verification steps without promoting an unrun check."""
    warnings: list[str] = []
    if api_runs:
        combined = _combine(api_runs)
        runner_completed = combined.runner_completed
        exit_code = combined.exit_code
        assertion_total = combined.assertion_total
        assertion_failed = combined.assertion_failed
        revision = next(
            (
                item.resolved.source_revision
                for item in api_runs
                if item.resolved.source_revision
            ),
            context.source_revision,
        )
        excerpt = api_runs[-1].excerpt
        warnings.extend(combined.warnings)
        process_started = api_runs[-1].resolved.argv != ("missing",)
        if api_runs[-1].normalized.status in {
            ExecutionStatus.cancelled,
            ExecutionStatus.timed_out,
        }:
            process_started = False
    else:
        runner_completed = False
        exit_code = None
        assertion_total = 0
        assertion_failed = 0
        revision = context.source_revision
        excerpt = ""
        process_started = False
    verification = [item for item in steps if item.kind != StepKind.api_suite.value]
    executed_verification = [item for item in verification if item.executed]
    assertion_total += len(executed_verification)
    assertion_failed += sum(
        item.status is ExecutionStatus.failed for item in executed_verification
    )
    executed_statuses = [item.status for item in steps if item.executed]
    final = (
        max(executed_statuses, key=lambda item: _RANK[item])
        if executed_statuses
        else ExecutionStatus.blocked
    )
    if any(not item.executed for item in steps) and final is ExecutionStatus.passed:
        final = ExecutionStatus.blocked
    names: list[str] = []
    if any(item.kind == StepKind.api_suite.value and item.executed for item in steps):
        names.append("api")
    if any(
        item.kind == StepKind.database_assertion.value and item.executed
        for item in steps
    ):
        names.append("database")
    if any(
        item.kind == StepKind.kafka_assertion.value and item.executed for item in steps
    ):
        names.append("kafka")
    if any(
        item.kind == StepKind.business_assertion.value and item.executed
        for item in steps
    ):
        names.append("business")
    database_steps = [
        item
        for item in steps
        if item.kind == StepKind.database_assertion.value and item.executed
    ]
    kafka_steps = [
        item
        for item in steps
        if item.kind == StepKind.kafka_assertion.value and item.executed
    ]
    if any(item.verified for item in kafka_steps):
        warnings.append("consumer_completion_not_observed")
    evidence = ApiOnlyEvidence(
        kind="e2e",
        execution_id=context.execution_id,
        profile_id=context.profile_id,
        workflow_id=context.workflow_id,
        suite_ids=context.suite_ids,
        suite_version=context.suite_version,
        source_revision=revision,
        checks=tuple(names),  # type: ignore[arg-type]
        database_verified=bool(database_steps)
        and all(item.verified for item in database_steps),
        kafka_verified=bool(kafka_steps) and all(item.verified for item in kafka_steps),
        assertion_total=assertion_total,
        assertion_failed=assertion_failed,
        status=final,
        runner_exit_code=exit_code,
        runner_completed=runner_completed,
    )
    return ExecutionRecord(
        execution_id=context.execution_id,
        profile_id=context.profile_id,
        workflow_id=context.workflow_id,
        suite_ids=context.suite_ids,
        suite_version=context.suite_version,
        source_revision=revision,
        status=final,
        assertion_status=final,
        runner_completed=runner_completed,
        runner_exit_code=exit_code,
        transitions=_path(final, process_started=process_started),
        queued_at=clock,
        started_at=clock,
        finished_at=clock,
        evidence=evidence,
        excerpt=excerpt or (steps[-1].reason if steps else ""),
        warnings=tuple(dict.fromkeys(warnings)),
        step_results=tuple(steps),
    )


def _step(
    context: ExecutionContext,
    step_id: str,
    kind: str,
    target: str,
    result: CheckResult,
) -> StepEvidence:
    return StepEvidence(
        step_id=step_id,
        kind=kind,
        target=target,
        status=result.status,
        executed=result.executed,
        verified=result.verified,
        reason=result.reason,
        evidence_ref=f"{context.execution_id}/{step_id}",
    )


def _skipped() -> CheckResult:
    return CheckResult(
        assertion_id="skipped",
        kind="skipped",
        status=ExecutionStatus.inconclusive,
        executed=False,
        verified=False,
        reason="skipped_after_dependency_failure",
    )


def _missing(target: str, kind: str) -> CheckResult:
    return CheckResult(
        assertion_id=target,
        kind=kind,
        status=ExecutionStatus.blocked,
        executed=False,
        verified=False,
        reason="assertion_not_registered",
    )
