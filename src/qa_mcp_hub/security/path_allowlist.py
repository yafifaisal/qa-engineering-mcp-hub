"""Scaffold for filesystem path allowlisting.

Purpose: Reserve canonicalization and containment checks before filesystem access.
Owning Milestone: 03
Status: SCAFFOLDED
Ownership: security.path_allowlist
Dependencies: Repository registry, workspace configuration, and native path rules.
Expected tests: Traversal, symlinks, case rules, UNC paths, and missing roots.
"""
