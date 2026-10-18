"""Deterministic credential expiry and rotation decisions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from qa_mcp_hub.auth.models import AuthKind, CredentialReference


class TokenLifecycleStatus(StrEnum):
    """Non-secret lifecycle states derived entirely from metadata."""

    valid = "valid"
    expiring = "expiring"
    expired = "expired"
    expiry_unknown = "expiry_unknown"


class TokenLifecycleAction(StrEnum):
    """Safe next actions; no action itself contacts a provider."""

    use = "use"
    rotate = "rotate"
    refresh = "refresh"


class TokenLifecycleDecision(BaseModel):
    """Explain a lifecycle decision without containing credential material."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: TokenLifecycleStatus
    action: TokenLifecycleAction
    reason: str


def evaluate_token_lifecycle(
    reference: CredentialReference,
    *,
    at: datetime | None = None,
    renewal_window: timedelta = timedelta(minutes=5),
) -> TokenLifecycleDecision:
    """Evaluate metadata only; refresh/rotation execution remains caller-controlled."""
    if renewal_window < timedelta(0):
        raise ValueError("renewal window cannot be negative")
    now = at or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("lifecycle comparison time must include a timezone")
    if reference.expires_at is None:
        return TokenLifecycleDecision(
            status=TokenLifecycleStatus.expiry_unknown,
            action=TokenLifecycleAction.use,
            reason=(
                "No expiry metadata is available; apply the provider's rotation policy."
            ),
        )
    action = (
        TokenLifecycleAction.refresh
        if reference.kind is AuthKind.oauth
        else TokenLifecycleAction.rotate
    )
    if reference.expires_at <= now:
        return TokenLifecycleDecision(
            status=TokenLifecycleStatus.expired,
            action=action,
            reason="Credential expiry metadata is in the past.",
        )
    if reference.expires_at <= now + renewal_window:
        return TokenLifecycleDecision(
            status=TokenLifecycleStatus.expiring,
            action=action,
            reason="Credential is within the configured renewal window.",
        )
    return TokenLifecycleDecision(
        status=TokenLifecycleStatus.valid,
        action=TokenLifecycleAction.use,
        reason="Credential expiry metadata is outside the renewal window.",
    )
