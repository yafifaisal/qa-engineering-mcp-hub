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

from qa_mcp_hub.runners.execution_context import ExecutionContext
from qa_mcp_hub.runners.result_normalizer import NormalizedResult
from qa_mcp_hub.runners.suite_runner import SuiteRun, run_registered_suite
from qa_mcp_hub.suites.models import SuiteDefinition
from qa_mcp_hub.workflows.models import (
    ApiOnlyEvidence,
    ExecutionRecord,
    ExecutionStatus,
)
from qa_mcp_hub.workflows.state_machine import transition

_RANK = {
    ExecutionStatus.passed: 0,
    ExecutionStatus.inconclusive: 1,
    ExecutionStatus.failed: 2,
    ExecutionStatus.cancelled: 3,
    ExecutionStatus.timed_out: 4,
    ExecutionStatus.error: 5,
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
