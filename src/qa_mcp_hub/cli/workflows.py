"""List registered workflows without executing them.

Purpose: show workspace workflow documents for the selected profile.
Milestone: 11
Status: IMPLEMENTED
Ownership: cli.workflows
Dependencies: configuration loader and workflow discovery.
Expected tests: profile isolation and no execution side effect.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from qa_mcp_hub.cli.config import CLIConfigError, fail, load_user_config
from qa_mcp_hub.config.loader import ConfigLoadError
from qa_mcp_hub.config.models import HubConfig
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.verification.service import workspace_for
from qa_mcp_hub.workflows.registry import load_workflows

app = typer.Typer(help="List registered workflows. Listing does not execute them.")
console = Console()


def _profile_name(config: HubConfig, profile: str | None) -> str:
    selected = profile or config.active_profile
    if selected is None or selected not in config.profiles:
        raise CLIConfigError("select a profile before listing workflows")
    return selected


def _handle_error(exc: Exception) -> NoReturn:
    if isinstance(exc, CLIConfigError | HubError | ConfigLoadError):
        fail(str(exc))
    raise exc


@app.command("list")
def list_command(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Profile to inspect"),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Configuration file"),
    ] = None,
) -> None:
    """List workflow documents owned by one profile workspace."""
    try:
        config = load_user_config(config_path)
        profile_id = _profile_name(config, profile)
        _selected, workspace = workspace_for(config, profile_id)
        rows = load_workflows(workspace)
    except Exception as exc:
        _handle_error(exc)
    table = Table(title=f"Workflows for {profile_id}")
    table.add_column("ID")
    table.add_column("Enabled")
    table.add_column("Approved")
    table.add_column("Policy")
    for item in rows:
        table.add_row(
            item.id,
            str(item.enabled).lower(),
            str(item.approved).lower(),
            item.evidence_policy,
        )
    console.print(table)
    console.print(f"{len(rows)} workflow(s); none were executed")
