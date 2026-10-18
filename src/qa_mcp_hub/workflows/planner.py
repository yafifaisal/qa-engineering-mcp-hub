"""Scaffold for immutable workflow run planning.

Purpose: Reserve dependency-ordered plans before any process or provider action.
Owning Milestone: 06
Status: SCAFFOLDED
Ownership: workflows.planner
Dependencies: Workflow models, suite resolver, dependencies, policy, and approvals.
Expected tests: Ordering, cycle rejection, previews, approval needs, and stable plans.
"""
