"""Workspace-scoped lookup of workflow documents.

Purpose: list files discovered in the approved workflow directories.
Milestone: 06
Status: IMPLEMENTED
Ownership: workflows.registry
Dependencies: Workflow discovery.
Expected tests: duplicate ids and deterministic listing.
"""

from pathlib import Path

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.workflows.discovery import discover_workflows
from qa_mcp_hub.workflows.models import WorkflowDefinition


def load_workflows(workspace: Path) -> tuple[WorkflowDefinition, ...]:
    """Load every workflow file. Duplicate ids fail the registry."""
    return discover_workflows(workspace)


def workflow_by_id(
    workflows: tuple[WorkflowDefinition, ...], workflow_id: str
) -> WorkflowDefinition:
    """Return one workflow or reject an unknown id."""
    for workflow in workflows:
        if workflow.id == workflow_id:
            return workflow
    raise HubError("unknown_workflow", f"workflow is not registered: {workflow_id}")
