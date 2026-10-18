# Getting started

QA Engineering MCP Hub Milestone 00 is a local Python 3.12+ FastMCP server. It
implements local introspection only: two tools, one resource, one prompt, and four
CLI behaviors. Every external provider remains `NOT_IMPLEMENTED`.

## Choose your platform

- [Windows 10/11](windows.md) — setup instructions; path behavior is tested by
  simulation, not on a live Windows runner.
- [macOS](macos.md) — local development instructions; consult the
  [progress record](../implementation/PROGRESS.md) for the latest executed gates.
- [Linux](linux.md) — setup instructions; path behavior is tested by simulation,
  not on a live Linux runner.
- [Codex and VS Code registration](codex-vscode.md) — keeps Codex TOML/CLI
  configuration separate from native VS Code JSON.

## What Milestone 00 provides

| Surface | Implemented item |
|---|---|
| MCP tools | `hub_health`, `hub_capabilities` |
| MCP resource | `qa-hub://status` |
| MCP prompt | `qa_hub_orientation` |
| CLI | `qa-mcp --help`, `serve`, `doctor`, `capabilities` |

`hub_health` reports readiness of the local process only. It does not test Jira,
Git, a database, Kafka, a CI system, or any other future integration.

## Common setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git,
then from the repository root run:

```sh
uv python install 3.12
uv sync --locked
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp capabilities
```

Start the stdio server only through an MCP client:

```sh
uv run qa-mcp serve
```

An stdio server waits for protocol messages and normally appears silent. Do not
type ordinary text into its stdin.

## Next reading

- [Canonical architecture](../architecture/CANONICAL_ARCHITECTURE.md)
- [Configuration boundaries](../architecture/configuration.md)
- [Security permissions](../security/permissions.md)
- [Troubleshooting](../troubleshooting/README.md)
- [Official Codex MCP documentation](https://developers.openai.com/codex/mcp)
