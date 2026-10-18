"""Offline OAuth state and PKCE infrastructure without provider integration.

Purpose: create local PKCE and single-use state that never calls a provider.
Milestone: 01
Status: IMPLEMENTED
Ownership: auth.oauth
Dependencies: hashlib and Pydantic.
Expected tests: challenge derivation, scope binding, and replay rejection.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from qa_mcp_hub.auth.models import CredentialScope


class OAuthInfrastructureError(RuntimeError):
    """Safe base error for local OAuth coordination."""


class OAuthStateError(OAuthInfrastructureError):
    """Raised for invalid, expired, replayed, or scope-mismatched state."""


class PKCEPair(BaseModel):
    """RFC 7636 verifier/challenge pair with a masked verifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verifier: SecretStr
    challenge: str = Field(min_length=43, max_length=128)
    method: str = Field(default="S256", frozen=True)


class PendingOAuthFlow(BaseModel):
    """Local authorization state; it performs no provider discovery or exchange."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: CredentialScope
    state: SecretStr
    pkce: PKCEPair
    created_at: datetime
    expires_at: datetime
    provider_flow_status: str = Field(default="NOT_IMPLEMENTED", frozen=True)


class _StateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    digest: str
    scope: CredentialScope
    expires_at: datetime


def build_pkce_challenge(verifier: str) -> str:
    """Create an unpadded base64url SHA-256 challenge for a valid verifier."""
    if not 43 <= len(verifier) <= 128:
        raise ValueError("PKCE verifier must contain between 43 and 128 characters")
    allowed = frozenset(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    )
    if any(character not in allowed for character in verifier):
        raise ValueError("PKCE verifier contains an unsupported character")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_pkce_pair(
    *, verifier_factory: Callable[[], str] | None = None
) -> PKCEPair:
    """Generate high-entropy local PKCE material; no network call is made."""
    verifier = (verifier_factory or (lambda: secrets.token_urlsafe(64)))()
    return PKCEPair(
        verifier=SecretStr(verifier),
        challenge=build_pkce_challenge(verifier),
    )


class OAuthStateManager:
    """Create and consume single-use, short-lived state bound to a scope."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        state_factory: Callable[[], str] | None = None,
        verifier_factory: Callable[[], str] | None = None,
        ttl: timedelta = timedelta(minutes=10),
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("OAuth state lifetime must be positive")
        self._clock = clock or (lambda: datetime.now(UTC))
        self._state_factory = state_factory or (lambda: secrets.token_urlsafe(32))
        self._verifier_factory = verifier_factory
        self._ttl = ttl
        self._pending: dict[str, _StateRecord] = {}

    @staticmethod
    def _digest(state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    def begin(self, scope: CredentialScope) -> PendingOAuthFlow:
        """Start local state tracking and produce PKCE request material."""
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("OAuth clock must return an aware datetime")
        state = self._state_factory()
        if len(state) < 32:
            raise ValueError("OAuth state must contain at least 32 characters")
        digest = self._digest(state)
        if digest in self._pending:
            raise OAuthStateError("OAuth state generation produced a duplicate value.")
        expires_at = now + self._ttl
        self._pending[digest] = _StateRecord(
            digest=digest,
            scope=scope,
            expires_at=expires_at,
        )
        return PendingOAuthFlow(
            scope=scope,
            state=SecretStr(state),
            pkce=generate_pkce_pair(verifier_factory=self._verifier_factory),
            created_at=now,
            expires_at=expires_at,
        )

    def consume(self, state: str, *, expected_scope: CredentialScope) -> None:
        """Validate and consume state exactly once without exposing its value."""
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("OAuth clock must return an aware datetime")
        digest = self._digest(state)
        record = self._pending.get(digest)
        if record is None or not hmac.compare_digest(record.digest, digest):
            raise OAuthStateError("OAuth state is invalid, expired, or already used.")
        if record.expires_at <= now:
            del self._pending[digest]
            raise OAuthStateError("OAuth state is invalid, expired, or already used.")
        if record.scope != expected_scope:
            raise OAuthStateError(
                "OAuth state does not match the active connection scope."
            )
        del self._pending[digest]
