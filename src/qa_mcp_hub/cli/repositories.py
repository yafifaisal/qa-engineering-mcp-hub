"""Register, list, discover, and validate local and remote repositories.

Purpose: expose repository registration without calling a remote Git API.
Milestone: 02
Status: IMPLEMENTED
Ownership: cli.repositories
Dependencies: Repository service, path policy, and active profile resolution.
Expected tests: allowlists, duplicate registration, invalid paths, and stable output.
"""

from pathlib import Path
from typing import Annotated, NoReturn

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from qa_mcp_hub.cli.config import (
    CLIConfigError,
    fail,
    load_user_config,
    persist_config,
)
from qa_mcp_hub.config.loader import ConfigLoadError
from qa_mcp_hub.config.models import HubConfig, RepositoryReference
from qa_mcp_hub.config.writer import ConfigWriteError
from qa_mcp_hub.core.enums import IndexingPermission
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.repositories.discovery import discover_local_repositories
from qa_mcp_hub.repositories.registry import (
    approved_roots,
    list_repositories,
    register_repository,
    remove_repository,
)
from qa_mcp_hub.repositories.validator import validate_repository

app = typer.Typer(help="Register and validate local or remote repositories.")
console = Console()


def _profile_name(config: HubConfig, profile: str | None) -> str:
    selected = profile or config.active_profile
    if selected is None or selected not in config.profiles:
        raise CLIConfigError("select a profile before using repositories")
    return selected


def _handle_error(exc: Exception) -> NoReturn:
    if isinstance(exc, ValidationError):
        fail("repository definition is invalid")
    if isinstance(exc, CLIConfigError | HubError | ConfigLoadError | ConfigWriteError):
        fail(str(exc))
    raise exc


@app.command("add")
def add_repository(
    repository_id: Annotated[str, typer.Argument(help="Repository identifier")],
    display_name: Annotated[
        str | None,
        typer.Option("--display-name", help="Human-readable name"),
    ] = None,
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Local checkout inside the profile workspace"),
    ] = None,
    path_env: Annotated[
        str | None,
        typer.Option("--path-env", help="Environment variable holding a local path"),
    ] = None,
    remote: Annotated[
        str | None,
        typer.Option("--remote", help="Remote slug or URL without credentials"),
    ] = None,
    connection: Annotated[
        str | None,
        typer.Option("--connection", help="Provider connection id in this profile"),
    ] = None,
    branch: Annotated[
        str,
        typer.Option("--branch", help="Default branch name"),
    ] = "main",
    include: Annotated[
        list[str] | None,
        typer.Option("--include", help="Relative include pattern; repeat for more"),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Relative exclude pattern; repeat for more"),
    ] = None,
    indexing: Annotated[
        IndexingPermission,
        typer.Option("--indexing", help="Permission recorded for Milestone 05"),
    ] = IndexingPermission.none,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Profile that will own the repository"),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Configuration file"),
    ] = None,
) -> None:
    """Register one local checkout or remote repository definition."""
    try:
        config = load_user_config(config_path)
        profile_id = _profile_name(config, profile)
        repository = RepositoryReference(
            id=repository_id,
            display_name=display_name or repository_id,
            path=str(path) if path is not None else None,
            path_env=path_env,
            remote=remote,
            connection_id=connection,
            default_branch=branch,
            include=tuple(include or ()),
            exclude=tuple(exclude or ()),
            indexing=indexing,
        )
        updated = register_repository(config, profile_id, repository)
        persist_config(updated, config_path)
    except Exception as exc:
        _handle_error(exc)
    console.print(f"Registered repository {repository_id} on profile {profile_id}.")


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
    """List repositories owned by one profile."""
    try:
        config = load_user_config(config_path)
        profile_id = _profile_name(config, profile)
        rows = list_repositories(config, profile_id)
    except Exception as exc:
        _handle_error(exc)
    table = Table(title=f"Repositories for {profile_id}")
    table.add_column("ID")
    table.add_column("Source")
    table.add_column("Connection")
    table.add_column("Indexing")
    for item in rows:
        source = item.path or item.path_env or item.remote or ""
        table.add_row(item.id, source, item.connection_id or "", item.indexing.value)
    console.print(table)


@app.command("remove")
def remove_command(
    repository_id: Annotated[str, typer.Argument(help="Repository identifier")],
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Owning profile"),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Configuration file"),
    ] = None,
) -> None:
    """Remove one repository from the selected profile."""
    try:
        config = load_user_config(config_path)
        profile_id = _profile_name(config, profile)
        updated = remove_repository(config, profile_id, repository_id)
        persist_config(updated, config_path)
    except Exception as exc:
        _handle_error(exc)
    console.print(f"Removed repository {repository_id} from profile {profile_id}.")


@app.command("discover")
def discover_command(
    root: Annotated[
        Path | None,
        typer.Option("--root", help="Approved directory to scan"),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Profile whose workspace is approved"),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Configuration file"),
    ] = None,
) -> None:
    """Find local Git checkouts. This command does not register or index them."""
    try:
        config = load_user_config(config_path)
        profile_id = _profile_name(config, profile)
        roots = approved_roots(config, profile_id)
        scan_root = root if root is not None else (roots[0] if roots else None)
        if scan_root is None:
            raise CLIConfigError("profile has no approved directory root")
        found = discover_local_repositories(scan_root, approved_roots=roots)
    except Exception as exc:
        _handle_error(exc)
    if not found:
        console.print("No Git repositories found inside the approved root.")
        return
    table = Table(title="Discovered repositories (not registered)")
    table.add_column("Suggested ID")
    table.add_column("Path")
    for item in found:
        table.add_row(item.suggested_id, item.path)
    console.print(table)


@app.command("validate")
def validate_command(
    repository_id: Annotated[str, typer.Argument(help="Repository identifier")],
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Owning profile"),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Configuration file"),
    ] = None,
) -> None:
    """Validate one repository. Remote provider APIs are not called."""
    try:
        config = load_user_config(config_path)
        profile_id = _profile_name(config, profile)
        report = validate_repository(config, profile_id, repository_id)
    except Exception as exc:
        _handle_error(exc)
    console.print(f"Repository: {report.repository_id}")
    console.print(f"Valid definition: {report.ok}")
    console.print(f"Provider API: {report.provider_status}")
    if report.metadata is not None:
        branch = report.metadata.branch or "detached"
        console.print(f"Branch: {branch}")
        console.print(f"HEAD: {report.metadata.head_sha}")
        console.print(f"Dirty: {report.metadata.dirty}")
        console.print(f"Remote URL: {report.metadata.remote_url or ''}")
    if report.protected_patterns:
        console.print("Secret paths stay excluded from indexing.")
    for issue in report.issues:
        console.print(f"{issue.code}: {issue.message}")
    if not report.ok:
        raise typer.Exit(code=1)
