"""Operating-system keyring backend with no plaintext fallback.

Purpose: store scoped credentials in the active OS keyring backend.
Milestone: 01
Status: IMPLEMENTED
Ownership: auth.keyring_store
Dependencies: optional Python keyring.
Expected tests: profile isolation and sanitized backend failure.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Protocol, cast

from qa_mcp_hub.auth.credential_store import (
    CredentialStorePolicyError,
    CredentialStoreUnavailableError,
)
from qa_mcp_hub.auth.models import CredentialReference, CredentialStoreKind


class _BackendDescriptor(Protocol):
    priority: float


class KeyringFacade(Protocol):
    """Injectable subset of Python keyring used by this adapter."""

    def get_keyring(self) -> _BackendDescriptor: ...

    def get_password(self, service_name: str, username: str) -> str | None: ...

    def set_password(self, service_name: str, username: str, password: str) -> None: ...

    def delete_password(self, service_name: str, username: str) -> None: ...


_UNAVAILABLE_MESSAGE = (
    "No usable OS keyring backend is available. Configure macOS Keychain, Windows "
    "Credential Manager, or a Linux Secret Service backend; no plaintext fallback "
    "was attempted."
)


def _load_system_keyring() -> KeyringFacade:
    """Load the optional dependency only when credential storage is requested."""
    try:
        module: ModuleType = import_module("keyring")
    except ImportError:
        raise CredentialStoreUnavailableError(_UNAVAILABLE_MESSAGE) from None
    return cast(KeyringFacade, module)


class KeyringCredentialStore:
    """Persist credentials using the active operating-system keyring backend."""

    kind = CredentialStoreKind.keyring
    SERVICE = "qa-engineering-mcp-hub"

    def __init__(
        self,
        *,
        backend: KeyringFacade | None = None,
        service: str = SERVICE,
    ) -> None:
        self._backend = backend
        self._service = service

    def _facade(self) -> KeyringFacade:
        facade = self._backend or _load_system_keyring()
        try:
            if facade.get_keyring().priority <= 0:
                raise CredentialStoreUnavailableError(_UNAVAILABLE_MESSAGE)
        except CredentialStoreUnavailableError:
            raise
        except Exception:
            raise CredentialStoreUnavailableError(_UNAVAILABLE_MESSAGE) from None
        return facade

    def describe_backend(self) -> str:
        """Return the active backend type name without reading a credential."""
        return type(self._facade().get_keyring()).__name__

    def _storage_key(self, reference: CredentialReference | str) -> str:
        if isinstance(reference, str):
            if not reference or any(character.isspace() for character in reference):
                raise ValueError(
                    "credential identifier must not be empty or contain spaces"
                )
            return reference
        if reference.store is not self.kind:
            raise CredentialStorePolicyError(
                "Credential reference is assigned to a different backend."
            )
        return reference.scope.storage_key(reference.reference)

    def get(self, reference: CredentialReference | str) -> str | None:
        """Retrieve from the exact scoped key and sanitize backend failures."""
        facade = self._facade()
        try:
            value = facade.get_password(self._service, self._storage_key(reference))
        except Exception:
            raise CredentialStoreUnavailableError(_UNAVAILABLE_MESSAGE) from None
        return value if value else None

    def set(self, reference: CredentialReference | str, secret: str) -> None:
        """Store a non-empty value without logging or serializing it."""
        if not secret:
            raise ValueError("credential value must not be empty")
        facade = self._facade()
        try:
            facade.set_password(self._service, self._storage_key(reference), secret)
        except Exception:
            raise CredentialStoreUnavailableError(_UNAVAILABLE_MESSAGE) from None

    def delete(self, reference: CredentialReference | str) -> None:
        """Delete idempotently while keeping backend error details private."""
        facade = self._facade()
        key = self._storage_key(reference)
        try:
            if facade.get_password(self._service, key) is None:
                return
            facade.delete_password(self._service, key)
        except Exception:
            raise CredentialStoreUnavailableError(_UNAVAILABLE_MESSAGE) from None


# Preserve the public name retained during the M00 architecture migration.
KeyringStore = KeyringCredentialStore
