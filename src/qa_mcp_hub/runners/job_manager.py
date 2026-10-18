"""Scaffold for bounded execution-job management.

Purpose: Reserve lifecycle, cancellation, concurrency, and lookup of approved jobs.
Owning Milestone: 06
Status: SCAFFOLDED
Ownership: runners.job_manager
Dependencies: Execution context, suite runner, polling, storage, and audit contracts.
Expected tests: Concurrency caps, cancellation races, ownership, expiry, and recovery.
"""
