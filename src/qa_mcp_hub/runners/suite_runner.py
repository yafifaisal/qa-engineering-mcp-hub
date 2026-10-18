"""Run one immutable suite plan and normalize its reporter.

Purpose: capture exit, assertions, and artifacts for a registered suite.
Milestone: 06
Status: IMPLEMENTED
Ownership: runners.suite_runner
Dependencies: Suite resolver, process runner, and result normalization.
Expected tests: plan fidelity, exit handling, and redaction.
"""

import json
import stat
import threading
from dataclasses import dataclass
from pathlib import Path

from qa_mcp_hub.auth.redaction import redact_text
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.runners.process_runner import ProcessRequest, run_process
from qa_mcp_hub.runners.result_normalizer import NormalizedResult, normalize
from qa_mcp_hub.runners.result_parser import parse_report
from qa_mcp_hub.security.process_policy import sanitized_env
from qa_mcp_hub.suites.models import ResolvedSuite, SuiteDefinition
from qa_mcp_hub.suites.resolver import resolve_suite


@dataclass(frozen=True)
class SuiteRun:
    """Normalized facts for one suite. The env file is not retained."""

    resolved: ResolvedSuite
    normalized: NormalizedResult
    excerpt: str


def run_registered_suite(
    suite: SuiteDefinition,
    workspace: Path,
    *,
    binary: Path,
    run_directory: Path,
    environment: str | None,
    timeout_seconds: int,
    secret_values: dict[str, str],
    cancel: threading.Event | None = None,
) -> SuiteRun:
    """Execute the fixed argv for one suite and delete the temporary env file."""
    run_directory.mkdir(parents=True, exist_ok=True)
    report_path = run_directory / "report.json"
    env_file = run_directory / "runner-env.json" if secret_values else None
    if env_file is not None:
        _write_env(env_file, suite.runner, secret_values)
    try:
        return _run_resolved(
            suite,
            workspace,
            binary=binary,
            report_path=report_path,
            env_file=env_file,
            environment=environment,
            timeout_seconds=timeout_seconds,
            secret_values=secret_values,
            cancel=cancel,
        )
    finally:
        if env_file is not None:
            env_file.unlink(missing_ok=True)
        report_path.unlink(missing_ok=True)


def _run_resolved(
    suite: SuiteDefinition,
    workspace: Path,
    *,
    binary: Path,
    report_path: Path,
    env_file: Path | None,
    environment: str | None,
    timeout_seconds: int,
    secret_values: dict[str, str],
    cancel: threading.Event | None,
) -> SuiteRun:
    try:
        resolved = resolve_suite(
            suite,
            workspace,
            binary=binary,
            report_path=report_path,
            env_file=env_file,
            environment=environment,
        )
    except HubError as exc:
        if exc.code != "runner_missing":
            raise
        return SuiteRun(
            _missing(suite, workspace, report_path),
            normalize(
                exit_code=None,
                timed_out=False,
                cancelled=False,
                runner_missing=True,
                parsed=None,
            ),
            "",
        )
    completed = run_process(
        ProcessRequest(
            argv=resolved.argv,
            cwd=resolved.working_directory,
            env=sanitized_env(secret_values),
            timeout_seconds=timeout_seconds,
            secrets=tuple(secret_values.values()),
        ),
        cancel,
    )
    parsed = None
    if report_path.is_file() and not completed.cancelled and not completed.timed_out:
        text = redact_text(
            report_path.read_text(encoding="utf-8"),
            secrets=tuple(secret_values.values()),
        )
        parsed = parse_report(suite.runner, text)
    if completed.truncated:
        parsed = None
    normalized = normalize(
        exit_code=completed.exit_code,
        timed_out=completed.timed_out,
        cancelled=completed.cancelled,
        runner_missing=False,
        parsed=parsed,
    )
    excerpt = redact_text(
        completed.stdout or completed.stderr,
        secrets=tuple(secret_values.values()),
    )
    return SuiteRun(resolved, normalized, excerpt)


def _write_env(path: Path, runner: str, values: dict[str, str]) -> None:
    if runner == "bruno":
        payload: dict[str, object] = {
            "name": "run",
            "variables": [
                {"name": key, "value": value, "enabled": True}
                for key, value in values.items()
            ],
        }
    else:
        payload = {
            "name": "run",
            "values": [
                {"key": key, "value": value, "enabled": True}
                for key, value in values.items()
            ],
        }
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _missing(
    suite: SuiteDefinition, workspace: Path, report_path: Path
) -> ResolvedSuite:
    del report_path
    return ResolvedSuite(
        suite=suite,
        collection_path=str(workspace / suite.path),
        working_directory=str(workspace / suite.path),
        source_revision=None,
        argv=("missing",),
    )
