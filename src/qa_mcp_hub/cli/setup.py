"""Idempotent interactive setup wizard for local QA MCP Hub configuration.

Purpose: create or select a profile and optional QA Workspace without secrets.
Milestone: 01
Status: IMPLEMENTED
Ownership: cli.setup_wizard
Dependencies: Profile commands, atomic configuration persistence, Typer, and Rich.
Expected tests: Mocked input, cancellation, safe reruns, and no secret output.
"""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from qa_mcp_hub.cli.config import (
    CLIConfigError,
    fail,
    load_user_config,
    persist_config,
    update_config,
)
from qa_mcp_hub.cli.profiles import add_profile_record, select_profile_record
from qa_mcp_hub.config.loader import ConfigLoadError
from qa_mcp_hub.config.models import ProfileConfig, QAWorkspaceReference
from qa_mcp_hub.config.writer import ConfigWriteError

console = Console()


def _normalized_workspace(path: Path) -> str:
    return str(path.expanduser().resolve(strict=False))


def setup_command(
    profile: str | None = typer.Option(
        None, "--profile", help="Profile id; prompted when omitted."
    ),
    workspace: Path | None = typer.Option(
        None, "--workspace", help="Optional QA Workspace path."
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Use defaults instead of prompting.",
    ),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Run the local setup wizard; rerunning the same answers is safe."""
    console.print(
        Panel.fit(
            "Configure a local profile. Credentials remain in keyring or approved "
            "environment variables.",
            title="QA MCP Hub setup",
        )
    )
    profile_name = profile
    workspace_path = workspace
    if not non_interactive:
        if profile_name is None:
            profile_name = typer.prompt("Profile id", default="default")
        if workspace_path is None:
            answer = typer.prompt(
                "QA Workspace path (optional)",
                default="",
                show_default=False,
            ).strip()
            workspace_path = Path(answer) if answer else None
    elif profile_name is None:
        profile_name = "default"

    try:
        config = load_user_config(path, allow_missing=True)
        existing = config.profiles.get(profile_name)
        if existing is None:
            updated = add_profile_record(
                config,
                profile_name,
                workspace_path=workspace_path,
                make_active=True,
            )
            result = "created"
        else:
            updated = config
            if workspace_path is not None:
                normalized = _normalized_workspace(workspace_path)
                if existing.workspace_id is None:
                    workspace_id = f"{profile_name}-workspace"
                    known = next(
                        (item for item in updated.workspaces if item.id == workspace_id),
                        None,
                    )
                    if known is not None and known.path != normalized:
                        raise CLIConfigError(
                            f"workspace id already refers to a different path: {workspace_id}"
                        )
                    workspaces = list(updated.workspaces)
                    if known is None:
                        workspaces.append(
                            QAWorkspaceReference(id=workspace_id, path=normalized)
                        )
                    profiles = dict(updated.profiles)
                    values = existing.model_dump(mode="python")
                    values["workspace_id"] = workspace_id
                    profiles[profile_name] = ProfileConfig.model_validate(values)
                    updated = update_config(
                        updated,
                        profiles=profiles,
                        workspaces=tuple(workspaces),
                    )
                else:
                    current_workspace = next(
                        item
                        for item in updated.workspaces
                        if item.id == existing.workspace_id
                    )
                    if current_workspace.path != normalized:
                        raise CLIConfigError(
                            "existing profile points to a different QA Workspace"
                        )
            updated = select_profile_record(updated, profile_name)
            result = "reused"
        written = persist_config(updated, path)
    except (
        CLIConfigError,
        ConfigLoadError,
        ConfigWriteError,
        ValidationError,
        StopIteration,
    ) as exc:
        if isinstance(exc, (CLIConfigError, ConfigLoadError, ConfigWriteError)):
            fail(str(exc))
        fail("setup values are invalid")

    console.print(f"Profile '{profile_name}' {result} and selected")
    console.print(f"Configuration: {written}")
    console.print("Next: qa-mcp integrations add --help")
