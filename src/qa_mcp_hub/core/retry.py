"""Bounded retry decisions for operations that are safe to repeat.

Purpose: decide whether another attempt is allowed without performing it.
Milestone: 02
Status: IMPLEMENTED
Ownership: core.retry
Dependencies: Core errors, operation context, and provider rate-limit metadata.
Expected tests: attempt caps, backoff, classification, cancellation, and idempotency.
"""

from pydantic import BaseModel, ConfigDict, Field

from qa_mcp_hub.core.errors import HubError


class RetryableError(HubError):
    """A transient failure of an operation the caller has marked safe."""

    def __init__(self, message: str = "temporary failure of a safe operation") -> None:
        super().__init__("retryable", message)


class RetryPolicy(BaseModel):
    """Caps and backoff for safe retries. Unsafe work is never retried."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(default=3, ge=1, le=5)
    initial_backoff_seconds: float = Field(default=0.2, gt=0, le=5)
    max_backoff_seconds: float = Field(default=2.0, gt=0, le=30)
    retry_safe_operations_only: bool = True


class RetryDecision(BaseModel):
    """The planner's answer. It does not sleep and does not call a provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    should_retry: bool
    delay_seconds: float = Field(ge=0)
    reason: str


def decide_retry(
    policy: RetryPolicy,
    *,
    attempt: int,
    operation_is_safe: bool,
    error: Exception,
) -> RetryDecision:
    """Return whether a completed attempt may be repeated."""
    if not operation_is_safe or not policy.retry_safe_operations_only:
        return RetryDecision(
            should_retry=False,
            delay_seconds=0,
            reason="unsafe_operation",
        )
    if not isinstance(error, RetryableError):
        return RetryDecision(
            should_retry=False, delay_seconds=0, reason="not_retryable"
        )
    if attempt >= policy.max_attempts:
        return RetryDecision(should_retry=False, delay_seconds=0, reason="attempt_cap")
    delay = min(
        policy.max_backoff_seconds,
        policy.initial_backoff_seconds * (2 ** (attempt - 1)),
    )
    return RetryDecision(should_retry=True, delay_seconds=delay, reason="safe_retry")
