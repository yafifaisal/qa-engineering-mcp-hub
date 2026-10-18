# Getting started

QA Engineering MCP Hub is a local Python 3.12+ FastMCP server. Milestone 11
packages that server as a Community Edition wheel. Install from a checkout with
uv, or install a wheel you built locally. The package is not on PyPI. Live
provider calls are not claimed. Platform guides below say which operating
systems were actually executed.

## Choose your platform

- [Windows 10/11](windows.md) — setup instructions. Native Windows CI has not
  been observed for this milestone.
- [macOS](macos.md) — local development instructions. Consult the
  [progress record](../implementation/PROGRESS.md) for the latest executed gates.
- [Linux](linux.md) — setup instructions. Native Linux CI has not been observed
  for this milestone.
- [Cursor, Codex, and VS Code registration](codex-vscode.md) — keeps Cursor
  JSON, Codex TOML, and native VS Code JSON as separate contracts.

## Install from a checkout

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git,
then from the repository root run:

```sh
uv python install 3.12
uv sync --frozen
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp setup --non-interactive --profile default
uv run qa-mcp profiles list
uv run qa-mcp integrations list
uv run qa-mcp repositories list
uv run qa-mcp workflows list
uv run qa-mcp clients install --help
```

Build a wheel without publishing it:

```sh
uv run python scripts/build_package.py
uvx --from dist/qa_engineering_mcp_hub-0.1.0-py3-none-any.whl qa-mcp --version
```

The setup wizard stores credential references in YAML. Secret values stay in an
OS keyring or an explicitly named environment variable. If the keyring backend
is unavailable, choose an environment reference. The application does not write
a plaintext credential file.

`qa-mcp workflows list` prints registered workflow documents and does not run
them. `qa-mcp integrations test` checks credential presence and reports provider
network connectivity as `NOT_IMPLEMENTED`.

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
