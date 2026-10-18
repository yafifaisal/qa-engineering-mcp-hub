"""Scaffold for the approved-suite registry.

Purpose: Reserve workspace-scoped lookup of explicitly registered executable suites.
Owning Milestone: 06
Status: SCAFFOLDED
Ownership: suites.registry
Dependencies: Suite models, workspace loader, validator, and authorization context.
Expected tests: Duplicate IDs, deterministic listing, scope isolation, and reloads.
"""
