# Getting started

QA Engineering MCP Hub is a local Python 3.12+ FastMCP server. Milestone 00
provides two tools, one resource, and one prompt. Milestone 01 adds secure local
setup, configuration, profiles, connection identities, credential references, and
MCP-client configuration generation. Milestone 02 adds provider contracts and
`qa-mcp repositories` for local registration and remote definitions. Milestone 03
adds read-only GitHub, GitLab, Bitbucket, and Jira tools. Milestone 04 adds
read-only Confluence and Google Docs tools. Other provider APIs remain
`NOT_IMPLEMENTED`. Milestone 05 indexes permitted local Git checkouts.
Live provider calls are not claimed.

## Choose your platform

- [Windows 10/11](windows.md) — setup instructions; path behavior is tested by
  simulation, not on a live Windows runner.
- [macOS](macos.md) — local development instructions; consult the
  [progress record](../implementation/PROGRESS.md) for the latest executed gates.
- [Linux](linux.md) — setup instructions; path behavior is tested by simulation,
  not on a live Linux runner.
- [Cursor, Codex, and VS Code registration](codex-vscode.md) — keeps Cursor
  JSON, Codex TOML, and native VS Code JSON as separate contracts.

## What works through Milestone 02

| Surface | Implemented item |
|---|---|
| MCP tools | `hub_health`, `hub_capabilities` |
| MCP resource | `qa-hub://status` |
| MCP prompt | `qa_hub_orientation` |
| M00 CLI | `serve`, `doctor`, `capabilities`, plus `--help` and `--version` |
| M01 CLI | `setup`; `profiles` (6 commands); `integrations` (6); `config` (2); `clients` (2) |
| M02 CLI | `repositories` `add`, `list`, `remove`, `discover`, and `validate` |

There are 25 leaf commands in total: three M00 commands, seventeen M01 commands,
and five repository commands. `repositories discover` does not register matches.
`repositories validate` can read local Git metadata; a remote definition reports
provider API status `NOT_IMPLEMENTED`.
Use `qa-mcp <group> --help` for exact options. `hub_health` reports readiness of
the local process only. Likewise, `integrations test` validates local connection
configuration and credential presence; it reports provider network connectivity as
`NOT_IMPLEMENTED`.

## Common setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git,
then from the repository root run:

```sh
uv python install 3.12
uv sync --frozen
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp capabilities
uv run qa-mcp setup
```

The setup wizard can create or reuse the native user configuration safely. It
stores only credential references in YAML. Secret values remain in an OS keyring or
an explicitly named environment variable.

After setup, inspect the local state without exposing credentials:

```sh
uv run qa-mcp profiles list
uv run qa-mcp integrations list
uv run qa-mcp config validate
uv run qa-mcp config show
uv run qa-mcp clients generate --help
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
- [Authentication boundaries](../architecture/authentication.md)
- [Security permissions](../security/permissions.md)
- [Troubleshooting](../troubleshooting/README.md)
- [Official Codex MCP documentation](https://developers.openai.com/codex/mcp)
