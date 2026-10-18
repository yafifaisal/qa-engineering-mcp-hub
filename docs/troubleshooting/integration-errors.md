# MCP and integration errors

## Server is absent from Codex

Verify absolute paths with `command -v uv`/`pwd` on macOS or Linux, or
`(Get-Command uv).Source`/`(Get-Location).Path` in PowerShell. Run
`uv run qa-mcp --help`, inspect `codex mcp list`, then restart the Codex extension.
Use [Codex registration syntax](../getting-started/codex-vscode.md), not native VS
Code MCP JSON.

## Server starts and appears silent

That is normal for stdio. Do not send ordinary terminal text. The MCP client owns
the subprocess and protocol. Run the real stdio test in
`tests/integration/test_mcp_protocol.py` to distinguish server behavior from client
configuration.

## Unexpected tools are visible

M00 must expose exactly `hub_health` and `hub_capabilities`. Restart the client to
clear old processes, then run `uv run python scripts/structure_audit.py`. A future
tool appearing in discovery is a mandatory architecture violation.

## Provider operation is missing

All provider pages show `NOT_IMPLEMENTED` during M00. The scaffold does not contact
external systems. Consult the [provider index](../providers/README.md) and progress
record; do not interpret a module or configuration file as a working integration.
