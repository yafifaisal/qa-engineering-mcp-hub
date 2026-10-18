"""Milestone 02 provider-contract and registry tests.

Remote provider methods are stubs. A passing test here is not provider connectivity.
"""

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from qa_mcp_hub.config.models import (
    ConnectionConfig,
    DeploymentKind,
    HubConfig,
    ProfileConfig,
)
from qa_mcp_hub.core.context import ExecutionContext
from qa_mcp_hub.core.enums import OperationStatus, ProviderCategory
from qa_mcp_hub.core.errors import UnknownProviderError, UnsupportedCapabilityError
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.core.results import result_from_error
from qa_mcp_hub.core.retry import RetryableError, RetryPolicy, decide_retry
from qa_mcp_hub.providers.contracts import GitProvider, TicketProvider
from qa_mcp_hub.providers.registry import (
    CATALOG,
    ProviderRegistry,
    ServiceContainer,
    build_stub,
    catalog_matches_document,
    connection_context,
    discover_capabilities,
)

ROOT = Path(__file__).resolve().parents[2]


def _config() -> HubConfig:
    return HubConfig(
        schema_version=1,
        active_profile="alpha",
        profiles={
            "alpha": ProfileConfig(
                connection_ids=("github-a", "github-b", "jira-a"),
            ),
            "beta": ProfileConfig(connection_ids=("gitlab-b",)),
        },
        connections=(
            ConnectionConfig(
                id="github-a",
                provider=ProviderKind.github,
                deployment=DeploymentKind.CLOUD,
                base_url="https://api.github.com",
                account="alpha-user",
            ),
            ConnectionConfig(
                id="github-b",
                provider=ProviderKind.github,
                deployment=DeploymentKind.SELF_MANAGED,
                base_url="https://github.example.invalid",
                account="alpha-second",
            ),
            ConnectionConfig(
                id="jira-a",
                provider=ProviderKind.jira,
                deployment=DeploymentKind.CLOUD,
                base_url="https://example.atlassian.net",
            ),
            ConnectionConfig(
                id="gitlab-b",
                provider=ProviderKind.gitlab,
                deployment=DeploymentKind.CLOUD,
                base_url="https://gitlab.example.invalid",
            ),
        ),
    )


def test_catalog_matches_architecture_document() -> None:
    document = yaml.safe_load((ROOT / "config/supported_providers.yaml").read_text())
    catalog_matches_document(document)
    assert {item.id for item in CATALOG} == set(ProviderKind)
    offline = {
        "github",
        "gitlab",
        "bitbucket",
        "jira",
        "confluence",
        "google_docs",
        "bruno",
        "postman",
    }
    assert {
        item.id.value
        for item in CATALOG
        if item.implementation_status == "OFFLINE_VERIFIED"
    } == offline
    assert all(
        item.implementation_status == "NOT_IMPLEMENTED"
        for item in CATALOG
        if item.id.value not in offline
    )
    assert len(CATALOG) == 18


def test_capability_discovery_does_not_advertise_tools() -> None:
    capabilities = discover_capabilities("github")
    assert [item.name for item in capabilities] == [
        "read_repository",
        "list_changes",
        "search_code",
        "compare_changes",
    ]
    assert all(item.status is OperationStatus.available for item in capabilities)
    exposed = {item.name for item in capabilities if item.exposed_as_mcp_tool}
    assert exposed == {"search_code", "compare_changes"}
    assert "hub_health" not in {item.name for item in capabilities}
    confluence = discover_capabilities("confluence")
    assert all(item.status is OperationStatus.available for item in confluence)
    assert {item.name for item in confluence if item.exposed_as_mcp_tool} == {
        "read_document",
        "search_documents",
    }
    postman = discover_capabilities("postman")
    assert all(item.status is OperationStatus.not_implemented for item in postman)
    assert all(item.exposed_as_mcp_tool is False for item in postman)


def test_unknown_provider_and_capability_are_typed_errors() -> None:
    with pytest.raises(UnknownProviderError):
        discover_capabilities("azure-devops")
    stub = build_stub(ProviderKind.github)
    context = ExecutionContext.create(
        profile_id="alpha",
        connection_id="github-a",
        environment="cloud",
    )
    with pytest.raises(UnsupportedCapabilityError) as caught:
        stub.read_repository(context)  # type: ignore[attr-defined]
    assert caught.value.status is OperationStatus.not_implemented
    mapped = result_from_error(caught.value)
    assert mapped.status is not OperationStatus.success


def test_category_stubs_are_not_interchangeable() -> None:
    git_stub = build_stub(ProviderKind.gitlab)
    ticket_stub = build_stub(ProviderKind.jira)
    assert isinstance(git_stub, GitProvider)
    assert not isinstance(git_stub, TicketProvider)
    assert isinstance(ticket_stub, TicketProvider)
    assert not isinstance(ticket_stub, GitProvider)


def test_multiple_instances_stay_profile_scoped() -> None:
    config = _config()
    registry = ProviderRegistry()
    first = connection_context(config.connections[0], profile_id="alpha")
    second = connection_context(config.connections[1], profile_id="alpha")
    bound_a = registry.bind(config, first)
    bound_b = registry.bind(config, second)
    assert bound_a.identity.connection_id == "github-a"
    assert bound_b.identity.connection_id == "github-b"
    assert bound_a.identity.environment == "cloud"
    assert bound_b.identity.environment == "self_managed"
    assert bound_a.adapter is not bound_b.adapter
    foreign = first.model_copy(update={"profile_id": "beta"})
    with pytest.raises(Exception, match="not in this profile"):
        registry.bind(config, foreign)


def test_injected_port_rejects_the_wrong_category() -> None:
    config = _config()
    services = ServiceContainer()
    context = connection_context(config.connections[2], profile_id="alpha")
    with pytest.raises(UnsupportedCapabilityError):
        services.git_provider(config, context)
    ticket = services.ticket_provider(config, context)
    assert ticket.category is ProviderCategory.tickets  # type: ignore[attr-defined]


def test_execution_context_is_immutable() -> None:
    context = ExecutionContext.create(
        profile_id="alpha",
        connection_id="github-a",
        environment="cloud",
        source_revision="abc123",
    )
    with pytest.raises(ValidationError):
        context.profile_id = "beta"  # type: ignore[misc]


def test_retry_contract_allows_only_safe_retryable_failures() -> None:
    policy = RetryPolicy()
    assert policy.retry_safe_operations_only is True
    refused = decide_retry(
        policy,
        attempt=1,
        operation_is_safe=False,
        error=RetryableError(),
    )
    assert refused.should_retry is False
    assert refused.reason == "unsafe_operation"
    allowed = decide_retry(
        policy,
        attempt=1,
        operation_is_safe=True,
        error=RetryableError(),
    )
    assert allowed.should_retry is True
    assert allowed.delay_seconds == pytest.approx(0.2)
    capped = decide_retry(
        policy,
        attempt=3,
        operation_is_safe=True,
        error=RetryableError(),
    )
    assert capped.reason == "attempt_cap"
    plain = decide_retry(
        policy,
        attempt=1,
        operation_is_safe=True,
        error=RuntimeError("no"),
    )
    assert plain.reason == "not_retryable"
    disabled = decide_retry(
        policy.model_copy(update={"retry_safe_operations_only": False}),
        attempt=1,
        operation_is_safe=True,
        error=RetryableError(),
    )
    assert disabled.reason == "unsafe_operation"
