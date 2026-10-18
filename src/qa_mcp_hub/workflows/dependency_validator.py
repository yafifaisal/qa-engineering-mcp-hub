"""Checks for missing, cyclic, and unavailable workflow steps.

Purpose: reject graphs that cannot be ordered or that cite missing assertions.
Milestone: 06
Status: IMPLEMENTED
Ownership: workflows.dependency_validator
Dependencies: Workflow and suite identities.
Expected tests: cycles, duplicate ids, and missing assertions.
"""

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.suites.models import SuiteDefinition
from qa_mcp_hub.workflows.models import StepKind, WorkflowDefinition

_UNAVAILABLE = {
    StepKind.database_assertion,
    StepKind.kafka_assertion,
    StepKind.business_assertion,
}


def validate_workflow(
    workflow: WorkflowDefinition, suites: dict[str, SuiteDefinition]
) -> tuple[str, ...]:
    """Return unavailable-step reasons. Structural errors are raised."""
    seen: set[str] = set()
    for step in workflow.steps:
        if step.id in seen:
            raise HubError("duplicate_step", f"duplicate step id: {step.id}")
        seen.add(step.id)
    known = {step.id for step in workflow.steps}
    graph = {step.id: step.depends_on for step in workflow.steps}
    for step in workflow.steps:
        for dependency in step.depends_on:
            if dependency not in known:
                raise HubError(
                    "unresolved_dependency",
                    f"step {step.id} depends on unknown step {dependency}",
                )
        if step.kind is StepKind.api_suite:
            suite = suites.get(step.target)
            if suite is None:
                raise HubError(
                    "unknown_suite",
                    f"workflow cites unknown suite {step.target}",
                )
            for assertion_id in step.assertion_ids:
                if assertion_id not in suite.assertion_ids:
                    raise HubError(
                        "missing_assertion",
                        f"assertion {assertion_id} is not declared by suite {suite.id}",
                    )
    _reject_cycles(graph)
    reasons: list[str] = []
    for step in workflow.steps:
        if step.kind in _UNAVAILABLE:
            reasons.append(f"{step.id}:unavailable_until_milestone_07")
    return tuple(reasons)


def _reject_cycles(graph: dict[str, tuple[str, ...]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(step_id: str) -> None:
        if step_id in visited:
            return
        if step_id in visiting:
            raise HubError("workflow_cycle", "workflow steps contain a cycle")
        visiting.add(step_id)
        for dependency in graph.get(step_id, ()):
            walk(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in graph:
        walk(step_id)
