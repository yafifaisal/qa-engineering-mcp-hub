"""Concurrency limit for approved suite runs.

Purpose: cap overlapping runs and keep each context private.
Milestone: 06
Status: IMPLEMENTED
Ownership: runners.job_manager
Dependencies: Execution context.
Expected tests: concurrency caps and immutable contexts.
"""

import threading
from collections.abc import Callable

from qa_mcp_hub.runners.execution_context import ExecutionContext


class JobManager:
    """Run approved jobs without exceeding the profile concurrency limit."""

    def __init__(self, max_concurrency: int) -> None:
        self._slots = threading.BoundedSemaphore(max_concurrency)
        self._lock = threading.Lock()
        self._cancels: dict[str, threading.Event] = {}
        self._threads: list[threading.Thread] = []
        self.peak = 0
        self._active = 0

    def register(self, execution_id: str) -> threading.Event:
        """Create the cancellation event before a run starts."""
        event = threading.Event()
        with self._lock:
            self._cancels[execution_id] = event
        return event

    def cancel(self, execution_id: str) -> bool:
        """Signal a running job. A missing id is not a running job."""
        with self._lock:
            event = self._cancels.get(execution_id)
        if event is None:
            return False
        event.set()
        return True

    def run(
        self,
        context: ExecutionContext,
        action: Callable[[ExecutionContext, threading.Event], None],
        *,
        wait: bool,
    ) -> None:
        """Run an action with a slot. The context object is not copied again."""
        event = self._cancels[context.execution_id]

        def worker() -> None:
            self._slots.acquire()
            with self._lock:
                self._active += 1
                self.peak = max(self.peak, self._active)
            try:
                action(context, event)
            finally:
                with self._lock:
                    self._active -= 1
                self._slots.release()

        if wait:
            worker()
            return
        thread = threading.Thread(target=worker, daemon=False)
        self._threads.append(thread)
        thread.start()

    def join(self, timeout: float) -> None:
        """Wait for background jobs started by this manager."""
        for thread in self._threads:
            thread.join(timeout=timeout)
