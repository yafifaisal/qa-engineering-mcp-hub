"""Milestone 01 credential isolation, backend, redaction, and OAuth tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr, ValidationError

from qa_mcp_hub.auth import (
    REDACTED,
    AuthKind,
    CredentialExpiredError,
    CredentialNotFoundError,
    CredentialReference,
    CredentialResolver,
    CredentialScope,
    CredentialScopeError,
    CredentialStoreKind,
    CredentialStorePolicyError,
    CredentialStoreUnavailableError,
    CredentialWriteUnsupportedError,
    EnvironmentCredentialStore,
    KeyringCredentialStore,
    OAuthStateError,
    OAuthStateManager,
    TokenLifecycleAction,
    TokenLifecycleStatus,
    build_pkce_challenge,
    evaluate_token_lifecycle,
    redact,
    redact_text,
)
from qa_mcp_hub.core.models import ProviderKind

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
SECRET = "m01-sensitive-value-for-tests"  # noqa: S105 - synthetic test fixture


def _scope(profile: str = "alpha", connection: str = "github-main") -> CredentialScope:
    return CredentialScope(
        profile=profile,
        provider=ProviderKind.github,
        connection_id=connection,
        host="API.GITHUB.COM.",
        account="qa@example.invalid",
    )


def _reference(
    *,
    store: CredentialStoreKind = CredentialStoreKind.keyring,
    scope: CredentialScope | None = None,
    expires_at: datetime | None = None,
    kind: AuthKind = AuthKind.pat,
) -> CredentialReference:
    return CredentialReference(
        store=store,
        reference=(
            "QA_MCP_GITHUB_TOKEN"
            if store is CredentialStoreKind.environment
            else "main"
        ),
        scope=scope or _scope(),
        kind=kind,
        expires_at=expires_at,
    )


class _BackendDescriptor:
    def __init__(self, priority: float = 1.0) -> None:
        self.priority = priority


class _MemoryKeyring:
    def __init__(self, *, priority: float = 1.0) -> None:
        self.descriptor = _BackendDescriptor(priority)
        self.values: dict[tuple[str, str], str] = {}

    def get_keyring(self) -> _BackendDescriptor:
        return self.descriptor

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.values.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.values[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.values.pop((service_name, username), None)


class _ExplodingKeyring(_MemoryKeyring):
    def get_password(self, service_name: str, username: str) -> str | None:
        del service_name, username
        raise RuntimeError(f"backend accidentally included {SECRET}")


def test_reference_is_typed_scoped_and_contains_no_secret_field() -> None:
    reference = _reference()

    assert reference.scope.host == "api.github.com"
    assert reference.profile == "alpha"
    assert "secret" not in reference.model_dump()
    assert SECRET not in reference.model_dump_json()
    with pytest.raises(ValidationError):
        CredentialReference(
            store="environment",
            reference="mixedCase",
            scope=_scope(),
            kind="api_token",
        )


def test_keyring_values_are_isolated_by_complete_profile_scope() -> None:
    backend = _MemoryKeyring()
    store = KeyringCredentialStore(backend=backend)
    alpha = _reference(scope=_scope("alpha"))
    beta = _reference(scope=_scope("beta"))

    store.set(alpha, "alpha-value")
    store.set(beta, "beta-value")

    assert store.get(alpha) == "alpha-value"
    assert store.get(beta) == "beta-value"
    assert len(backend.values) == 2
    store.delete(alpha)
    assert store.get(alpha) is None
    assert store.get(beta) == "beta-value"


def test_environment_backend_is_allowlisted_and_read_only() -> None:
    reference = _reference(store=CredentialStoreKind.environment)
    store = EnvironmentCredentialStore(
        environ={reference.reference: SECRET},
        allowed_names={reference.reference},
    )

    assert store.get(reference) == SECRET
    with pytest.raises(CredentialWriteUnsupportedError):
        store.set(reference, "replacement")
    with pytest.raises(CredentialWriteUnsupportedError):
        store.delete(reference)

    unapproved = EnvironmentCredentialStore(
        environ={reference.reference: SECRET},
        allowed_names=set(),
    )
    with pytest.raises(CredentialStorePolicyError):
        unapproved.get(reference)


def test_resolver_enforces_scope_missing_value_and_expiry() -> None:
    reference = _reference(store=CredentialStoreKind.environment)
    store = EnvironmentCredentialStore(
        environ={reference.reference: SECRET},
        allowed_names={reference.reference},
    )
    resolver = CredentialResolver([store], clock=lambda: NOW)

    resolved = resolver.resolve(reference, expected_scope=reference.scope)
    assert resolved.secret.get_secret_value() == SECRET
    assert SECRET not in repr(resolved)
    assert SECRET not in resolved.model_dump_json()

    with pytest.raises(CredentialScopeError):
        resolver.resolve(reference, expected_scope=_scope("beta"))

    missing = CredentialResolver(
        [
            EnvironmentCredentialStore(
                environ={},
                allowed_names={reference.reference},
            )
        ],
        clock=lambda: NOW,
    )
    with pytest.raises(CredentialNotFoundError, match="missing"):
        missing.resolve(reference)

    expired = reference.model_copy(update={"expires_at": NOW - timedelta(seconds=1)})
    with pytest.raises(CredentialExpiredError, match="expired"):
        resolver.resolve(expired)


def test_keyring_backend_failures_are_actionable_and_sanitized() -> None:
    unavailable = KeyringCredentialStore(backend=_MemoryKeyring(priority=0))
    with pytest.raises(CredentialStoreUnavailableError) as unavailable_error:
        unavailable.get(_reference())
    message = str(unavailable_error.value)
    assert "OS keyring backend" in message
    assert "plaintext fallback" in message

    exploding = KeyringCredentialStore(backend=_ExplodingKeyring())
    with pytest.raises(CredentialStoreUnavailableError) as backend_error:
        exploding.get(_reference())
    assert SECRET not in str(backend_error.value)


def test_nested_and_text_redaction_preserve_non_secret_references() -> None:
    value = {
        "credential_reference": "keyring-id",
        "nested": [
            {"access_token": SECRET},
            SecretStr("another-sensitive-value"),
        ],
        "url": f"https://user:{SECRET}@example.invalid/path?token={SECRET}&mode=read",
    }

    redacted = redact(value, secrets=(SECRET,))
    assert redacted["credential_reference"] == "keyring-id"
    assert redacted["nested"] == [{"access_token": REDACTED}, REDACTED]
    assert SECRET not in str(redacted)

    text = redact_text(
        f"Authorization: Bearer {SECRET}; password={SECRET}",
        secrets=(SECRET,),
    )
    assert SECRET not in text
    assert REDACTED in text


def test_oauth_state_and_pkce_are_offline_scoped_and_single_use() -> None:
    state = "s" * 43
    verifier = "v" * 64
    manager = OAuthStateManager(
        clock=lambda: NOW,
        state_factory=lambda: state,
        verifier_factory=lambda: verifier,
    )
    flow = manager.begin(_scope())

    assert flow.provider_flow_status == "NOT_IMPLEMENTED"
    assert flow.pkce.challenge == build_pkce_challenge(verifier)
    assert state not in repr(flow)
    assert verifier not in repr(flow)
    with pytest.raises(OAuthStateError, match="active connection"):
        manager.consume(state, expected_scope=_scope("beta"))

    manager.consume(state, expected_scope=_scope())
    with pytest.raises(OAuthStateError, match="invalid"):
        manager.consume(state, expected_scope=_scope())


def test_lifecycle_decisions_do_not_refresh_or_contact_a_provider() -> None:
    unknown = evaluate_token_lifecycle(_reference(), at=NOW)
    assert unknown.status is TokenLifecycleStatus.expiry_unknown
    assert unknown.action is TokenLifecycleAction.use

    expired_oauth = _reference(
        kind=AuthKind.oauth,
        expires_at=NOW - timedelta(seconds=1),
    )
    decision = evaluate_token_lifecycle(expired_oauth, at=NOW)
    assert decision.status is TokenLifecycleStatus.expired
    assert decision.action is TokenLifecycleAction.refresh
