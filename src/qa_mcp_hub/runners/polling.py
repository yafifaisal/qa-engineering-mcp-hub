"""Scaffold for bounded asynchronous polling.

Purpose: Reserve cancellable polling with explicit deadlines and attempt limits.
Owning Milestone: 06
Status: SCAFFOLDED
Ownership: runners.polling
Dependencies: Core retry policy, operation context, clocks, and normalized errors.
Expected tests: Deadlines, backoff, cancellation, terminal states, and attempt caps.
"""
