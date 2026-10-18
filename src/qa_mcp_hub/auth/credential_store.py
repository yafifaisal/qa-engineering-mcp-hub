"""Credential-store contract retained for later integration.

Purpose: Define a secret-retrieval interface without choosing a storage backend.
Owning Milestone: 01
Status: SCAFFOLDED
Ownership: auth.credential_store
Dependencies: Python typing only; concrete stores remain future work.
Expected tests: Contract conformance, missing-secret behavior, and deletion semantics.

Implementation note: ``CredentialStore`` preserves pre-existing repository code.
It is not imported or registered by the Milestone 00 runtime.
"""

from typing import Protocol


class CredentialStore(Protocol):
    """Pre-existing protocol for credential backends."""

    def get(self, credential_id: str) -> str | None: ...

    def set(self, credential_id: str, secret: str) -> None: ...

    def delete(self, credential_id: str) -> None: ...
