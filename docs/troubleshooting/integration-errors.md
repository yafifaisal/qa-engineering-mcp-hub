# MCP and integration errors

## Server is absent from Cursor or Codex

Verify absolute paths with `command -v uv`/`pwd` on macOS or Linux, or
`(Get-Command uv).Source`/`(Get-Location).Path` in PowerShell. Run
`uv run qa-mcp --help`. In Cursor, confirm `.cursor/mcp.json` and restart Cursor.
In Codex, inspect `codex mcp list`, then restart the Codex extension.
Use the matching contract in
[Cursor, Codex, and VS Code registration](../getting-started/codex-vscode.md).

## Server starts and appears silent

That is normal for stdio. Do not send ordinary terminal text. The MCP client owns
the subprocess and protocol. Run the real stdio test in
`tests/integration/test_mcp_protocol.py` to distinguish server behavior from client
configuration.

## Unexpected tools are visible

Compare the client's tool list with `qa_mcp_hub.mcp.registry.REGISTERED_TOOL_NAMES`.
Restart the client to clear an old process, then run
`uv run python scripts/structure_audit.py`. A tool outside that set is an
architecture violation.

## Local integration test cannot reach a provider

This is the expected M01 boundary. `qa-mcp integrations test` validates local
configuration and credential presence only and reports network connectivity as
`NOT_IMPLEMENTED`. Consult the [provider index](../providers/README.md) and progress
record; do not interpret a valid connection profile or stored credential as a
working provider adapter.

## Configuration is rejected

Run `qa-mcp config validate` and inspect only the sanitized error. Malformed YAML,
unsupported schema versions, unknown providers, duplicate connection IDs, ambiguous
connection ownership, and missing profile references are intentionally rejected.
Do not remove validation or copy a secret into YAML to work around the error.
