# Windows 10/11 setup

Verification status: **OFFLINE_VERIFIED (simulated paths only)**. The repository
tests Windows path selection from another operating system. Milestone 00 has not
been `LIVE_VERIFIED` on a native Windows runner.

## Prerequisites

Use PowerShell and install Git plus
[uv using an official method](https://docs.astral.sh/uv/getting-started/installation/).
One supported package-manager option is:

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
uv --version
uv python install 3.12
```

Clone or extract the repository to a normal user-writable directory. Avoid
copying tokens or company QA assets into the public framework checkout.

## Install and check Milestone 00

From the repository root:

```powershell
uv sync --frozen
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp capabilities
uv run pytest -q
```

The native user configuration directory resolves beneath
`%APPDATA%\qa-mcp-hub`. Configuration-file loading, profiles, credentials, and
provider connections are future work; the directory path alone does not imply
those features work.

## Register with Codex

Find absolute paths first:

```powershell
(Get-Command uv).Source
(Get-Location).Path
```

Then substitute those values:

```powershell
codex mcp add qa-hub -- "C:\absolute\path\to\uv.exe" run --project "C:\absolute\path\to\qa-engineering-mcp-hub" qa-mcp serve
codex mcp list
```

Codex CLI and the Codex IDE extension share Codex configuration. For manual TOML,
use forward-slash paths such as `C:/Users/name/project` or escape each backslash.
See [Codex and VS Code registration](codex-vscode.md).

## Windows-specific cautions

- Keep `uv.exe`, the project, and any future QA Workspace on allowlisted absolute
  paths.
- Windows Credential Manager support is future Milestone 01 work. Do not infer
  support from the installed `keyring` package.
- If PowerShell cannot find a newly installed executable, open a new terminal and
  rerun `Get-Command uv` or `Get-Command codex`.
- A silent `qa-mcp serve` process is normal for stdio. Use `codex mcp list` and
  the client MCP view instead of sending text to the process.

For setup failures, see [Troubleshooting](../troubleshooting/README.md).
