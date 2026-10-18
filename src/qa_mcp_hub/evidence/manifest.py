"""Scaffold for immutable evidence manifests.

Purpose: Reserve stable inventories, hashes, provenance, and completeness metadata.
Owning Milestone: 10
Status: SCAFFOLDED
Ownership: evidence.manifest
Dependencies: Evidence models, artifact store, collector, redactor, and clocks.
Expected tests: Deterministic ordering, hash changes, missing files, and round trips.
"""
