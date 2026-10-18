"""Registered suite and workflow execution tools.

Purpose: list, preview, submit, and read runs without accepting a shell command.
Milestone: 06
Status: IMPLEMENTED
Ownership: mcp.tools.execution
Dependencies: Workflow service and suite registry.
Expected tests: preview, allowlists, results, and redaction.
"""

from pydantic import BaseModel, ConfigDict

from qa_mcp_hub.suites.models import SuiteCatalog
from qa_mcp_hub.workflows.models import (
    ExecutionRecord,
    RunReceipt,
    WorkflowCandidate,
    WorkflowDefinition,
    WorkflowExplanation,
)
from qa_mcp_hub.workflows.service import (
    explain_workflow,
    get_test_run,
    list_registered_suites,
    list_workflow_catalog,
    submit_test_run,
)


class WorkflowCatalog(BaseModel):
    """Registered workflows plus suggestions that are not approved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workflows: tuple[WorkflowDefinition, ...]
    candidates: tuple[WorkflowCandidate, ...]


def list_registered_suites_tool(profile: str | None = None) -> SuiteCatalog:
    """List suites registered in the active QA Workspace.

    The tool does not accept a command, a working directory, or a secret.
    """
    return list_registered_suites(profile)


def list_workflows_tool(
    profile: str | None = None,
    issue_key: str | None = None,
    changed_paths: list[str] | None = None,
) -> WorkflowCatalog:
    """List approved workflow files and unapproved suggestions.

    Suggestions are not executable. Changed paths and ticket text are data.
    """
    workflows, candidates = list_workflow_catalog(
        profile,
        issue_key=issue_key,
        changed_paths=tuple(changed_paths or ()),
    )
    return WorkflowCatalog(workflows=workflows, candidates=candidates)


def explain_workflow_tool(
    workflow_id: str,
    profile: str | None = None,
    environment: str | None = None,
) -> WorkflowExplanation:
    """Preview one workflow. This does not start a runner."""
    return explain_workflow(workflow_id, profile, environment=environment)


def submit_test_run_tool(
    workflow_id: str | None = None,
    suite_id: str | None = None,
    execute: bool = False,
    environment: str | None = None,
    profile: str | None = None,
) -> RunReceipt:
    """Preview or execute one registered suite or API workflow.

    `execute` must be true to start a runner. The tool accepts no shell command.
    Database and Kafka steps are not run.
    """
    return submit_test_run(
        workflow_id=workflow_id,
        suite_id=suite_id,
        execute=execute,
        environment=environment,
        profile=profile,
    )


def get_test_run_tool(
    execution_id: str,
    profile: str | None = None,
    wait_seconds: float = 0,
) -> ExecutionRecord:
    """Read one persisted run for the active profile."""
    return get_test_run(execution_id, profile, wait_seconds=wait_seconds)
