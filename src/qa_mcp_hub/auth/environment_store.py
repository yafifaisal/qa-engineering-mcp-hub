"""Read-only backend for explicitly approved environment credential references."""

from __future__ import annotations

import os
from collections.abc import Collection, Mapping

from qa_mcp_hub.auth.credential_store import (
    CredentialStorePolicyError,
    CredentialWriteUnsupportedError,
)
from qa_mcp_hub.auth.models import CredentialReference, CredentialStoreKind


class EnvironmentCredentialStore:
    """Resolve named variables without copying them into persisted configuration."""

    kind = CredentialStoreKind.environment

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        allowed_names: Collection[str] | None = None,
        allowed_prefix: str = "QA_MCP_",
    ) -> None:
        self._environ = os.environ if environ is None else environ
        self._allowed_names = (
            frozenset(allowed_names) if allowed_names is not None else None
        )
        self._allowed_prefix = allowed_prefix

    def _check_reference(self, reference: CredentialReference) -> None:
        if reference.store is not self.kind:
            raise CredentialStorePolicyError(
                "Credential reference is assigned to a different backend."
            )
        name = reference.reference
        allowed = (
            name in self._allowed_names
            if self._allowed_names is not None
            else bool(self._allowed_prefix) and name.startswith(self._allowed_prefix)
        )
        if not allowed:
            raise CredentialStorePolicyError(
                "Environment credential reference is not explicitly approved."
            )

    def get(self, reference: CredentialReference) -> str | None:
        """Read a non-empty approved value; never mutate the process environment."""
        self._check_reference(reference)
        value = self._environ.get(reference.reference)
        return value if value else None

    def set(self, reference: CredentialReference, secret: str) -> None:
        """Reject persistence because environment ownership is external."""
        del reference, secret
        raise CredentialWriteUnsupportedError(
            "Environment credential storage is read-only; set the approved variable "
            "outside QA MCP Hub."
        )

    def delete(self, reference: CredentialReference) -> None:
        """Reject deletion because environment ownership is external."""
        del reference
        raise CredentialWriteUnsupportedError(
            "Environment credential storage is read-only; unset the approved variable "
            "outside QA MCP Hub."
        )
