"""Typed, non-secret authentication and credential-reference contracts.

Milestone 01 deliberately models where a credential lives without ever placing its
value in configuration. A reference is immutable and bound to the complete
profile/connection scope that is allowed to resolve it.

Purpose: describe credential references and authentication capability contracts.
Milestone: 01
Status: IMPLEMENTED
Ownership: auth.models
Dependencies: Pydantic and the provider identity enum.
Expected tests: scope binding, expiry metadata, and no secret fields.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import quote

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from qa_mcp_hub.core.models import ProviderKind


class CredentialStoreKind(StrEnum):
    """Approved ways for configuration to refer to credential material."""

    environment = "environment"
    keyring = "keyring"
    oauth_reference = "oauth_reference"

    ENVIRONMENT = environment
    KEYRING = keyring
    OAUTH_REFERENCE = oauth_reference


class AuthKind(StrEnum):
    """Authentication forms understood by the provider contract boundary."""

    api_token = "api_token"  # noqa: S105 - enum label, never credential material
    pat = "pat"
    oauth = "oauth"
    none = "none"

    API_TOKEN = api_token
    PAT = pat
    OAUTH = oauth
    NONE = none


class CredentialScope(BaseModel):
    """Immutable authorization scope for one connection's credential."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    provider: ProviderKind
    connection_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    host: str | None = Field(default=None, max_length=253)
    account: str | None = Field(default=None, min_length=1, max_length=320)

    @field_validator("host")
    @classmethod
    def normalize_host(cls, value: str | None) -> str | None:
        """Accept a hostname (and optional port), never a URL or path."""
        if value is None:
            return None
        normalized = value.strip().lower().rstrip(".")
        if (
            not normalized
            or "://" in normalized
            or "/" in normalized
            or any(
                character.isspace() or ord(character) < 32 for character in normalized
            )
        ):
            raise ValueError("host must be a hostname with an optional port")
        return normalized

    @field_validator("account")
    @classmethod
    def normalize_account(cls, value: str | None) -> str | None:
        """Reject ambiguous or control-character-bearing account identifiers."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 for character in normalized):
            raise ValueError("account must be a non-empty printable identifier")
        return normalized

    def storage_key(self, reference: str) -> str:
        """Build an unambiguous, non-secret key for a credential backend."""
        values = (
            ("profile", self.profile),
            ("provider", self.provider.value),
            ("connection", self.connection_id),
            ("host", self.host or ""),
            ("account", self.account or ""),
            ("reference", reference),
        )
        return "v1|" + "|".join(
            f"{name}={quote(value, safe='')}" for name, value in values
        )


class CredentialReference(BaseModel):
    """Serializable pointer to secret material, never the material itself."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    store: CredentialStoreKind
    reference: str = Field(min_length=1, max_length=512)
    scope: CredentialScope
    kind: AuthKind
    expires_at: datetime | None = None

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        """Permit opaque identifiers while excluding whitespace and controls."""
        normalized = value.strip()
        if normalized != value or any(
            character.isspace() or ord(character) < 32 for character in value
        ):
            raise ValueError("credential reference must not contain whitespace")
        return normalized

    @field_validator("expires_at")
    @classmethod
    def require_aware_expiry(cls, value: datetime | None) -> datetime | None:
        """Avoid platform-dependent comparisons with naive timestamps."""
        if value is not None and value.tzinfo is None:
            raise ValueError("credential expiry must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_backend_contract(self) -> CredentialReference:
        """Validate backend-specific reference syntax and no-auth misuse."""
        if self.kind is AuthKind.none:
            raise ValueError("credentials cannot use the 'none' authentication kind")
        if self.store is CredentialStoreKind.environment:
            if re.fullmatch(r"[A-Z][A-Z0-9_]*", self.reference) is None:
                raise ValueError(
                    "environment credential references must be uppercase variable names"
                )
        return self

    @property
    def profile(self) -> str:
        """Expose the bound profile without duplicating serialized state."""
        return self.scope.profile

    @property
    def provider(self) -> ProviderKind:
        """Expose the bound provider without duplicating serialized state."""
        return self.scope.provider

    @property
    def host(self) -> str | None:
        """Expose the bound host without duplicating serialized state."""
        return self.scope.host

    @property
    def account(self) -> str | None:
        """Expose the bound account without duplicating serialized state."""
        return self.scope.account

    @property
    def connection_id(self) -> str:
        """Expose the bound connection without duplicating serialized state."""
        return self.scope.connection_id

    def is_expired(self, *, at: datetime | None = None) -> bool:
        """Return whether the declared metadata says the credential has expired."""
        if self.expires_at is None:
            return False
        checked_at = at or datetime.now(UTC)
        if checked_at.tzinfo is None:
            raise ValueError("expiry comparison time must include a timezone")
        return self.expires_at <= checked_at


class ResolvedCredential(BaseModel):
    """A resolver result whose representation and serialization mask the secret."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: CredentialReference
    secret: SecretStr
    resolved_at: datetime

    @field_validator("resolved_at")
    @classmethod
    def require_aware_resolution_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("credential resolution time must include a timezone")
        return value


class AuthenticationCapability(BaseModel):
    """Provider auth capability contract, not an implementation claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderKind
    supported_kinds: frozenset[AuthKind] = Field(min_length=1)
    token_rotation_supported: bool = False
    oauth_provider_flow_status: str = Field(default="NOT_IMPLEMENTED", frozen=True)

    @field_validator("oauth_provider_flow_status")
    @classmethod
    def prevent_false_oauth_claim(cls, value: str) -> str:
        """M01 provides infrastructure only; no provider OAuth flow is implemented."""
        if value != "NOT_IMPLEMENTED":
            raise ValueError("provider OAuth flows are NOT_IMPLEMENTED in Milestone 01")
        return value

    def supports(self, kind: AuthKind) -> bool:
        """Return whether the contract advertises an authentication form."""
        return kind in self.supported_kinds
