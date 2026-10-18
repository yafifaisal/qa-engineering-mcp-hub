"""Profile-scoped credential resolution with explicit backend selection.

Purpose: resolve one credential only from its declared backend and scope.
Milestone: 01
Status: IMPLEMENTED
Ownership: auth.credential_resolver
Dependencies: credential stores and reference models.
Expected tests: scope isolation, missing values, and expiry failure.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from pydantic import SecretStr

from qa_mcp_hub.auth.credential_store import (
    CredentialExpiredError,
    CredentialNotFoundError,
    CredentialScopeError,
    CredentialStore,
    CredentialStorePolicyError,
)
from qa_mcp_hub.auth.models import (
    CredentialReference,
    CredentialScope,
    CredentialStoreKind,
    ResolvedCredential,
)


class CredentialResolver:
    """Resolve only the backend and scope explicitly named by configuration."""

    def __init__(
        self,
        stores: Iterable[CredentialStore],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        by_kind: dict[CredentialStoreKind, CredentialStore] = {}
        for store in stores:
            if store.kind in by_kind:
                raise ValueError(f"duplicate credential backend: {store.kind.value}")
            by_kind[store.kind] = store
        self._stores = by_kind
        self._clock = clock or (lambda: datetime.now(UTC))

    def _store_for(self, reference: CredentialReference) -> CredentialStore:
        store = self._stores.get(reference.store)
        if store is None:
            raise CredentialStorePolicyError(
                "The referenced credential backend is not configured."
            )
        return store

    @staticmethod
    def _check_scope(
        reference: CredentialReference,
        expected_scope: CredentialScope | None,
    ) -> None:
        if expected_scope is not None and reference.scope != expected_scope:
            raise CredentialScopeError(
                "Credential scope does not match the active profile and connection."
            )

    def resolve(
        self,
        reference: CredentialReference,
        *,
        expected_scope: CredentialScope | None = None,
    ) -> ResolvedCredential:
        """Resolve one secret after exact scope and expiry checks."""
        self._check_scope(reference, expected_scope)
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("credential resolver clock must return an aware datetime")
        if reference.is_expired(at=now):
            raise CredentialExpiredError(
                "Credential metadata reports an expired value; rotate or authenticate "
                "again."
            )
        value = self._store_for(reference).get(reference)
        if not value:
            raise CredentialNotFoundError(
                "Credential is missing from the configured backend."
            )
        return ResolvedCredential(
            reference=reference,
            secret=SecretStr(value),
            resolved_at=now,
        )

    def store(
        self,
        reference: CredentialReference,
        secret: SecretStr | str,
        *,
        expected_scope: CredentialScope | None = None,
    ) -> None:
        """Write through only to the explicitly selected writable backend."""
        self._check_scope(reference, expected_scope)
        value = secret.get_secret_value() if isinstance(secret, SecretStr) else secret
        if not value:
            raise ValueError("credential value must not be empty")
        self._store_for(reference).set(reference, value)

    def remove(
        self,
        reference: CredentialReference,
        *,
        expected_scope: CredentialScope | None = None,
    ) -> None:
        """Remove only the value bound to the caller's exact scope."""
        self._check_scope(reference, expected_scope)
        self._store_for(reference).delete(reference)
