"""Translation of a process result and a reporter into one status.

Purpose: keep runner success separate from assertion success.
Milestone: 06
Status: IMPLEMENTED
Ownership: runners.result_normalizer
Dependencies: Parsed reports and execution status.
Expected tests: status mapping and the PASS invariant.
"""

from qa_mcp_hub.runners.result_parser import ParsedReport
from qa_mcp_hub.workflows.models import ExecutionStatus


class NormalizedResult:
    """Facts from one process. PASS is withheld without assertion names."""

    def __init__(
        self,
        *,
        status: ExecutionStatus,
        assertion_status: ExecutionStatus,
        runner_completed: bool,
        exit_code: int | None,
        assertion_total: int,
        assertion_failed: int,
        warnings: tuple[str, ...] = (),
    ) -> None:
        self.status = status
        self.assertion_status = assertion_status
        self.runner_completed = runner_completed
        self.exit_code = exit_code
        self.assertion_total = assertion_total
        self.assertion_failed = assertion_failed
        self.warnings = warnings


def normalize(
    *,
    exit_code: int | None,
    timed_out: bool,
    cancelled: bool,
    runner_missing: bool,
    parsed: ParsedReport | None,
) -> NormalizedResult:
    """Map process and reporter facts onto the canonical statuses."""
    if cancelled:
        return _plain(ExecutionStatus.cancelled, exit_code, runner_completed=False)
    if timed_out:
        return _plain(ExecutionStatus.timed_out, exit_code, runner_completed=False)
    if runner_missing or parsed is None or not parsed.valid:
        return _plain(ExecutionStatus.error, exit_code, runner_completed=False)
    failed = sum(0 if item.passed else 1 for item in parsed.assertions)
    total = len(parsed.assertions)
    runner_completed = exit_code == 0
    warnings: tuple[str, ...] = ()
    if parsed.reason is not None:
        warnings = (parsed.reason,)
    if total == 0:
        return NormalizedResult(
            status=ExecutionStatus.inconclusive,
            assertion_status=ExecutionStatus.inconclusive,
            runner_completed=runner_completed,
            exit_code=exit_code,
            assertion_total=0,
            assertion_failed=0,
            warnings=warnings or ("no_assertions",),
        )
    if failed:
        return NormalizedResult(
            status=ExecutionStatus.failed,
            assertion_status=ExecutionStatus.failed,
            runner_completed=runner_completed,
            exit_code=exit_code,
            assertion_total=total,
            assertion_failed=failed,
            warnings=warnings,
        )
    if not runner_completed:
        return NormalizedResult(
            status=ExecutionStatus.error,
            assertion_status=ExecutionStatus.passed,
            runner_completed=False,
            exit_code=exit_code,
            assertion_total=total,
            assertion_failed=0,
            warnings=warnings + ("runner_exit_nonzero",),
        )
    return NormalizedResult(
        status=ExecutionStatus.passed,
        assertion_status=ExecutionStatus.passed,
        runner_completed=True,
        exit_code=exit_code,
        assertion_total=total,
        assertion_failed=0,
        warnings=warnings,
    )


def _plain(
    status: ExecutionStatus, exit_code: int | None, *, runner_completed: bool
) -> NormalizedResult:
    return NormalizedResult(
        status=status,
        assertion_status=ExecutionStatus.inconclusive,
        runner_completed=runner_completed,
        exit_code=exit_code,
        assertion_total=0,
        assertion_failed=0,
    )
