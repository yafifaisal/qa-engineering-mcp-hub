# macOS setup

Milestone 00 is developed locally on macOS. A statement that it is
`OFFLINE_VERIFIED` still requires recorded passing commands in the
[progress document](../implementation/PROGRESS.md); file existence is not proof.

## Prerequisites

Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Homebrew users may run:

```sh
brew install git uv
uv --version
uv python install 3.12
```

## Install and check Milestone 00

From the repository root:

```sh
uv sync --locked
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp capabilities
uv run pytest -q
```

The native user configuration directory is
`~/Library/Application Support/qa-mcp-hub`. Profiles, credential persistence,
and provider connections remain future work.

## Register with Codex

Resolve absolute paths:

```sh
command -v uv
pwd
```

Substitute them in the registration command:

```sh
codex mcp add qa-hub -- /absolute/path/to/uv run --project /absolute/path/to/qa-engineering-mcp-hub qa-mcp serve
codex mcp list
```

Restart the Codex IDE extension after changing MCP configuration. Full TOML and
client verification guidance is in [Codex and VS Code registration](codex-vscode.md).

## macOS-specific cautions

- Keep company QA Workspace data outside the public framework checkout.
- macOS Keychain integration is scaffolded for a future milestone; it is not part
  of the M00 runtime.
- Do not use an ordinary terminal interaction to test stdio. Use the MCP protocol
  tests or a configured client.

For setup failures, see [Troubleshooting](../troubleshooting/README.md).
