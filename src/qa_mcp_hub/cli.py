"""Typer CLI entry point; business commands are added in later milestones."""

from typing import Annotated

import typer
from rich.console import Console

from qa_mcp_hub import __version__
from qa_mcp_hub.capabilities import list_capabilities
from qa_mcp_hub.config import HubSettings, default_config_dir

app = typer.Typer(help="QA Engineering MCP Hub — Community Edition")
console = Console(stderr=True)


@app.command("serve")
def serve_command() -> None:
    """Run FastMCP using stdio for Codex and other MCP clients."""
    from qa_mcp_hub.server import serve

    serve()


@app.command("doctor")
def doctor() -> None:
    """Check local package readiness; external integrations are not configured yet."""
    settings = HubSettings()
    console.print(f"QA MCP Hub {__version__}: ready (local only)")
    console.print(f"Server: {settings.server_name}")
    console.print(f"Config directory (future): {default_config_dir()}")
    console.print("External integrations: not implemented in Milestone 00")


@app.command("capabilities")
def capabilities() -> None:
    """Show which capabilities are actually available."""
    catalog = list_capabilities()
    console.print("Implemented: " + ", ".join(catalog.implemented))
    console.print("Planned: " + ", ".join(catalog.planned))


@app.callback()
def root(
    version: Annotated[
        bool, typer.Option("--version", help="Display package version", is_eager=True)
    ] = False,
) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
