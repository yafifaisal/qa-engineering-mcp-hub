"""Canonical provider catalog, capability discovery, and adapter binding.

Purpose: resolve a profile connection to a contract stub without calling a vendor.
Milestone: 02
Status: IMPLEMENTED
Ownership: Provider identifier allowlist, capability metadata, and adapter
factory routing.
Dependencies: Provider contracts and models; future connection and credential
resolvers.
Expected tests: unknown-provider rejection, connection isolation, capability,
and factory-routing tests.
"""

from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from qa_mcp_hub.config.models import ConnectionConfig, HubConfig
from qa_mcp_hub.core.context import ExecutionContext
from qa_mcp_hub.core.enums import OperationStatus, ProviderCategory
from qa_mcp_hub.core.errors import (
    CatalogMismatchError,
    ProviderResolutionError,
    UnknownProviderError,
    UnsupportedCapabilityError,
)
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.core.results import Pagination, ToolResult
from qa_mcp_hub.providers.contracts import (
    ApiAutomationProvider,
    CicdProvider,
    DatabaseProvider,
    DocumentationProvider,
    GitProvider,
    StreamingProvider,
    TestManagementProvider,
    TicketProvider,
)
from qa_mcp_hub.providers.models import (
    ConnectionIdentity,
    ProviderCapability,
    ProviderDescriptor,
)

CATEGORY_CAPABILITIES: dict[ProviderCategory, tuple[str, ...]] = {
    ProviderCategory.git: (
        "read_repository",
        "list_changes",
        "search_code",
        "compare_changes",
    ),
    ProviderCategory.tickets: ("read_issue",),
    ProviderCategory.documentation: ("read_document",),
    ProviderCategory.api_automation: ("list_requests",),
    ProviderCategory.database: ("read_schema",),
    ProviderCategory.streaming: ("read_consumer_lag",),
    ProviderCategory.cicd: ("read_pipeline",),
    ProviderCategory.test_management: ("read_case",),
}

_OFFLINE = "OFFLINE_VERIFIED"

CATALOG: tuple[ProviderDescriptor, ...] = (
    ProviderDescriptor(
        id=ProviderKind.github,
        category=ProviderCategory.git,
        implementation_status=_OFFLINE,
    ),
    ProviderDescriptor(
        id=ProviderKind.gitlab,
        category=ProviderCategory.git,
        implementation_status=_OFFLINE,
    ),
    ProviderDescriptor(
        id=ProviderKind.bitbucket,
        category=ProviderCategory.git,
        variants=("cloud", "self_managed"),
        implementation_status=_OFFLINE,
    ),
    ProviderDescriptor(
        id=ProviderKind.jira,
        category=ProviderCategory.tickets,
        variants=("cloud", "self_managed"),
        implementation_status=_OFFLINE,
    ),
    ProviderDescriptor(
        id=ProviderKind.confluence,
        category=ProviderCategory.documentation,
        variants=("cloud", "self_managed"),
    ),
    ProviderDescriptor(
        id=ProviderKind.google_docs,
        category=ProviderCategory.documentation,
    ),
    ProviderDescriptor(id=ProviderKind.bruno, category=ProviderCategory.api_automation),
    ProviderDescriptor(
        id=ProviderKind.postman,
        category=ProviderCategory.api_automation,
    ),
    ProviderDescriptor(id=ProviderKind.postgresql, category=ProviderCategory.database),
    ProviderDescriptor(id=ProviderKind.mysql, category=ProviderCategory.database),
    ProviderDescriptor(id=ProviderKind.kafka, category=ProviderCategory.streaming),
    ProviderDescriptor(
        id=ProviderKind.bitbucket_pipelines,
        category=ProviderCategory.cicd,
    ),
    ProviderDescriptor(id=ProviderKind.github_actions, category=ProviderCategory.cicd),
    ProviderDescriptor(
        id=ProviderKind.jenkins,
        category=ProviderCategory.cicd,
        variants=("self_managed",),
    ),
    ProviderDescriptor(
        id=ProviderKind.xray,
        category=ProviderCategory.test_management,
        variants=("cloud", "self_managed"),
    ),
    ProviderDescriptor(
        id=ProviderKind.testrail,
        category=ProviderCategory.test_management,
    ),
    ProviderDescriptor(
        id=ProviderKind.spreadsheet,
        category=ProviderCategory.test_management,
        formats=("csv", "xlsx"),
    ),
    ProviderDescriptor(
        id=ProviderKind.google_sheets,
        category=ProviderCategory.test_management,
    ),
)

_BY_ID: dict[ProviderKind, ProviderDescriptor] = {item.id: item for item in CATALOG}
_READ_PROVIDERS = {
    ProviderKind.github,
    ProviderKind.gitlab,
    ProviderKind.bitbucket,
    ProviderKind.jira,
}
_EXPOSED_CAPABILITIES = {"search_code", "compare_changes", "read_issue"}


class BoundProvider(BaseModel):
    """A connection-scoped stub. The adapter object is not serialized."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    identity: ConnectionIdentity
    context: ExecutionContext
    category: ProviderCategory
    adapter: object


class _Unavailable:
    def __init__(self, provider: ProviderKind, category: ProviderCategory) -> None:
        self.provider = provider
        self.category = category

    def _unavailable(self, capability: str) -> ToolResult:
        known = capability in CATEGORY_CAPABILITIES[self.category]
        raise UnsupportedCapabilityError(
            self.provider.value,
            capability,
            implemented=known,
        )


class GitContractStub(_Unavailable):
    """Git port that reports every operation as not implemented."""

    def read_repository(self, context: ExecutionContext) -> ToolResult:
        return self._unavailable("read_repository")

    def list_changes(self, context: ExecutionContext, page: Pagination) -> ToolResult:
        del context, page
        return self._unavailable("list_changes")


class TicketContractStub(_Unavailable):
    """Ticket port that reports every operation as not implemented."""

    def read_issue(self, context: ExecutionContext) -> ToolResult:
        return self._unavailable("read_issue")


class DocumentationContractStub(_Unavailable):
    """Documentation port that reports every operation as not implemented."""

    def read_document(self, context: ExecutionContext) -> ToolResult:
        return self._unavailable("read_document")


class ApiAutomationContractStub(_Unavailable):
    """API-automation port that reports every operation as not implemented."""

    def list_requests(self, context: ExecutionContext, page: Pagination) -> ToolResult:
        del context, page
        return self._unavailable("list_requests")


class DatabaseContractStub(_Unavailable):
    """Database port that reports every operation as not implemented."""

    def read_schema(self, context: ExecutionContext) -> ToolResult:
        return self._unavailable("read_schema")


class StreamingContractStub(_Unavailable):
    """Streaming port that reports every operation as not implemented."""

    def read_consumer_lag(self, context: ExecutionContext) -> ToolResult:
        return self._unavailable("read_consumer_lag")


class CicdContractStub(_Unavailable):
    """CI/CD port that reports every operation as not implemented."""

    def read_pipeline(self, context: ExecutionContext) -> ToolResult:
        return self._unavailable("read_pipeline")


class TestManagementContractStub(_Unavailable):
    """Test-management port that reports every operation as not implemented."""

    def read_case(self, context: ExecutionContext) -> ToolResult:
        return self._unavailable("read_case")


def ensure_catalog() -> None:
    """Reject a catalog that drifted from the ProviderKind allowlist."""
    if {item.id for item in CATALOG} != set(ProviderKind):
        raise CatalogMismatchError("provider catalog does not match ProviderKind")
    for item in CATALOG:
        expected = (
            "OFFLINE_VERIFIED" if item.id in _READ_PROVIDERS else "NOT_IMPLEMENTED"
        )
        if item.implementation_status != expected:
            raise CatalogMismatchError("catalog implementation status is inconsistent")


def catalog_matches_document(document: dict[str, Any]) -> None:
    """Compare the in-code catalog with config/supported_providers.yaml."""
    ensure_catalog()
    rows = document.get("providers")
    if not isinstance(rows, list) or len(rows) != len(CATALOG):
        raise CatalogMismatchError("supported provider document has the wrong shape")
    for descriptor, row in zip(CATALOG, rows, strict=True):
        if not isinstance(row, dict):
            raise CatalogMismatchError("supported provider row is invalid")
        if row.get("id") != descriptor.id.value:
            raise CatalogMismatchError("provider id order does not match the catalog")
        if row.get("category") != descriptor.category.value:
            raise CatalogMismatchError(f"category mismatch for {descriptor.id.value}")
        if tuple(row.get("variants", ())) != descriptor.variants:
            raise CatalogMismatchError(f"variant mismatch for {descriptor.id.value}")
        if tuple(row.get("formats", ())) != descriptor.formats:
            raise CatalogMismatchError(f"format mismatch for {descriptor.id.value}")
        if row.get("implementation_status") != descriptor.implementation_status:
            raise CatalogMismatchError(
                f"implementation status mismatch for {descriptor.id.value}"
            )


def discover_capabilities(provider_id: str) -> tuple[ProviderCapability, ...]:
    """List contract capabilities. Only read tools that exist are exposed."""
    descriptor = require_descriptor(provider_id)
    readable = descriptor.id in _READ_PROVIDERS
    return tuple(
        ProviderCapability(
            provider=descriptor.id,
            name=name,
            status=(
                OperationStatus.available
                if readable
                else OperationStatus.not_implemented
            ),
            exposed_as_mcp_tool=readable and name in _EXPOSED_CAPABILITIES,
        )
        for name in CATEGORY_CAPABILITIES[descriptor.category]
    )


def require_descriptor(provider_id: str) -> ProviderDescriptor:
    """Return the catalog entry or reject an unknown identifier."""
    ensure_catalog()
    try:
        kind = ProviderKind(provider_id)
    except ValueError as exc:
        raise UnknownProviderError(provider_id) from exc
    return _BY_ID[kind]


def open_read_adapter(
    connection: ConnectionConfig, secret: object, http_client: object
) -> object:
    """Open a read-only GitHub, GitLab, Bitbucket, or Jira adapter."""
    import httpx
    from pydantic import SecretStr

    from qa_mcp_hub.adapters.git.bitbucket import open_bitbucket
    from qa_mcp_hub.adapters.git.github import open_github
    from qa_mcp_hub.adapters.git.gitlab import open_gitlab
    from qa_mcp_hub.adapters.tickets.jira import open_jira

    if not isinstance(secret, SecretStr) or not isinstance(http_client, httpx.Client):
        raise ProviderResolutionError("read adapter requires a secret and HTTP client")
    kind = connection.provider
    if kind is ProviderKind.github:
        return open_github(
            base_url=connection.base_url,
            deployment=connection.deployment,
            secret=secret,
            http_client=http_client,
        )
    if kind is ProviderKind.gitlab:
        return open_gitlab(
            base_url=connection.base_url,
            deployment=connection.deployment,
            secret=secret,
            http_client=http_client,
        )
    if kind is ProviderKind.bitbucket:
        return open_bitbucket(
            base_url=connection.base_url,
            deployment=connection.deployment,
            account=connection.account,
            auth_kind=connection.auth_kind,
            secret=secret,
            http_client=http_client,
        )
    if kind is ProviderKind.jira:
        return open_jira(
            base_url=connection.base_url,
            deployment=connection.deployment,
            account=connection.account,
            auth_kind=connection.auth_kind,
            secret=secret,
            http_client=http_client,
        )
    raise UnsupportedCapabilityError(kind.value, "read", implemented=False)


def build_stub(provider: ProviderKind) -> object:
    """Return the category stub for one provider. The stub performs no I/O."""
    descriptor = _BY_ID[provider]
    category = descriptor.category
    if category is ProviderCategory.git:
        return GitContractStub(provider, category)
    if category is ProviderCategory.tickets:
        return TicketContractStub(provider, category)
    if category is ProviderCategory.documentation:
        return DocumentationContractStub(provider, category)
    if category is ProviderCategory.api_automation:
        return ApiAutomationContractStub(provider, category)
    if category is ProviderCategory.database:
        return DatabaseContractStub(provider, category)
    if category is ProviderCategory.streaming:
        return StreamingContractStub(provider, category)
    if category is ProviderCategory.cicd:
        return CicdContractStub(provider, category)
    return TestManagementContractStub(provider, category)


class ProviderRegistry:
    """Resolve catalog entries and profile-scoped connection bindings."""

    def __init__(self) -> None:
        ensure_catalog()

    def descriptor(self, provider_id: str) -> ProviderDescriptor:
        return require_descriptor(provider_id)

    def capabilities(self, provider_id: str) -> tuple[ProviderCapability, ...]:
        return discover_capabilities(provider_id)

    def bind(self, config: HubConfig, context: ExecutionContext) -> BoundProvider:
        """Bind one profile connection to its contract stub."""
        if context.connection_id is None:
            raise ProviderResolutionError("a connection is required")
        profile = config.profiles.get(context.profile_id)
        if profile is None:
            raise ProviderResolutionError("profile does not exist")
        if context.connection_id not in profile.connection_ids:
            raise ProviderResolutionError("connection is not in this profile")
        connection = _connection(config, context.connection_id)
        if connection is None:
            raise ProviderResolutionError("connection does not exist")
        descriptor = self.descriptor(connection.provider.value)
        identity = ConnectionIdentity(
            profile_id=context.profile_id,
            connection_id=connection.id,
            provider=connection.provider,
            account=connection.account,
            environment=context.environment,
        )
        return BoundProvider(
            identity=identity,
            context=context,
            category=descriptor.category,
            adapter=build_stub(connection.provider),
        )


class ServiceContainer:
    """Injects protocol-typed ports so callers never construct a vendor client."""

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self._registry = registry or ProviderRegistry()

    def bind(self, config: HubConfig, context: ExecutionContext) -> BoundProvider:
        return self._registry.bind(config, context)

    def git_provider(self, config: HubConfig, context: ExecutionContext) -> GitProvider:
        bound = self.bind(config, context)
        if bound.category is not ProviderCategory.git or not isinstance(
            bound.adapter, GitProvider
        ):
            raise UnsupportedCapabilityError(
                bound.identity.provider.value,
                "read_repository",
                implemented=False,
            )
        return bound.adapter

    def ticket_provider(
        self, config: HubConfig, context: ExecutionContext
    ) -> TicketProvider:
        return cast(
            TicketProvider,
            _require(
                self.bind(config, context),
                ProviderCategory.tickets,
                TicketProvider,
            ),
        )

    def documentation_provider(
        self, config: HubConfig, context: ExecutionContext
    ) -> DocumentationProvider:
        return cast(
            DocumentationProvider,
            _require(
                self.bind(config, context),
                ProviderCategory.documentation,
                DocumentationProvider,
            ),
        )

    def api_automation_provider(
        self, config: HubConfig, context: ExecutionContext
    ) -> ApiAutomationProvider:
        return cast(
            ApiAutomationProvider,
            _require(
                self.bind(config, context),
                ProviderCategory.api_automation,
                ApiAutomationProvider,
            ),
        )

    def database_provider(
        self, config: HubConfig, context: ExecutionContext
    ) -> DatabaseProvider:
        return cast(
            DatabaseProvider,
            _require(
                self.bind(config, context),
                ProviderCategory.database,
                DatabaseProvider,
            ),
        )

    def streaming_provider(
        self, config: HubConfig, context: ExecutionContext
    ) -> StreamingProvider:
        return cast(
            StreamingProvider,
            _require(
                self.bind(config, context),
                ProviderCategory.streaming,
                StreamingProvider,
            ),
        )

    def cicd_provider(
        self, config: HubConfig, context: ExecutionContext
    ) -> CicdProvider:
        return cast(
            CicdProvider,
            _require(self.bind(config, context), ProviderCategory.cicd, CicdProvider),
        )

    def test_management_provider(
        self, config: HubConfig, context: ExecutionContext
    ) -> TestManagementProvider:
        return cast(
            TestManagementProvider,
            _require(
                self.bind(config, context),
                ProviderCategory.test_management,
                TestManagementProvider,
            ),
        )


def connection_context(
    connection: ConnectionConfig,
    *,
    profile_id: str,
    source_revision: str | None = None,
) -> ExecutionContext:
    """Snapshot deployment and connection identity before any later config edit."""
    return ExecutionContext.create(
        profile_id=profile_id,
        connection_id=connection.id,
        environment=connection.deployment.value,
        source_revision=source_revision,
    )


def _connection(config: HubConfig, connection_id: str) -> ConnectionConfig | None:
    return next((item for item in config.connections if item.id == connection_id), None)


def _require(bound: BoundProvider, category: ProviderCategory, port: Any) -> object:
    if bound.category is not category or not isinstance(bound.adapter, port):
        raise UnsupportedCapabilityError(
            bound.identity.provider.value,
            CATEGORY_CAPABILITIES[category][0],
            implemented=False,
        )
    return bound.adapter
