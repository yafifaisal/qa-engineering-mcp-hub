# Windows 10/11 setup

Verification status: **OFFLINE_VERIFIED (simulated paths only)**. Native Windows
10/11 execution of this milestone was not observed. The checked-in CI workflow
names `windows-latest`, and that workflow has not run in this session.

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

## Install and check

From the repository root:

```powershell
uv sync --frozen
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp capabilities
uv run qa-mcp setup
uv run qa-mcp config validate
uv run qa-mcp workflows list
uv run python scripts/build_package.py
```

The native user configuration directory resolves beneath
`%APPDATA%\qa-mcp-hub`. M01 stores versioned non-secret YAML there. A `keyring`
reference can use Windows Credential Manager when a compatible backend is usable;
otherwise the command fails closed. No token is written to YAML.

## Register with Codex

Find absolute paths first:

```powershell
(Get-Command uv).Source
(Get-Location).Path
```

Then substitute those values:

```powershell
codex mcp add qa_hub -- "C:\absolute\path\to\uv.exe" run --project "C:\absolute\path\to\qa-engineering-mcp-hub" qa-mcp serve
codex mcp list
```

Codex CLI and the Codex IDE extension share Codex configuration. For manual TOML,
use forward-slash paths such as `C:/Users/name/project` or escape each backslash.
See [Codex and VS Code registration](codex-vscode.md).

## Windows-specific cautions

- Keep `uv.exe`, the project, and any future QA Workspace on allowlisted absolute
  paths.
- The installed `keyring` package alone does not prove a working Credential Manager
  round trip. Consult the progress record for native backend evidence.
- If PowerShell cannot find a newly installed executable, open a new terminal and
  rerun `Get-Command uv` or `Get-Command codex`.
- A silent `qa-mcp serve` process is normal for stdio. Use `codex mcp list` and
  the client MCP view instead of sending text to the process.

For setup failures, see [Troubleshooting](../troubleshooting/README.md).
