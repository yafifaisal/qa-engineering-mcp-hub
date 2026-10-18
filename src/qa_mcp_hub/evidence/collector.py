"""Collect evidence from checks that actually ran.

Purpose: copy executed step facts and omit unrun database or Kafka claims.
Milestone: 10
Status: IMPLEMENTED
Ownership: evidence.collector
Dependencies: Execution records, policies, and redaction.
Expected tests: API-only exclusion, partial runs, and crash recovery.
"""

from qa_mcp_hub.evidence.completeness import overall_status
from qa_mcp_hub.evidence.models import (
    EvidenceCheck,
    EvidenceCheckStatus,
    EvidencePolicy,
)
from qa_mcp_hub.evidence.redactor import redact_evidence
from qa_mcp_hub.workflows.models import ExecutionRecord, ExecutionStatus, StepEvidence

_KIND = {
    "api_suite": "api",
    "database_assertion": "database",
    "kafka_assertion": "kafka",
    "business_assertion": "business",
}
_STATUS = {
    ExecutionStatus.passed: EvidenceCheckStatus.passed,
    ExecutionStatus.failed: EvidenceCheckStatus.failed,
    ExecutionStatus.blocked: EvidenceCheckStatus.blocked,
    ExecutionStatus.inconclusive: EvidenceCheckStatus.inconclusive,
}
_INCOMPLETE = {
    ExecutionStatus.error,
    ExecutionStatus.timed_out,
    ExecutionStatus.cancelled,
}


def collect_checks(
    record: ExecutionRecord,
    policy: EvidencePolicy,
    *,
    ci_references: tuple[str, ...] = (),
    recovered: bool = False,
) -> tuple[tuple[EvidenceCheck, ...], str, tuple[str, ...], EvidenceCheckStatus]:
    """Build checks, a sanitized excerpt, limitations, and the overall status."""
    allowed = set(policy.required_checks) | set(policy.optional_checks)
    grouped: dict[str, list[StepEvidence]] = {}
    limitations: list[str] = []
    for step in record.step_results:
        name = _KIND.get(step.kind)
        if name is None:
            continue
        if name not in allowed:
            limitations.append(f"{name} was not collected for this policy")
            continue
        if not step.executed:
            continue
        grouped.setdefault(name, []).append(step)
    checks = [_from_steps(name, steps) for name, steps in sorted(grouped.items())]
    excerpt, residual = redact_evidence(
        record.excerpt,
        strict=policy.redaction.profile == "strict",
    )
    if "api" not in grouped or policy.redaction.profile == "strict":
        excerpt = ""
    redaction = _redaction_check(residual, policy)
    checks.append(redaction)
    if ci_references:
        checks.append(
            EvidenceCheck(
                name="cicd",
                result=EvidenceCheckStatus.inconclusive,
                executed=True,
                evidence_reference="ci_observation",
                detail="pipeline status is not a QA result",
            )
        )
        limitations.append("a pipeline status was referenced and is not a QA result")
    else:
        limitations.append("no CI reference was stored for this execution")
    if recovered or record.status in _INCOMPLETE or not record.runner_completed:
        limitations.append("execution did not finish cleanly")
    status = overall_status(policy, tuple(checks))
    if recovered or record.status in _INCOMPLETE or not record.runner_completed:
        if status is EvidenceCheckStatus.passed:
            status = EvidenceCheckStatus.blocked
    return tuple(checks), excerpt, tuple(limitations), status


def _from_steps(
    name: str, steps: tuple[StepEvidence, ...] | list[StepEvidence]
) -> EvidenceCheck:
    chosen = min(steps, key=lambda item: _rank(item))
    result = _STATUS.get(chosen.status, EvidenceCheckStatus.blocked)
    return EvidenceCheck(
        name=name,
        result=result,
        executed=True,
        evidence_reference=chosen.evidence_ref or chosen.step_id,
        detail=chosen.reason,
    )


def _rank(step: StepEvidence) -> int:
    result = _STATUS.get(step.status, EvidenceCheckStatus.blocked)
    return {
        EvidenceCheckStatus.failed: 0,
        EvidenceCheckStatus.blocked: 1,
        EvidenceCheckStatus.inconclusive: 2,
        EvidenceCheckStatus.passed: 3,
    }.get(result, 1)


def _redaction_check(residual: bool, policy: EvidencePolicy) -> EvidenceCheck:
    failed = residual and policy.redaction.block_on_secret_detection
    result = EvidenceCheckStatus.failed if failed else EvidenceCheckStatus.passed
    detail = "residual_secret" if failed else "sanitized"
    return EvidenceCheck(
        name="security_redaction",
        result=result,
        executed=True,
        evidence_reference="redactor",
        detail=detail,
    )
