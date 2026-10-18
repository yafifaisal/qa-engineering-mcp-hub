"""Credential-store contracts and deliberately sanitized domain errors."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from qa_mcp_hub.auth.models import CredentialReference, CredentialStoreKind


class CredentialError(RuntimeError):
    """Base class for errors safe to present without revealing secret material."""


class CredentialNotFoundError(CredentialError):
    """Raised when an approved reference has no available value."""


class CredentialExpiredError(CredentialError):
    """Raised before use when expiry metadata is in the past."""


class CredentialScopeError(CredentialError):
    """Raised when a caller attempts to resolve outside the bound scope."""


class CredentialStoreUnavailableError(CredentialError):
    """Raised when an approved secure backend cannot be used."""


class CredentialStorePolicyError(CredentialError):
    """Raised when a backend operation is not permitted by policy."""


class CredentialWriteUnsupportedError(CredentialStorePolicyError):
    """Raised when writes are attempted against a read-only backend."""


@runtime_checkable
class CredentialStore(Protocol):
    """Narrow interface implemented by approved local secret backends."""

    kind: CredentialStoreKind

    def get(self, reference: CredentialReference) -> str | None:
        """Retrieve one secret for its exact scoped reference."""
        ...

    def set(self, reference: CredentialReference, secret: str) -> None:
        """Store one non-empty secret, if the backend is writable."""
        ...

    def delete(self, reference: CredentialReference) -> None:
        """Delete one secret, if the backend is writable."""
        ...
