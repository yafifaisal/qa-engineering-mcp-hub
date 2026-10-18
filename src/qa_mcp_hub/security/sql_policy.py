"""Scaffold for registered read-only SQL policy.

Purpose: Reserve parsed SELECT-only enforcement, binding, row caps, and deadlines.
Owning Milestone: 07
Status: SCAFFOLDED
Ownership: security.sql_policy
Dependencies: Registered assertions, database contracts, and operation context.
Expected tests: Multi-statement rejection, CTEs, binding, limits, and dialects.
"""
