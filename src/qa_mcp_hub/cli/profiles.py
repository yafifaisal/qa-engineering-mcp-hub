"""Profile-management commands for isolated QA workspaces.

Purpose: safely create, inspect, select, edit, and remove local profiles.
Milestone: 01
Status: IMPLEMENTED
Ownership: cli.profile_commands
Dependencies: Immutable configuration models and atomic configuration writes.
Expected tests: Duplicates, active selection, isolation, edits, and safe deletion.
"""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from qa_mcp_hub.cli.config import (
    CLIConfigError,
    fail,
    load_user_config,
    persist_config,
    safe_yaml,
    update_config,
)
from qa_mcp_hub.config.loader import ConfigLoadError
from qa_mcp_hub.config.models import (
    HubConfig,
    LogLevel,
    ProfileConfig,
    QAWorkspaceReference,
)
from qa_mcp_hub.config.writer import ConfigWriteError

app = typer.Typer(help="Create and select isolated workspace profiles.")
console = Console()


def _workspace_path(value: Path) -> str:
    return str(value.expanduser().resolve(strict=False))


def add_profile_record(
    config: HubConfig,
    name: str,
    *,
    description: str | None = None,
    workspace_path: Path | None = None,
    workspace_id: str | None = None,
    make_active: bool = False,
) -> HubConfig:
    """Return a validated configuration containing one new profile."""
    if name in config.profiles:
        raise CLIConfigError(f"profile already exists: {name}")

    workspaces = list(config.workspaces)
    selected_workspace: str | None = None
    if workspace_path is not None:
        selected_workspace = workspace_id or f"{name}-workspace"
        path_value = _workspace_path(workspace_path)
        existing = next(
            (item for item in workspaces if item.id == selected_workspace), None
        )
        if existing is not None and existing.path != path_value:
            raise CLIConfigError(
                f"workspace id already refers to a different path: {selected_workspace}"
            )
        if existing is None:
            workspaces.append(
                QAWorkspaceReference(id=selected_workspace, path=path_value)
            )
    elif workspace_id is not None:
        if not any(item.id == workspace_id for item in workspaces):
            raise CLIConfigError(f"unknown workspace id: {workspace_id}")
        selected_workspace = workspace_id

    try:
        profile = ProfileConfig(
            description=description,
            workspace_id=selected_workspace,
        )
    except ValidationError as exc:
        raise CLIConfigError("profile values are invalid") from exc
    profiles = dict(config.profiles)
    profiles[name] = profile
    active_profile = (
        name if make_active or config.active_profile is None else config.active_profile
    )
    return update_config(
        config,
        profiles=profiles,
        workspaces=tuple(workspaces),
        active_profile=active_profile,
    )


def select_profile_record(config: HubConfig, name: str) -> HubConfig:
    """Select a profile for future resolutions without mutating old snapshots."""
    if name not in config.profiles:
        raise CLIConfigError(f"profile does not exist: {name}")
    return update_config(config, active_profile=name)


def remove_profile_record(
    config: HubConfig,
    name: str,
    *,
    allow_active: bool = False,
) -> HubConfig:
    """Remove an empty profile, refusing implicit connection/credential deletion."""
    profile = config.profiles.get(name)
    if profile is None:
        raise CLIConfigError(f"profile does not exist: {name}")
    if profile.connection_ids:
        raise CLIConfigError(
            "profile still has integrations; remove them explicitly before the profile"
        )
    if config.active_profile == name and not allow_active:
        raise CLIConfigError(
            "profile is active; pass --force-active to clear the active selection"
        )
    profiles = dict(config.profiles)
    del profiles[name]
    active_profile = None if config.active_profile == name else config.active_profile
    return update_config(config, profiles=profiles, active_profile=active_profile)


def _handle_error(exc: Exception) -> NoReturn:
    if isinstance(exc, (CLIConfigError, ConfigLoadError, ConfigWriteError)):
        fail(str(exc))
    fail("profile operation failed")


@app.command("add")
def add_profile(
    name: str = typer.Argument(..., help="Unique lowercase profile id."),
    description: str | None = typer.Option(None, help="Human-readable purpose."),
    workspace: Path | None = typer.Option(
        None, "--workspace", help="Optional QA Workspace path."
    ),
    workspace_id: str | None = typer.Option(
        None, "--workspace-id", help="Workspace id to create or reuse."
    ),
    use: bool = typer.Option(False, "--use", help="Make this the active profile."),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Create a profile; duplicate ids fail without modifying the file."""
    try:
        config = load_user_config(path, allow_missing=True)
        updated = add_profile_record(
            config,
            name,
            description=description,
            workspace_path=workspace,
            workspace_id=workspace_id,
            make_active=use,
        )
        written = persist_config(updated, path)
    except (CLIConfigError, ConfigLoadError, ConfigWriteError, ValidationError) as exc:
        _handle_error(exc)
    console.print(f"Profile '{name}' created in {written}")


@app.command("list")
def list_profiles(
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """List profiles without resolving or displaying any credential."""
    try:
        config = load_user_config(path)
    except ConfigLoadError as exc:
        _handle_error(exc)
    table = Table("Active", "Profile", "Workspace", "Connections", "Repositories")
    for name, profile in sorted(config.profiles.items()):
        table.add_row(
            "*" if name == config.active_profile else "",
            name,
            profile.workspace_id or "-",
            str(len(profile.connection_ids)),
            str(len(profile.repository_ids)),
        )
    console.print(table)


@app.command("use")
def use_profile(
    name: str = typer.Argument(..., help="Existing profile id."),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Select the profile used by subsequent configuration resolutions."""
    try:
        updated = select_profile_record(load_user_config(path), name)
        persist_config(updated, path)
    except (CLIConfigError, ConfigLoadError, ConfigWriteError) as exc:
        _handle_error(exc)
    console.print(f"Active profile: {name}")


@app.command("show")
def show_profile(
    name: str | None = typer.Argument(None, help="Profile id; defaults to active."),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Show one profile and its non-secret references."""
    try:
        config = load_user_config(path)
        selected = name or config.active_profile
        if selected is None or selected not in config.profiles:
            raise CLIConfigError("no matching active profile")
        scoped = update_config(
            config,
            active_profile=selected,
            profiles={selected: config.profiles[selected]},
            connections=tuple(
                item
                for item in config.connections
                if item.id in config.profiles[selected].connection_ids
            ),
            repositories=tuple(
                item
                for item in config.repositories
                if item.id in config.profiles[selected].repository_ids
            ),
            workspaces=tuple(
                item
                for item in config.workspaces
                if item.id == config.profiles[selected].workspace_id
            ),
        )
    except (CLIConfigError, ConfigLoadError) as exc:
        _handle_error(exc)
    typer.echo(safe_yaml(scoped), nl=False)


@app.command("edit")
def edit_profile(
    name: str = typer.Argument(..., help="Existing profile id."),
    description: str | None = typer.Option(None, help="Replacement description."),
    workspace_id: str | None = typer.Option(
        None, "--workspace-id", help="Replacement existing workspace id."
    ),
    log_level: LogLevel | None = typer.Option(
        None, "--log-level", help="Profile log-level override."
    ),
    clear_description: bool = typer.Option(
        False, help="Remove the current description."
    ),
    clear_workspace: bool = typer.Option(False, help="Remove the workspace reference."),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Edit profile metadata while retaining connection isolation."""
    try:
        config = load_user_config(path)
        current = config.profiles.get(name)
        if current is None:
            raise CLIConfigError(f"profile does not exist: {name}")
        if workspace_id is not None and not any(
            item.id == workspace_id for item in config.workspaces
        ):
            raise CLIConfigError(f"unknown workspace id: {workspace_id}")
        values = current.model_dump(mode="python")
        if description is not None or clear_description:
            values["description"] = None if clear_description else description
        if workspace_id is not None or clear_workspace:
            values["workspace_id"] = None if clear_workspace else workspace_id
        if log_level is not None:
            values["log_level"] = log_level
        profiles = dict(config.profiles)
        profiles[name] = ProfileConfig.model_validate(values)
        updated = update_config(config, profiles=profiles)
        persist_config(updated, path)
    except (CLIConfigError, ConfigLoadError, ConfigWriteError, ValidationError) as exc:
        _handle_error(exc)
    console.print(f"Profile '{name}' updated")


@app.command("remove")
def remove_profile(
    name: str = typer.Argument(..., help="Profile id to remove."),
    force_active: bool = typer.Option(
        False,
        "--force-active",
        help="Allow removal of the active empty profile.",
    ),
    path: Path | None = typer.Option(None, "--config", help="Configuration path."),
) -> None:
    """Remove an empty profile without implicitly deleting integrations."""
    try:
        updated = remove_profile_record(
            load_user_config(path),
            name,
            allow_active=force_active,
        )
        persist_config(updated, path)
    except (CLIConfigError, ConfigLoadError, ConfigWriteError) as exc:
        _handle_error(exc)
    console.print(f"Profile '{name}' removed")
