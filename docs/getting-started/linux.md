# Linux setup

Verification status: **OFFLINE_VERIFIED (simulated paths only)**. The repository
tests Linux path selection from another operating system. Milestones 00 and 01 have not
been `LIVE_VERIFIED` on a native Linux runner.

## Prerequisites

Install Git and [uv using the official installation
instructions](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
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
uv run pytest -q
```

The native user configuration directory is
`${XDG_CONFIG_HOME}/qa-mcp-hub` when `XDG_CONFIG_HOME` is set, otherwise
`~/.config/qa-mcp-hub`. M01 stores versioned non-secret YAML there. Credential
values may come from an explicitly named environment variable or a usable Linux
keyring backend; no plaintext fallback exists.

## Register with Codex

Resolve absolute paths, then register the server:

```sh
command -v uv
pwd
codex mcp add qa_hub -- /absolute/path/to/uv run --project /absolute/path/to/qa-engineering-mcp-hub qa-mcp serve
codex mcp list
```

See [Codex and VS Code registration](codex-vscode.md) before editing client files
manually.

## Linux-specific cautions

- Headless systems may not have a usable Secret Service/keyring session. M01
  detects this and fails closed; use an explicitly named environment reference when
  policy allows it.
- Do not run the stdio process as a public network service. Remote transport and
  remote authentication are not implemented.
- Native Linux installation and CI evidence are still required before claiming
  `LIVE_VERIFIED` Linux support.

For setup failures, see [Troubleshooting](../troubleshooting/README.md).
