"""Cancellable polling with a deadline and an attempt cap.

Purpose: bound waits for a process or a persisted run.
Milestone: 06
Status: IMPLEMENTED
Ownership: runners.polling
Dependencies: Clocks and cancellation events.
Expected tests: deadlines, cancellation, and attempt caps.
"""

import threading
import time
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from qa_mcp_hub.core.errors import HubError


class PollOutcome(BaseModel):
    """Why a bounded poll stopped."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    completed: bool
    attempts: int
    reason: str


def poll_until(
    ready: Callable[[], bool],
    *,
    timeout_seconds: float,
    interval_seconds: float,
    max_attempts: int,
    cancel: threading.Event | None = None,
) -> PollOutcome:
    """Call a predicate until it is true, the deadline passes, or it is cancelled."""
    if timeout_seconds <= 0 or timeout_seconds > 60:
        raise HubError(
            "poll_bounds", "polling timeout must be between 0 and 60 seconds"
        )
    if interval_seconds <= 0 or max_attempts < 1 or max_attempts > 100:
        raise HubError("poll_bounds", "polling attempts are outside the allowed range")
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    while attempts < max_attempts:
        if cancel is not None and cancel.is_set():
            return PollOutcome(completed=False, attempts=attempts, reason="cancelled")
        attempts += 1
        if ready():
            return PollOutcome(completed=True, attempts=attempts, reason="completed")
        if time.monotonic() >= deadline:
            return PollOutcome(completed=False, attempts=attempts, reason="deadline")
        time.sleep(min(interval_seconds, max(0.0, deadline - time.monotonic())))
    return PollOutcome(completed=False, attempts=attempts, reason="max_attempts")
