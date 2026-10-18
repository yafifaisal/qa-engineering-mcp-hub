"""Typed provider ports. Concrete adapters are not supplied here.

Purpose: define the Git, ticket, documentation, API, database, streaming,
CI/CD, and test-management operations a future adapter must satisfy.
Milestone: 02
Status: IMPLEMENTED
Ownership: Provider-neutral protocol definitions and capability boundaries.
Dependencies: Standard-library typing and canonical provider models.
Expected tests: protocol conformance suites using deterministic test doubles.
"""

from typing import Protocol, runtime_checkable

from qa_mcp_hub.core.context import ExecutionContext
from qa_mcp_hub.core.results import Pagination, ToolResult


@runtime_checkable
class GitProvider(Protocol):
    """Read-oriented Git port. Remote hosting APIs are not implemented."""

    def read_repository(self, context: ExecutionContext) -> ToolResult:
        """Read one repository description for the bound connection."""

    def list_changes(self, context: ExecutionContext, page: Pagination) -> ToolResult:
        """List one page of changes for the bound connection."""


@runtime_checkable
class TicketProvider(Protocol):
    """Read-oriented ticket port."""

    def read_issue(self, context: ExecutionContext) -> ToolResult:
        """Read one issue for the bound connection."""


@runtime_checkable
class DocumentationProvider(Protocol):
    """Read-oriented documentation port."""

    def read_document(self, context: ExecutionContext) -> ToolResult:
        """Read one document for the bound connection."""


@runtime_checkable
class ApiAutomationProvider(Protocol):
    """Read-oriented API-automation port."""

    def list_requests(self, context: ExecutionContext, page: Pagination) -> ToolResult:
        """List one page of stored requests for the bound connection."""


@runtime_checkable
class DatabaseProvider(Protocol):
    """Read-oriented database port. It does not expose SQL execution."""

    def read_schema(self, context: ExecutionContext) -> ToolResult:
        """Read schema metadata for the bound connection."""


@runtime_checkable
class StreamingProvider(Protocol):
    """Read-oriented streaming port. It does not start a consumer."""

    def read_consumer_lag(self, context: ExecutionContext) -> ToolResult:
        """Read consumer-lag metadata for the bound connection."""


@runtime_checkable
class CicdProvider(Protocol):
    """Read-oriented CI/CD port."""

    def read_pipeline(self, context: ExecutionContext) -> ToolResult:
        """Read one pipeline description for the bound connection."""


@runtime_checkable
class TestManagementProvider(Protocol):
    """Read-oriented test-management port."""

    def read_case(self, context: ExecutionContext) -> ToolResult:
        """Read one test case for the bound connection."""
