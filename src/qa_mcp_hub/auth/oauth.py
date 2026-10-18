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


_GOOGLE_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"
_DOCS_SCOPE = "https://www.googleapis.com/auth/documents.readonly"
_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.metadata.readonly"


class GoogleAccessToken(BaseModel):
    """A short-lived access token. The refresh token is not retained here."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    access_token: SecretStr
    expires_at: datetime
    scopes: tuple[str, ...] = ()


def refresh_google_access_token(
    *,
    refresh_token: SecretStr,
    client_id: str,
    client_secret: SecretStr,
    http_client: object,
    clock: Callable[[], datetime] | None = None,
    expected_scope: str = _DOCS_SCOPE,
) -> GoogleAccessToken:
    """Exchange a refresh token at Google's token endpoint.

    The returned model and any error message omit the refresh token.
    """
    import httpx

    from qa_mcp_hub.core.errors import ProviderRequestError

    if not isinstance(http_client, httpx.Client):
        raise ProviderRequestError(
            "provider_unreachable",
            "google token request failed",
            status_code=0,
        )
    now = (clock or (lambda: datetime.now(UTC)))()
    if now.tzinfo is None:
        raise ValueError("OAuth clock must return an aware datetime")
    try:
        response = http_client.post(
            _GOOGLE_OAUTH_ENDPOINT,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token.get_secret_value(),
                "client_id": client_id,
                "client_secret": client_secret.get_secret_value(),
            },
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise ProviderRequestError(
            "provider_unreachable",
            "google token request failed",
            status_code=0,
        ) from exc
    if response.status_code in {400, 401}:
        raise ProviderRequestError(
            "oauth_expired",
            "google oauth token is expired or revoked",
            status_code=response.status_code,
        )
    if response.status_code >= 400:
        raise ProviderRequestError(
            "provider_http",
            "google token request failed",
            status_code=response.status_code,
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderRequestError(
            "invalid_response",
            "google token response was not valid JSON",
            status_code=response.status_code,
        ) from exc
    access_token = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(access_token, str):
        raise ProviderRequestError(
            "invalid_response",
            "google token response had an unexpected shape",
            status_code=response.status_code,
        )
    expires_in = payload.get("expires_in")
    if not isinstance(expires_in, int) or expires_in < 1:
        raise ProviderRequestError(
            "invalid_response",
            "google token response had an unexpected shape",
            status_code=response.status_code,
        )
    scope_text = payload.get("scope")
    scopes = tuple(scope_text.split()) if isinstance(scope_text, str) else ()
    if scopes and expected_scope not in scopes:
        raise ProviderRequestError(
            "insufficient_scope",
            "google oauth token is missing the required read scope",
            status_code=0,
        )
    return GoogleAccessToken(
        access_token=SecretStr(access_token),
        expires_at=now + timedelta(seconds=expires_in),
        scopes=scopes,
    )


def google_drive_scope_present(token: GoogleAccessToken) -> bool:
    """Return whether a refresh response included the Drive metadata scope."""
    return not token.scopes or _DRIVE_SCOPE in token.scopes
