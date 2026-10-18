"""Provider contract namespace.

Purpose: export catalog lookup and protocol types without vendor adapters.
Milestone: 02
Status: IMPLEMENTED
Ownership: Provider package namespace and public-contract curation.
Dependencies: Pydantic and standard-library typing only when implemented.
Expected tests: package import and public-surface tests.
"""

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
from qa_mcp_hub.providers.registry import (
    ProviderRegistry,
    ServiceContainer,
    discover_capabilities,
)

__all__ = [
    "ApiAutomationProvider",
    "CicdProvider",
    "DatabaseProvider",
    "DocumentationProvider",
    "GitProvider",
    "ProviderRegistry",
    "ServiceContainer",
    "StreamingProvider",
    "TestManagementProvider",
    "TicketProvider",
    "discover_capabilities",
]
