"""Local readiness checks for package settings, configuration, and keyring.

Purpose: report Milestone 00 process readiness and Milestone 01 local configuration
without contacting a provider or printing a secret.
Milestone: 01
Status: IMPLEMENTED
Ownership: cli.doctor
Dependencies: settings loader, configuration loader, and the keyring probe.
Expected tests: valid settings, invalid settings, absent or invalid config, and
no secret output.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from qa_mcp_hub import __version__
from qa_mcp_hub.auth.credential_store import CredentialStoreUnavailableError
from qa_mcp_hub.auth.keyring_store import KeyringCredentialStore
from qa_mcp_hub.config.loader import (
    ConfigLoadError,
    SettingsLoadError,
    load_config,
    load_settings,
)
from qa_mcp_hub.config.paths import default_config_dir, default_config_path

console = Console(stderr=True)


def doctor_command(
    path: Path | None = typer.Option(
        None,
        "--config",
        help="Configuration file to inspect. Defaults to the native user path.",
    ),
) -> None:
    """Check local package, configuration, and credential-backend readiness."""
    try:
        settings = load_settings()
    except SettingsLoadError as exc:
        console.print(f"Configuration error: {exc}")
        raise typer.Exit(code=2) from exc

    console.print(f"QA MCP Hub {__version__}: ready (local only)")
    console.print(f"Server: {settings.server_name}")
    console.print(f"Transport: {settings.transport}")
    console.print(f"Config directory: {default_config_dir()}")
    console.print("External integrations: live connectivity is not implemented")

    config_path = path.expanduser() if path is not None else default_config_path()
    exit_code = 0
    if not config_path.is_file():
        console.print("User configuration: absent")
    else:
        try:
            config = load_config(config_path)
        except ConfigLoadError as exc:
            console.print(f"User configuration: INVALID ({exc})")
            exit_code = 1
        else:
            active = config.active_profile or "none"
            console.print(
                "User configuration: VALID "
                f"({len(config.profiles)} profile(s), active {active}, "
                f"{len(config.connections)} connection(s))"
            )

    try:
        backend_name = KeyringCredentialStore().describe_backend()
    except CredentialStoreUnavailableError as exc:
        console.print(f"Keyring backend: unavailable ({exc})")
    else:
        console.print(f"Keyring backend: available ({backend_name})")

    console.print("Provider network connectivity: NOT_IMPLEMENTED")
    if exit_code:
        raise typer.Exit(code=exit_code)
