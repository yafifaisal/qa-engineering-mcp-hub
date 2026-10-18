"""Scaffold for normalized Git metadata inspection.

Purpose: Reserve read-only remotes, revisions, branches, and worktree state.
Owning Milestone: 03
Status: SCAFFOLDED
Ownership: repositories.git_metadata
Dependencies: Repository models, bounded process policy, and source references.
Expected tests: Detached heads, multiple remotes, dirty state, timeouts, and redaction.
"""
