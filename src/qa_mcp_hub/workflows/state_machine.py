"""Scaffold for workflow run-state transitions.

Purpose: Reserve explicit legal transitions for planned and executing workflows.
Owning Milestone: 06
Status: SCAFFOLDED
Ownership: workflows.state_machine
Dependencies: Workflow models, normalized results, audit, and execution storage.
Expected tests: Legal transitions, terminal immutability, recovery, and concurrency.
"""
