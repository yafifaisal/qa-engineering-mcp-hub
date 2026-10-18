"""Local integration configuration and credential-readiness commands.

Purpose: manage connection records and scoped credentials without provider calls.
Milestone: 01
Status: IMPLEMENTED
Ownership: cli.integration_commands
Dependencies: Configuration models, credential stores/resolver, Typer, and Rich.
Expected tests: Duplicate providers, profile isolation, missing credentials, and no network.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from pydantic import SecretStr, ValidationError
from rich.console import Console
from rich.table import Table

from qa_mcp_hub.auth import (
    AuthKind,
    CredentialError,
    CredentialReference,
    CredentialResolver,
    CredentialScope,
    CredentialStoreKind,
    EnvironmentCredentialStore,
    KeyringCredentialStore,
)
from qa_mcp_hub.cli.config import (
    CLIConfigError,
    fail,
    load_user_config,
    persist_config,
    update_config,
)
from qa_mcp_hub.config.loader import ConfigLoadError
from qa_mcp_hub.config.models import (
    ConnectionConfig,
    DeploymentKind,
    HubConfig,
    ProfileConfig,
)
from qa_mcp_hub.config.writer import ConfigWriteError
from qa_mcp_hub.core.models import ProviderKind

app = typer.Typer(help="Manage local provider connection and credential references.")
console = Console()


def _connection(config: HubConfig, connection_id: str) -> ConnectionConfig:
    match = next((item for item in config.connections if item.id == connection_id), None)
    if match is None:
        raise CLIConfigError(f"integration does not exist: {connection_id}")
    return match


def _owner(config: HubConfig, connection_id: str) -> str:
    owners = [
        name
        for name, profile in config.profiles.items()
        if connection_id in profile.connection_ids
    ]
    if len(owners) != 1:
        raise CLIConfigError("integration is not assigned to exactly one profile")
    return owners[0]


def _replace_connection(
    config: HubConfig,
    replacement: ConnectionConfig,
) -> HubConfig:
    connections = tuple(
        replacement if item.id == replacement.id else item
        for item in config.connections
    )
    return update_config(config, connections=connections)


def add_connection_record(
    config: HubConfig,
    connection_id: str,
    *,
    provider: ProviderKind,
    profile_name: str | None,
    deployment: DeploymentKind,
    base_url: str | None,
    account: str | None,
    auth_kind: AuthKind,
) -> HubConfig:
    """Add one globally unique connection and bind it to exactly one profile."""
    if any(item.id == connection_id for item in config.connections):
        raise CLIConfigError(f"integration already exists: {connection_id}")
    selected_profile = profile_name or config.active_profile
    if selected_profile is None or selected_profile not in config.profiles:
        raise CLIConfigError("select an existing profile before adding an integration")
    try:
        connection = ConnectionConfig(
            id=connection_id,
            provider=provider,
            deployment=deployment,
            base_url=base_url,
            account=account,
            auth_kind=auth_kind,
        )
        current = config.profiles[selected_profile]
        values = current.model_dump(mode="python")
        values["connection_ids"] = (*current.connection_ids, connection_id)
        profiles = dict(config.profiles)
        profiles[selected_profile] = ProfileConfig.model_validate(values)
        return update_config(
            config,
            profiles=profiles,
            connections=(*config.connections, connection),
        )
    except ValidationError as exc:
        raise CLIConfigError("integration values are invalid") from exc


def remove_connection_record(config: HubConfig, connection_id: str) -> HubConfig:
    """Remove a connection after rejecting repository reference breakage."""
    _connection(config, connection_id)
    if any(item.connection_id == connection_id for item in config.repositories):
        raise CLIConfigError(
            "integration is referenced by a repository and cannot be removed"
        )
    profiles: dict[str, ProfileConfig] = {}
    for name, profile in config.profiles.items():
        values = profile.model_dump(mode="python")
        values["connection_ids"] = tuple(
            item for item in profile.connection_ids if item != connection_id
        )
        profiles[name] = ProfileConfig.model_validate(values)
    connections = tuple(item for item in config.connections if item.id != connection_id)
    return update_config(config, profiles=profiles, connections=connections)


def _parse_expiry(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CLIConfigError("expiry must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise CLIConfigError("expiry timestamp must include a timezone")
    return parsed


def _scope(
    profile_name: str,
    connection: ConnectionConfig,
) -> CredentialScope:
    return CredentialScope(
        profile=profile_name,
        provider=connection.provider,
        connection_id=connection.id,
        host=connection.host,
        account=connection.account,
    )


def _stores_for(reference: CredentialReference) -> list[object]:
    if reference.store is CredentialStoreKind.environment:
        return [EnvironmentCredentialStore(allowed_names={reference.reference})]
    if reference.store is CredentialStoreKind.keyring:
        return [KeyringCredentialStore()]
    return []


def _handle_error(exc: Exception) -> None:
    if isinstance(
        exc,
        (CLIConfigError, ConfigLoadError, ConfigWriteError, CredentialError),
    ):
        fail(str(exc))
    fail("integration operation failed")


@app.command("add")
def add_integration(
    connection_id: str = typer.Argument(..., help="Unique connection id."),
    provider: ProviderKind = typer.Option(..., "--provider", help="Supported provider."),
    profile: str | None = typer.Option(
        None, "--profile", help="Owning profile; defaults to active."
    ),
    deployment: DeploymentKind = typer.Option(
        DeploymentKind.CLOUD, "--deployment", help="Provider deployment shape."
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="HTTPS endpoint for this connection."
    ),
    account: str | None = typer.Option(None, help="Account or tenant identifier."),
    auth_kind: AuthKind = typer.Option(
        AuthKind.none,
        "--auth-kind",
        help="none, api_token, pat, or oauth.",
    ),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Add a local connection; no provider request is made."""
    try:
        updated = add_connection_record(
            load_user_config(path),
            connection_id,
            provider=provider,
            profile_name=profile,
            deployment=deployment,
            base_url=base_url,
            account=account,
            auth_kind=auth_kind,
        )
        persist_config(updated, path)
    except (
        CLIConfigError,
        ConfigLoadError,
        ConfigWriteError,
        ValidationError,
    ) as exc:
        _handle_error(exc)
    console.print(
        f"Integration '{connection_id}' added; provider connectivity is NOT_IMPLEMENTED"
    )


@app.command("list")
def list_integrations(
    profile: str | None = typer.Option(
        None, "--profile", help="Filter by owning profile."
    ),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """List connection metadata without resolving credentials."""
    try:
        config = load_user_config(path)
        if profile is not None and profile not in config.profiles:
            raise CLIConfigError(f"profile does not exist: {profile}")
    except (CLIConfigError, ConfigLoadError) as exc:
        _handle_error(exc)
    table = Table("Profile", "Id", "Provider", "Deployment", "Auth", "Credential")
    for connection in config.connections:
        owner = _owner(config, connection.id)
        if profile is not None and owner != profile:
            continue
        table.add_row(
            owner,
            connection.id,
            connection.provider.value,
            connection.deployment.value,
            connection.auth_kind.value,
            connection.credential.store.value if connection.credential else "missing",
        )
    console.print(table)


@app.command("auth")
def authenticate_integration(
    connection_id: str = typer.Argument(..., help="Existing connection id."),
    kind: AuthKind | None = typer.Option(
        None, "--kind", help="Override the connection authentication kind."
    ),
    store_kind: CredentialStoreKind | None = typer.Option(
        None, "--store", help="environment, keyring, or oauth_reference."
    ),
    reference: str | None = typer.Option(
        None,
        "--reference",
        help="Environment variable name or opaque backend reference.",
    ),
    expires_at: str | None = typer.Option(
        None, "--expires-at", help="Optional timezone-aware ISO 8601 metadata."
    ),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Attach a scoped credential reference, prompting secretly for keyring values."""
    stored_reference: CredentialReference | None = None
    keyring: KeyringCredentialStore | None = None
    try:
        config = load_user_config(path)
        connection = _connection(config, connection_id)
        profile_name = _owner(config, connection_id)
        selected_kind = kind or connection.auth_kind
        if selected_kind is AuthKind.none:
            raise CLIConfigError("choose an authentication kind before authenticating")
        if connection.credential is not None:
            raise CLIConfigError(
                "credential reference already exists; use integrations rotate"
            )
        selected_store = store_kind
        if selected_store is None:
            selected_store = (
                CredentialStoreKind.oauth_reference
                if selected_kind is AuthKind.oauth
                else CredentialStoreKind.keyring
            )
        if selected_kind is AuthKind.oauth and selected_store is not CredentialStoreKind.oauth_reference:
            raise CLIConfigError(
                "OAuth provider flows are NOT_IMPLEMENTED; only local oauth_reference metadata is allowed"
            )
        if selected_kind is not AuthKind.oauth and selected_store is CredentialStoreKind.oauth_reference:
            raise CLIConfigError("oauth_reference requires the oauth authentication kind")
        if reference is None:
            if selected_store is CredentialStoreKind.environment:
                reference = typer.prompt("Environment variable name")
            else:
                reference = "primary" if selected_store is CredentialStoreKind.keyring else "pending"
        credential = CredentialReference(
            store=selected_store,
            reference=reference,
            scope=_scope(profile_name, connection),
            kind=selected_kind,
            expires_at=_parse_expiry(expires_at),
        )
        values = connection.model_dump(mode="python")
        values.update(auth_kind=selected_kind, credential=credential)
        replacement = ConnectionConfig.model_validate(values)
        updated = _replace_connection(config, replacement)
        if selected_store is CredentialStoreKind.keyring:
            secret = typer.prompt(
                "Credential value",
                hide_input=True,
                confirmation_prompt=True,
            )
            keyring = KeyringCredentialStore()
            CredentialResolver([keyring]).store(
                credential,
                SecretStr(secret),
                expected_scope=credential.scope,
            )
            stored_reference = credential
        try:
            persist_config(updated, path)
        except Exception:
            if stored_reference is not None and keyring is not None:
                keyring.delete(stored_reference)
            raise
    except (
        CLIConfigError,
        ConfigLoadError,
        ConfigWriteError,
        CredentialError,
        ValidationError,
        ValueError,
    ) as exc:
        _handle_error(exc)
    console.print(f"Credential reference configured for '{connection_id}'")
    if selected_kind is AuthKind.oauth:
        console.print("Provider OAuth authorization: NOT_IMPLEMENTED")


@app.command("test")
def test_integration(
    connection_id: str = typer.Argument(..., help="Existing connection id."),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Validate local configuration and credential presence, never the network."""
    ready = False
    try:
        config = load_user_config(path)
        connection = _connection(config, connection_id)
        profile_name = _owner(config, connection_id)
        console.print("Local configuration: VALID")
        if not connection.enabled:
            console.print("Credential readiness: DISABLED")
        elif connection.auth_kind is AuthKind.none:
            console.print("Credential readiness: NOT_REQUIRED")
            ready = True
        elif connection.credential is None:
            console.print("Credential readiness: MISSING")
        elif connection.credential.store is CredentialStoreKind.oauth_reference:
            console.print("Credential readiness: NOT_IMPLEMENTED (OAuth provider flow)")
        else:
            stores = _stores_for(connection.credential)
            resolver = CredentialResolver(stores)  # type: ignore[arg-type]
            resolver.resolve(
                connection.credential,
                expected_scope=_scope(profile_name, connection),
            )
            console.print("Credential readiness: PRESENT")
            ready = True
    except (CLIConfigError, ConfigLoadError, CredentialError) as exc:
        console.print(f"Credential readiness: {exc}")
    console.print("Provider network connectivity: NOT_IMPLEMENTED")
    if not ready:
        raise typer.Exit(code=1)


@app.command("rotate")
def rotate_integration(
    connection_id: str = typer.Argument(..., help="Existing connection id."),
    expires_at: str | None = typer.Option(
        None, "--expires-at", help="Replacement timezone-aware expiry metadata."
    ),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Replace one keyring value without accepting a plaintext command option."""
    old_secret: str | None = None
    keyring: KeyringCredentialStore | None = None
    reference: CredentialReference | None = None
    try:
        config = load_user_config(path)
        connection = _connection(config, connection_id)
        reference = connection.credential
        if reference is None:
            raise CLIConfigError("integration has no credential reference")
        if reference.store is CredentialStoreKind.environment:
            raise CLIConfigError(
                "environment credentials are read-only; rotate the variable outside QA MCP Hub"
            )
        if reference.store is CredentialStoreKind.oauth_reference:
            raise CLIConfigError("OAuth provider token rotation is NOT_IMPLEMENTED")
        keyring = KeyringCredentialStore()
        old_secret = keyring.get(reference)
        secret = typer.prompt(
            "New credential value",
            hide_input=True,
            confirmation_prompt=True,
        )
        replacement_reference = reference.model_copy(
            update={"expires_at": _parse_expiry(expires_at)}
            if expires_at is not None
            else {}
        )
        values = connection.model_dump(mode="python")
        values["credential"] = replacement_reference
        updated = _replace_connection(
            config,
            ConnectionConfig.model_validate(values),
        )
        keyring.set(replacement_reference, secret)
        try:
            persist_config(updated, path)
        except Exception:
            if old_secret is None:
                keyring.delete(reference)
            else:
                keyring.set(reference, old_secret)
            raise
    except (
        CLIConfigError,
        ConfigLoadError,
        ConfigWriteError,
        CredentialError,
        ValidationError,
        ValueError,
    ) as exc:
        _handle_error(exc)
    console.print(f"Credential rotated for '{connection_id}'")


@app.command("remove")
def remove_integration(
    connection_id: str = typer.Argument(..., help="Existing connection id."),
    keep_credential: bool = typer.Option(
        False,
        "--keep-credential",
        help="Leave any keyring value in place intentionally.",
    ),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Remove a connection and, by default, its exact scoped keyring value."""
    deleted_secret: str | None = None
    keyring: KeyringCredentialStore | None = None
    reference: CredentialReference | None = None
    try:
        config = load_user_config(path)
        connection = _connection(config, connection_id)
        reference = connection.credential
        updated = remove_connection_record(config, connection_id)
        if (
            not keep_credential
            and reference is not None
            and reference.store is CredentialStoreKind.keyring
        ):
            keyring = KeyringCredentialStore()
            deleted_secret = keyring.get(reference)
            keyring.delete(reference)
        try:
            persist_config(updated, path)
        except Exception:
            if keyring is not None and reference is not None and deleted_secret is not None:
                keyring.set(reference, deleted_secret)
            raise
    except (
        CLIConfigError,
        ConfigLoadError,
        ConfigWriteError,
        CredentialError,
        ValidationError,
    ) as exc:
        _handle_error(exc)
    console.print(f"Integration '{connection_id}' removed")
