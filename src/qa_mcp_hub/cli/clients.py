"""Generate and explicitly install credential-free MCP client configuration.

Purpose: render current Codex TOML and native VS Code JSON stdio contracts.
Milestone: 01
Status: IMPLEMENTED
Ownership: cli.client_config_commands
Dependencies: Standard TOML/JSON contracts and the atomic configuration writer.
Expected tests: Parsing, platform-safe commands, no secrets, and overwrite protection.
"""

from __future__ import annotations

import json
import re
import tomllib
from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console

from qa_mcp_hub.cli.config import fail
from qa_mcp_hub.config.writer import ConfigWriteError, atomic_write_text

app = typer.Typer(help="Generate or install MCP client launch configuration.")
console = Console()


class ClientKind(StrEnum):
    """Client dialects implemented and parser-verified in Milestone 01."""

    codex = "codex"
    vscode = "vscode"


def _toml_string(value: str) -> str:
    """Use JSON's compatible escaping for a TOML basic string."""
    return json.dumps(value, ensure_ascii=True)


def render_codex_toml(*, command: str = "qa-mcp") -> str:
    """Render the documented Codex stdio server table without an env table."""
    document = "\n".join(
        (
            "[mcp_servers.qa_hub]",
            f"command = {_toml_string(command)}",
            'args = ["serve"]',
            "enabled = true",
            "startup_timeout_sec = 10",
            "tool_timeout_sec = 60",
            "",
        )
    )
    parsed = tomllib.loads(document)
    if parsed["mcp_servers"]["qa_hub"]["args"] != ["serve"]:
        raise ValueError("generated Codex configuration failed validation")
    return document


def render_vscode_json(*, command: str = "qa-mcp") -> str:
    """Render a native VS Code stdio server object without credential fields."""
    document = {
        "servers": {
            "qa_hub": {
                "type": "stdio",
                "command": command,
                "args": ["serve"],
            }
        }
    }
    return json.dumps(document, indent=2, sort_keys=False) + "\n"


def render_client_config(client: ClientKind, *, command: str = "qa-mcp") -> str:
    """Render one supported client contract from non-secret launch values only."""
    if not command.strip():
        raise ValueError("launch command cannot be empty")
    if client is ClientKind.codex:
        return render_codex_toml(command=command)
    return render_vscode_json(command=command)


def default_client_path(
    client: ClientKind,
    *,
    home: Path | None = None,
    cwd: Path | None = None,
) -> Path:
    """Return the conventional user/project destination for a client dialect."""
    if client is ClientKind.codex:
        return (home or Path.home()) / ".codex" / "config.toml"
    return (cwd or Path.cwd()) / ".vscode" / "mcp.json"


def _merge_vscode(previous: str, generated: str, *, force: bool) -> str:
    """Merge only ``servers.qa_hub`` while preserving unrelated JSON settings."""
    try:
        current = json.loads(previous)
        desired = json.loads(generated)["servers"]["qa_hub"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ConfigWriteError("existing VS Code client config is invalid") from exc
    if not isinstance(current, dict):
        raise ConfigWriteError("existing VS Code client config must be a JSON object")
    servers = current.setdefault("servers", {})
    if not isinstance(servers, dict):
        raise ConfigWriteError("existing VS Code servers value must be an object")
    existing = servers.get("qa_hub")
    if existing == desired:
        return previous
    if existing is not None and not force:
        raise ConfigWriteError(
            "qa_hub already exists with different settings; pass --force to replace only that entry"
        )
    servers["qa_hub"] = desired
    return json.dumps(current, indent=2, sort_keys=False) + "\n"


_TOML_HEADER = re.compile(r"^\s*\[([^\[\]]+)]\s*(?:#.*)?$")


def _replace_codex_table(previous: str, generated: str) -> str:
    """Replace the plain qa_hub table and its child tables, preserving all others."""
    lines = previous.splitlines(keepends=True)
    start: int | None = None
    end = len(lines)
    for index, line in enumerate(lines):
        match = _TOML_HEADER.match(line.rstrip("\r\n"))
        if match is None:
            continue
        header = match.group(1).strip()
        if start is None and header == "mcp_servers.qa_hub":
            start = index
            continue
        if start is not None and not header.startswith("mcp_servers.qa_hub."):
            end = index
            break
    if start is None:
        raise ConfigWriteError(
            "existing qa_hub uses unsupported TOML syntax; edit it manually"
        )
    prefix = "".join(lines[:start]).rstrip()
    suffix = "".join(lines[end:]).lstrip()
    parts = [part for part in (prefix, generated.rstrip(), suffix) if part]
    return "\n\n".join(parts) + "\n"


def _merge_codex(previous: str, generated: str, *, force: bool) -> str:
    """Merge only ``mcp_servers.qa_hub`` while preserving unrelated TOML."""
    try:
        current = tomllib.loads(previous)
        desired = tomllib.loads(generated)["mcp_servers"]["qa_hub"]
    except (tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise ConfigWriteError("existing Codex client config is invalid") from exc
    servers = current.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ConfigWriteError("existing Codex mcp_servers value must be a table")
    existing = servers.get("qa_hub")
    if existing == desired:
        return previous
    if existing is None:
        separator = "" if not previous.strip() else "\n\n"
        return previous.rstrip() + separator + generated
    if not force:
        raise ConfigWriteError(
            "qa_hub already exists with different settings; pass --force to replace only that table"
        )
    return _replace_codex_table(previous, generated)


def install_client_config(
    client: ClientKind,
    content: str,
    *,
    destination: Path | None = None,
    force: bool = False,
) -> tuple[Path, bool]:
    """Atomically install, returning ``(path, changed)``; identical reruns are safe."""
    target = (destination or default_client_path(client)).expanduser()
    if target.exists():
        try:
            previous = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigWriteError(f"cannot read existing client config: {target}") from exc
        merged = (
            _merge_codex(previous, content, force=force)
            if client is ClientKind.codex
            else _merge_vscode(previous, content, force=force)
        )
        if merged == previous:
            return target, False
        backup = target.with_name(f"{target.name}.bak")
        atomic_write_text(backup, previous)
        try:
            atomic_write_text(target, merged)
        except ConfigWriteError:
            atomic_write_text(target, previous)
            raise
        return target, True
    atomic_write_text(target, content)
    return target, True


@app.command("generate")
def generate_client(
    client: ClientKind = typer.Argument(..., help="Client dialect: codex or vscode."),
    command: str = typer.Option(
        "qa-mcp",
        "--command",
        help="Executable available to the MCP client.",
    ),
) -> None:
    """Print parser-validated client configuration without writing a file."""
    try:
        content = render_client_config(client, command=command)
    except ValueError as exc:
        fail(str(exc))
    typer.echo(content, nl=False)


@app.command("install")
def install_client(
    client: ClientKind = typer.Argument(..., help="Client dialect: codex or vscode."),
    destination: Path | None = typer.Option(
        None,
        "--path",
        help="Destination; defaults to the client's conventional location.",
    ),
    command: str = typer.Option(
        "qa-mcp",
        "--command",
        help="Executable available to the MCP client.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Back up and replace a different existing file.",
    ),
) -> None:
    """Explicitly install generated content with idempotency and overwrite safety."""
    try:
        content = render_client_config(client, command=command)
        target, changed = install_client_config(
            client,
            content,
            destination=destination,
            force=force,
        )
    except (ValueError, ConfigWriteError) as exc:
        fail(str(exc))
    status = "Installed" if changed else "Already current"
    console.print(f"{status}: {target}")
