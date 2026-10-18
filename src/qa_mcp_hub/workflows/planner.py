"""Build an immutable preview before any suite process starts.

Purpose: show order, argv, and unavailable steps.
Milestone: 06
Status: IMPLEMENTED
Ownership: workflows.planner
Dependencies: Dependency validation and runner argument builders.
Expected tests: ordering, cycles, and previews.
"""

from pathlib import Path

from qa_mcp_hub.adapters.api_automation.bruno import bruno_arguments
from qa_mcp_hub.adapters.api_automation.postman import newman_arguments
from qa_mcp_hub.suites.models import SuiteDefinition
from qa_mcp_hub.workflows.dependency_validator import validate_workflow
from qa_mcp_hub.workflows.models import (
    PlannedStep,
    StepKind,
    WorkflowDefinition,
    WorkflowExplanation,
)


def explain_definition(
    workflow: WorkflowDefinition,
    suites: dict[str, SuiteDefinition],
    *,
    report_path: Path,
    environment: str | None,
) -> WorkflowExplanation:
    """Return a preview. This function does not start a process."""
    reasons = validate_workflow(workflow, suites)
    unavailable = {item.split(":", 1)[0] for item in reasons}
    order = _order(workflow)
    steps: list[PlannedStep] = []
    for step_id in order:
        step = next(item for item in workflow.steps if item.id == step_id)
        if step.id in unavailable or step.kind is not StepKind.api_suite:
            steps.append(
                PlannedStep(
                    id=step.id,
                    kind=step.kind,
                    target=step.target,
                    available=False,
                    reason="unavailable_until_milestone_07",
                )
            )
            continue
        suite = suites[step.target]
        selected = environment if environment is not None else suite.environment
        steps.append(
            PlannedStep(
                id=step.id,
                kind=step.kind,
                target=step.target,
                available=True,
                reason="registered_api_suite",
                argv=_preview_argv(suite, report_path, selected),
            )
        )
    api_only = bool(steps) and all(step.available for step in steps)
    blocked = None
    if not api_only:
        blocked = "non_api_step_unavailable"
    if not workflow.approved:
        blocked = "workflow_not_approved"
    if not workflow.enabled:
        blocked = "workflow_disabled"
    return WorkflowExplanation(
        workflow_id=workflow.id,
        name=workflow.name,
        approved=workflow.approved,
        enabled=workflow.enabled,
        api_only=api_only,
        steps=tuple(steps),
        blocked_reason=blocked,
    )


def _preview_argv(
    suite: SuiteDefinition, report_path: Path, environment: str | None
) -> tuple[str, ...]:
    if suite.runner == "bruno":
        tail = bruno_arguments(
            report_path=report_path,
            environment=environment,
            env_file=None,
        )
        return ("bru", *tail)
    collection = Path(suite.path)
    tail = newman_arguments(
        collection_path=collection,
        report_path=report_path,
        env_file=None,
    )
    return ("newman", *tail)


def _order(workflow: WorkflowDefinition) -> tuple[str, ...]:
    pending = {step.id: set(step.depends_on) for step in workflow.steps}
    ordered: list[str] = []
    while pending:
        ready = sorted(step_id for step_id, deps in pending.items() if not deps)
        if not ready:
            break
        chosen = ready[0]
        ordered.append(chosen)
        del pending[chosen]
        for deps in pending.values():
            deps.discard(chosen)
    return tuple(ordered)
