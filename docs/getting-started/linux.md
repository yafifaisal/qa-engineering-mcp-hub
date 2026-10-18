# Linux setup

Verification status: **OFFLINE_VERIFIED (simulated paths only)**. The repository
tests Linux path selection from another operating system. Milestone 00 has not
been `LIVE_VERIFIED` on a native Linux runner.

## Prerequisites

Install Git and [uv using the official installation
instructions](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv --version
uv python install 3.12
```

## Install and check Milestone 00

From the repository root:

```sh
uv sync --frozen
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp capabilities
uv run pytest -q
```

The native user configuration directory is
`${XDG_CONFIG_HOME}/qa-mcp-hub` when `XDG_CONFIG_HOME` is set, otherwise
`~/.config/qa-mcp-hub`. Profiles, credentials, and providers remain future work.

## Register with Codex

Resolve absolute paths, then register the server:

```sh
command -v uv
pwd
codex mcp add qa-hub -- /absolute/path/to/uv run --project /absolute/path/to/qa-engineering-mcp-hub qa-mcp serve
codex mcp list
```

See [Codex and VS Code registration](codex-vscode.md) before editing client files
manually.

## Linux-specific cautions

- Headless systems may not have a usable Secret Service/keyring session. Keyring
  behavior is future Milestone 01 work and is not verified by M00.
- Do not run the stdio process as a public network service. Remote transport and
  remote authentication are not implemented.
- Native Linux installation and CI evidence are still required before claiming
  `LIVE_VERIFIED` Linux support.

For setup failures, see [Troubleshooting](../troubleshooting/README.md).
