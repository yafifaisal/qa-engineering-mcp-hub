"""Typer command application for the implemented Milestone 00 surface.

Purpose: expose serve, doctor, capabilities, help, and version behavior to humans.
Milestone: 00
Status: IMPLEMENTED
Ownership: cli.root_application
Dependencies: Typer, Rich, and local M00 services.
Expected tests: all commands, standalone version, help, and exit codes.
"""

from typing import Annotated

import typer
from rich.console import Console

from qa_mcp_hub import __version__
from qa_mcp_hub.config import SettingsLoadError, default_config_dir, load_settings
from qa_mcp_hub.core.capabilities import list_capabilities

app = typer.Typer(
    help="QA Engineering MCP Hub — Community Edition",
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console(stderr=True)


@app.command("serve")
def serve_command() -> None:
    """Run FastMCP using stdio for Codex and other MCP clients."""
    from qa_mcp_hub.server import serve

    serve()


@app.command("doctor")
def doctor() -> None:
    """Check local package readiness, not third-party integrations."""
    try:
        settings = load_settings()
    except SettingsLoadError as exc:
        console.print(f"Configuration error: {exc}")
        raise typer.Exit(code=2) from exc
    console.print(f"QA MCP Hub {__version__}: ready (local only)")
    console.print(f"Server: {settings.server_name}")
    console.print(f"Transport: {settings.transport}")
    console.print(f"Config directory: {default_config_dir()}")
    console.print("External integrations: not implemented in Milestone 00")


@app.command("capabilities")
def capabilities() -> None:
    """Show capabilities that are callable now versus planned."""
    catalog = list_capabilities()
    console.print("Implemented: " + ", ".join(catalog.implemented))
    console.print("Planned: " + ", ".join(catalog.planned))


@app.callback()
def root(
    version: Annotated[
        bool, typer.Option("--version", help="Display package version", is_eager=True)
    ] = False,
) -> None:
    """Handle root options shared by every command."""
    if version:
        console.print(__version__)
        raise typer.Exit()


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()
