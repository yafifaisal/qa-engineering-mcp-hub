"""Typer commands and shared helpers for non-secret user configuration.

Purpose: load, validate, redact, and present the consolidated Milestone 01 YAML.
Milestone: 01
Status: IMPLEMENTED
Ownership: cli.config_commands
Dependencies: Configuration loaders/writers, redaction, Typer, and Rich.
Expected tests: Missing/malformed files, validation, safe output, and exit codes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError
from rich.console import Console

from qa_mcp_hub.auth.redaction import redact
from qa_mcp_hub.config.loader import (
    ConfigLoadError,
    ConfigNotFoundError,
    load_config,
)
from qa_mcp_hub.config.models import CURRENT_SCHEMA_VERSION, HubConfig
from qa_mcp_hub.config.paths import default_config_path
from qa_mcp_hub.config.writer import ConfigWriteError, save_config

app = typer.Typer(help="Inspect and validate local non-secret configuration.")
console = Console()
error_console = Console(stderr=True)


class CLIConfigError(ValueError):
    """A presentation-safe local configuration command error."""


def selected_config_path(path: Path | None) -> Path:
    """Resolve an explicit CLI path before the native user-config default."""
    return path.expanduser() if path is not None else default_config_path()


def empty_config() -> HubConfig:
    """Create an explicit current-version configuration for first-time setup."""
    return HubConfig(schema_version=CURRENT_SCHEMA_VERSION)


def load_user_config(path: Path | None, *, allow_missing: bool = False) -> HubConfig:
    """Load one user configuration, optionally returning a new empty model."""
    selected = selected_config_path(path)
    try:
        return load_config(selected)
    except ConfigNotFoundError:
        if allow_missing:
            return empty_config()
        raise


def update_config(config: HubConfig, **changes: Any) -> HubConfig:
    """Revalidate a full immutable configuration after a command mutation."""
    document = config.model_dump(mode="python")
    document.update(changes)
    try:
        return HubConfig.model_validate(document)
    except ValidationError as exc:
        raise CLIConfigError(
            "the requested change would make configuration invalid"
        ) from exc


def persist_config(config: HubConfig, path: Path | None) -> Path:
    """Persist configuration through the atomic writer at the selected path."""
    return save_config(config, selected_config_path(path))


def safe_yaml(config: HubConfig) -> str:
    """Render a redacted YAML view without any resolved credential value."""
    document = config.model_dump(mode="json", exclude_none=True)
    safe_document = redact(document)
    return str(
        yaml.safe_dump(
            safe_document,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    )


def fail(message: str, *, code: int = 2) -> None:
    """Print one sanitized command error and stop the current Typer command."""
    error_console.print(f"Error: {message}")
    raise typer.Exit(code=code)


@app.command("show")
def show_config(
    path: Path | None = typer.Option(
        None,
        "--config",
        help="Explicit configuration path (highest path precedence).",
    ),
) -> None:
    """Print the validated configuration with defensive redaction."""
    try:
        config = load_user_config(path)
    except ConfigLoadError as exc:
        fail(str(exc))
    typer.echo(safe_yaml(config), nl=False)


@app.command("validate")
def validate_config_command(
    path: Path | None = typer.Option(None, "--config", help="Configuration to validate."),
) -> None:
    """Strictly parse and validate the current schema without modifying it."""
    selected = selected_config_path(path)
    try:
        config = load_config(selected)
    except ConfigLoadError as exc:
        fail(str(exc))
    console.print(
        f"VALID: schema {config.schema_version}, {len(config.profiles)} profile(s), "
        f"{len(config.connections)} connection(s)"
    )


def present_unexpected_error(exc: Exception) -> None:
    """Map known persistence/validation errors to a secret-safe CLI boundary."""
    if isinstance(exc, (ConfigLoadError, ConfigWriteError, CLIConfigError)):
        fail(str(exc))
    fail("configuration operation failed")
