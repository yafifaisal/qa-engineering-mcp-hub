"""Deterministic comparison of registered observation paths.

Purpose: evaluate a business invariant from executed observations only.
Milestone: 07
Status: IMPLEMENTED
Ownership: verification.invariant_engine
Dependencies: Check observations and execution status.
Expected tests: match, mismatch, and missing inputs.
"""

from qa_mcp_hub.verification.models import AssertionDefinition, CheckResult
from qa_mcp_hub.workflows.models import ExecutionStatus


def evaluate_invariant(
    assertion: AssertionDefinition,
    observations: dict[str, str],
) -> CheckResult:
    """Compare two declared paths. Missing inputs do not pass."""
    left_key = assertion.definition.get("left")
    right_key = assertion.definition.get("right")
    if not isinstance(left_key, str) or not isinstance(right_key, str):
        return CheckResult(
            assertion_id=assertion.id,
            kind=assertion.kind,
            status=ExecutionStatus.blocked,
            executed=False,
            verified=False,
            reason="invariant_incomplete",
        )
    left = observations.get(left_key)
    right = observations.get(right_key)
    if left is None or right is None:
        return CheckResult(
            assertion_id=assertion.id,
            kind=assertion.kind,
            status=ExecutionStatus.inconclusive,
            executed=True,
            verified=False,
            reason="invariant_input_missing",
        )
    if left != right:
        return CheckResult(
            assertion_id=assertion.id,
            kind=assertion.kind,
            status=ExecutionStatus.failed,
            executed=True,
            verified=False,
            reason="invariant_mismatch",
            observations=(("left", left), ("right", right)),
        )
    return CheckResult(
        assertion_id=assertion.id,
        kind=assertion.kind,
        status=ExecutionStatus.passed,
        executed=True,
        verified=True,
        reason="invariant_holds",
        observations=(("left", left), ("right", right)),
    )
