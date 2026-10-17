# QA Engineering MCP Hub — Milestone 00

Cross-platform Python/FastMCP foundation. No external integrations yet.

## Prerequisites

Install `uv` from https://docs.astral.sh/uv/. On macOS use `brew install uv`;
on Windows use `winget install --id astral-sh.uv -e`.

## Setup

```sh
uv sync
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp capabilities
```

## Start MCP (stdio)

```sh
uv run qa-mcp serve
```

Stdio MCP servers wait for a client and may appear silent. Do not send ordinary text to stdin.

## Codex integration

Get the absolute path to `uv` and the project directory.
On macOS/Linux: `command -v uv` and `pwd`.
On PowerShell: `(Get-Command uv).Source` and `(Get-Location).Path`.

Then (replace placeholders):

```
codex mcp add qa-hub -- /ABSOLUTE/UV/PATH run --project /ABSOLUTE/PROJECT/PATH qa-mcp serve
codex mcp list
```

In Windows, use native Windows paths and `uv.exe` returned by PowerShell.

## Validate

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
uv build
```

A lockfile is created by the first successful `uv lock` or `uv sync` with network access.
Do not run `uv sync --frozen` before it exists.

## What exists?

- `hub_health` and `hub_capabilities` MCP tools.
- `qa-mcp doctor` and `qa-mcp capabilities` local CLI.
- Pydantic settings and cross-platform configuration directory resolution.

## What does not exist?

Jira, Git providers, tests, Kafka, databases, tokens, remote hosting, OAuth,
evidence, real integration diagnostics. These belong to later milestones.

## Beginner explanation

`pyproject.toml` describes the installable package and tools.
`uv.lock` freezes dependency resolution once created.
`src/qa_mcp_hub/server.py` exposes functions to MCP clients.
`src/qa_mcp_hub/cli.py` handles human terminal commands.
`src/qa_mcp_hub/config.py` validates non-secret settings.
`tests/` verifies local behavior and protocol calls.
`docs/` keeps agent and human decisions traceable.
