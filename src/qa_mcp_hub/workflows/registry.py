"""Scaffold for the approved-workflow registry.

Purpose: Reserve workspace-scoped lookup of explicitly registered workflows.
Owning Milestone: 06
Status: SCAFFOLDED
Ownership: workflows.registry
Dependencies: Workflow models, discovery, validator, and workspace configuration.
Expected tests: Duplicate IDs, deterministic listing, scope isolation, and reloads.
"""
