"""Typer command application for Milestone 00 and local Milestone 01 commands.

Purpose: expose serve, doctor, capabilities, and local setup/configuration commands.
Milestone: 01
Status: IMPLEMENTED
Ownership: cli.root_application
Dependencies: Typer, Rich, and local M00/M01 command modules.
Expected tests: help, version, doctor, capabilities, and M01 command registration.
"""

from typing import Annotated

import typer
from rich.console import Console

from qa_mcp_hub import __version__
from qa_mcp_hub.cli.clients import app as clients_app
from qa_mcp_hub.cli.config import app as config_app
from qa_mcp_hub.cli.doctor import doctor_command
from qa_mcp_hub.cli.integrations import app as integrations_app
from qa_mcp_hub.cli.profiles import app as profiles_app
from qa_mcp_hub.cli.repositories import app as repositories_app
from qa_mcp_hub.cli.setup import setup_command
from qa_mcp_hub.core.capabilities import list_capabilities

app = typer.Typer(
    help="QA Engineering MCP Hub — Community Edition",
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console(stderr=True)
app.command("setup")(setup_command)
app.command("doctor")(doctor_command)
app.add_typer(profiles_app, name="profiles")
app.add_typer(integrations_app, name="integrations")
app.add_typer(config_app, name="config")
app.add_typer(clients_app, name="clients")
app.add_typer(repositories_app, name="repositories")


@app.command("serve")
def serve_command() -> None:
    """Run FastMCP using stdio for Codex and other MCP clients."""
    from qa_mcp_hub.server import serve

    serve()


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
