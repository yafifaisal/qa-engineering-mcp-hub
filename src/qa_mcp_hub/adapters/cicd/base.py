"""CI/CD adapter base scaffold.

Purpose: Reserve normalized pipeline run, step, log, and artifact translation
shared across providers.
Milestone: 08
Status: SCAFFOLDED
Ownership: Shared CI/CD read mechanics and explicit trigger-approval contract.
Dependencies: Provider contracts; future HTTP policy, credentials, and approval service.
Expected tests: Run-state normalization, pagination, log-limit, artifact, and
write-denial tests.

This module intentionally contains no provider implementation in Milestone 00.
"""
