# macOS setup

Local quality gates for Milestone 11 were executed on macOS. That verifies the
package, tests, and wheel install on this machine. It does not verify a hosted
macOS runner, and it does not make any provider LIVE_VERIFIED. Consult the
[progress record](../implementation/PROGRESS.md).

## Prerequisites

Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Homebrew users may run:

```sh
brew install git uv
uv --version
uv python install 3.12
```

## Install and check

From the repository root:

```sh
uv sync --frozen
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp capabilities
uv run qa-mcp setup
uv run qa-mcp config validate
uv run qa-mcp workflows list
uv run python scripts/build_package.py
```

The native user configuration directory is
`~/Library/Application Support/qa-mcp-hub`. M01 stores versioned non-secret YAML
there. A `keyring` credential reference can use macOS Keychain when the installed
keyring backend is usable; otherwise the command fails closed with an actionable
error. Never place the secret in YAML.

## Register with Codex

Resolve absolute paths:

```sh
command -v uv
pwd
```

Substitute them in the registration command:

```sh
codex mcp add qa_hub -- /absolute/path/to/uv run --project /absolute/path/to/qa-engineering-mcp-hub qa-mcp serve
codex mcp list
```

Restart the Codex IDE extension after changing MCP configuration. Full TOML and
client verification guidance is in [Codex and VS Code registration](codex-vscode.md).

## macOS-specific cautions

- Keep company QA Workspace data outside the public framework checkout.
- Mocked credential-store tests prove resolver behavior, not a live Keychain round
  trip. Consult the progress record for current native backend evidence.
- Do not use an ordinary terminal interaction to test stdio. Use the MCP protocol
  tests or a configured client.

For setup failures, see [Troubleshooting](../troubleshooting/README.md).
