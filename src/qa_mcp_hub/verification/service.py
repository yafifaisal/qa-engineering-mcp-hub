"""Registered verification entry points for MCP tools.

Purpose: list assertions and run one database or Kafka check from the registry.
Milestone: 07
Status: IMPLEMENTED
Ownership: verification.service
Dependencies: Assertion registry, database checks, and Kafka checks.
Expected tests: missing assertions, blocked infrastructure, and redacted results.
"""

from pathlib import Path

from qa_mcp_hub.adapters.database.base import DatabaseReader
from qa_mcp_hub.adapters.streaming.kafka import TopicReader
from qa_mcp_hub.config.loader import load_config
from qa_mcp_hub.config.models import HubConfig
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.verification.assertion_registry import executable, load_assertions
from qa_mcp_hub.verification.database_assertions import run_database_assertion
from qa_mcp_hub.verification.kafka_assertions import run_kafka_assertion
from qa_mcp_hub.verification.models import (
    AssertionSummary,
    CheckResult,
    summary_for,
)
from qa_mcp_hub.verification.runtime import current_database, current_kafka


def list_assertion_summaries(
    workspace: Path,
) -> tuple[AssertionSummary, ...]:
    """List registered assertions without their SQL text."""
    assertions = load_assertions(workspace)
    return tuple(summary_for(item) for item in assertions.values())


def check_database(
    workspace: Path,
    assertion_id: str,
    parameters: dict[str, str],
    approved_connections: dict[str, str],
    *,
    reader: DatabaseReader | None = None,
) -> CheckResult:
    """Run one registered database assertion for the supplied reader."""
    assertion = executable(load_assertions(workspace), assertion_id)
    return run_database_assertion(
        assertion,
        parameters,
        reader=current_database() if reader is None else reader,
        approved_connections=approved_connections,
    )


def check_kafka(
    workspace: Path,
    assertion_id: str,
    parameters: dict[str, str],
    approved_connections: dict[str, str],
    *,
    reader: TopicReader | None = None,
) -> CheckResult:
    """Run one registered Kafka assertion for the supplied observer."""
    assertion = executable(load_assertions(workspace), assertion_id)
    return run_kafka_assertion(
        assertion,
        parameters,
        reader=current_kafka() if reader is None else reader,
        approved_connections=approved_connections,
    )


def approved_connections(config: HubConfig, profile_id: str) -> dict[str, str]:
    """Map connection ids owned by the profile to their provider names."""
    profile = config.profiles[profile_id]
    allowed = set(profile.connection_ids)
    return {
        item.id: item.provider.value
        for item in config.connections
        if item.id in allowed and item.enabled
    }


def workspace_for(config: HubConfig, profile: str | None) -> tuple[str, Path]:
    """Resolve the active profile workspace without reading a secret."""
    selected = profile or config.active_profile
    if selected is None or selected not in config.profiles:
        raise HubError("profile_required", "an active profile is required")
    item = config.profiles[selected]
    if item.workspace_id is None:
        raise HubError("workspace_required", "profile has no QA workspace")
    for workspace in config.workspaces:
        if workspace.id == item.workspace_id:
            return selected, Path(workspace.path)
    raise HubError("workspace_required", "workspace reference is missing")


def load_profile_config() -> HubConfig:
    """Load the local hub configuration."""
    return load_config()
