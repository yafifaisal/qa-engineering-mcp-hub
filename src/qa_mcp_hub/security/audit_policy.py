"""Scaffold for security audit policy.

Purpose: Reserve required events, fields, retention, and redaction for risky actions.
Owning Milestone: 02
Status: SCAFFOLDED
Ownership: security.audit_policy
Dependencies: Core audit, context, approvals, credential redaction, and storage.
Expected tests: Event coverage, required fields, ordering, retention, and no secrets.
"""
