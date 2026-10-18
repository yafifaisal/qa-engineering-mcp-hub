"""Service protocols that keep callers independent of concrete providers.

Purpose: describe injected framework services without importing an adapter.
Milestone: 02
Status: IMPLEMENTED
Ownership: core.contracts
Dependencies: Core models, results, and context contracts.
Expected tests: structural conformance, dependency direction, and import cycles.
"""

from typing import Protocol

from qa_mcp_hub.core.context import ExecutionContext
from qa_mcp_hub.core.retry import RetryDecision, RetryPolicy


class RetryPlanner(Protocol):
    """Plans a retry. Implementations must not perform the operation."""

    def decide(
        self,
        policy: RetryPolicy,
        *,
        attempt: int,
        operation_is_safe: bool,
        error: Exception,
    ) -> RetryDecision:
        """Return a retry decision for one completed attempt."""


class ExecutionScope(Protocol):
    """Supplies the immutable context for the current operation."""

    def context(self) -> ExecutionContext:
        """Return the frozen profile, connection, environment, and revision."""
