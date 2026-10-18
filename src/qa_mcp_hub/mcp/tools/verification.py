"""MCP tools for registered database, Kafka, and E2E checks.

Purpose: expose registry ids without accepting SQL text or a shell command.
Milestone: 07
Status: IMPLEMENTED
Ownership: mcp.tools.verification
Dependencies: Verification service and workflow submission.
Expected tests: discovery, assertion allowlists, and blocked infrastructure.
"""

from qa_mcp_hub.verification.models import AssertionSummary, CheckResult
from qa_mcp_hub.verification.service import (
    approved_connections,
    check_database,
    check_kafka,
    list_assertion_summaries,
    load_profile_config,
    workspace_for,
)
from qa_mcp_hub.workflows.models import RunReceipt
from qa_mcp_hub.workflows.service import submit_test_run


def list_registered_assertions_tool(
    profile: str | None = None,
) -> tuple[AssertionSummary, ...]:
    """List registered assertions. SQL text is not returned."""
    config = load_profile_config()
    _profile_id, workspace = workspace_for(config, profile)
    return list_assertion_summaries(workspace)


def run_database_assertion_tool(
    assertion_id: str,
    parameters: dict[str, str] | None = None,
    profile: str | None = None,
) -> CheckResult:
    """Run one registered database assertion.

    The tool does not accept a SQL string, a connection URI, or a secret.
    """
    config = load_profile_config()
    profile_id, workspace = workspace_for(config, profile)
    return check_database(
        workspace,
        assertion_id,
        parameters or {},
        approved_connections(config, profile_id),
    )


def find_kafka_event_tool(
    assertion_id: str,
    correlation: dict[str, str] | None = None,
    profile: str | None = None,
) -> CheckResult:
    """Find one event for a registered Kafka assertion.

    The tool does not commit consumer offsets or scan an undeclared topic.
    """
    config = load_profile_config()
    profile_id, workspace = workspace_for(config, profile)
    return check_kafka(
        workspace,
        assertion_id,
        correlation or {},
        approved_connections(config, profile_id),
    )


def verify_e2e_workflow_tool(
    workflow_id: str,
    correlation: dict[str, str] | None = None,
    execute: bool = False,
    profile: str | None = None,
) -> RunReceipt:
    """Preview or run one registered workflow, including its verification steps.

    A preview does not mark database or Kafka checks as verified.
    """
    return submit_test_run(
        workflow_id=workflow_id,
        execute=execute,
        profile=profile,
        correlation=correlation,
    )
