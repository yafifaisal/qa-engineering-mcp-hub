"""Secure local credential references, stores, resolution, and OAuth primitives."""

from qa_mcp_hub.auth.credential_resolver import CredentialResolver
from qa_mcp_hub.auth.credential_store import (
    CredentialError,
    CredentialExpiredError,
    CredentialNotFoundError,
    CredentialScopeError,
    CredentialStore,
    CredentialStorePolicyError,
    CredentialStoreUnavailableError,
    CredentialWriteUnsupportedError,
)
from qa_mcp_hub.auth.environment_store import EnvironmentCredentialStore
from qa_mcp_hub.auth.keyring_store import KeyringCredentialStore, KeyringStore
from qa_mcp_hub.auth.models import (
    AuthenticationCapability,
    AuthKind,
    CredentialReference,
    CredentialScope,
    CredentialStoreKind,
    ResolvedCredential,
)
from qa_mcp_hub.auth.oauth import (
    OAuthInfrastructureError,
    OAuthStateError,
    OAuthStateManager,
    PendingOAuthFlow,
    PKCEPair,
    build_pkce_challenge,
    generate_pkce_pair,
)
from qa_mcp_hub.auth.redaction import REDACTED, redact, redact_text, redact_value
from qa_mcp_hub.auth.token_lifecycle import (
    TokenLifecycleAction,
    TokenLifecycleDecision,
    TokenLifecycleStatus,
    evaluate_token_lifecycle,
)

__all__ = [
    "REDACTED",
    "AuthenticationCapability",
    "AuthKind",
    "CredentialError",
    "CredentialExpiredError",
    "CredentialNotFoundError",
    "CredentialReference",
    "CredentialResolver",
    "CredentialScope",
    "CredentialScopeError",
    "CredentialStore",
    "CredentialStoreKind",
    "CredentialStorePolicyError",
    "CredentialStoreUnavailableError",
    "CredentialWriteUnsupportedError",
    "EnvironmentCredentialStore",
    "KeyringCredentialStore",
    "KeyringStore",
    "OAuthInfrastructureError",
    "OAuthStateError",
    "OAuthStateManager",
    "PKCEPair",
    "PendingOAuthFlow",
    "ResolvedCredential",
    "TokenLifecycleAction",
    "TokenLifecycleDecision",
    "TokenLifecycleStatus",
    "build_pkce_challenge",
    "evaluate_token_lifecycle",
    "generate_pkce_pair",
    "redact",
    "redact_text",
    "redact_value",
]
