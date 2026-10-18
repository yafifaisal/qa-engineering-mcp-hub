# Register the local MCP server with Codex or native VS Code

The hub uses local stdio and does not expose an HTTP endpoint. M01 can generate or
install client launch configuration, but it never embeds provider credentials.

## Codex CLI and Codex IDE extension

Codex CLI and the Codex IDE extension share Codex MCP configuration. The user
file is normally `~/.codex/config.toml`; a trusted project may also provide
`.codex/config.toml`. The preferred registration path is the CLI:

```sh
codex mcp add qa_hub -- /absolute/path/to/uv run --project /absolute/path/to/qa-engineering-mcp-hub qa-mcp serve
codex mcp list
```

In the Codex terminal UI, `/mcp` shows configured servers. In the IDE extension,
open the settings gear, choose **MCP servers**, add an **STDIO** server, save, and
restart the extension.

Equivalent manual TOML is:

```toml
[mcp_servers.qa_hub]
command = "/absolute/path/to/uv"
args = [
  "run",
  "--project",
  "/absolute/path/to/qa-engineering-mcp-hub",
  "qa-mcp",
  "serve",
]
enabled = true
startup_timeout_sec = 10
tool_timeout_sec = 60
```

On Windows, use forward slashes or escaped backslashes in TOML. Do not put tokens
in `args` or an inline environment table. A sanitized copy is available at
[`config/examples/codex.example.toml`](../../config/examples/codex.example.toml).

The authoritative syntax is the [official Codex MCP
documentation](https://developers.openai.com/codex/mcp).

## Native VS Code/Copilot MCP configuration

Native VS Code MCP support is a different client and configuration dialect; it is
not the canonical configuration for the Codex extension. One VS Code workspace
format uses `.vscode/mcp.json` and a `servers` object:

```json
{
  "servers": {
    "qa_hub": {
      "type": "stdio",
      "command": "/absolute/path/to/uv",
      "args": [
        "run",
        "--project",
        "/absolute/path/to/qa-engineering-mcp-hub",
        "qa-mcp",
        "serve"
      ]
    }
  }
}
```

VS Code schemas and supported locations can change independently. Check the
[official VS Code MCP documentation](https://code.visualstudio.com/docs/agent-customization/mcp-servers)
for the installed version. Do not paste this JSON into Codex `config.toml`.

## Generate or install with qa-mcp

M01 provides parser-checked generation for both formats:

```sh
qa-mcp clients generate codex
qa-mcp clients generate vscode
qa-mcp clients install --help
```

Generation is side-effect free. Installation merges the `qa_hub` entry while
preserving unrelated client settings. It is idempotent, refuses to replace a
different `qa_hub` entry unless `--force` is explicit, and creates a backup before
replacement. Use `--command` when `qa-mcp` is not on the MCP client's PATH.
Generated content contains only the local launch command; provider tokens remain in
the configured credential backend.

## Verify the MCP surface

After restarting the client, verify that the server starts and that exactly these
components are discoverable through protocol tests:

- tools: `hub_health`, `hub_capabilities`;
- resource: `qa-hub://status`;
- prompt: `qa_hub_orientation`.

Client interfaces do not all display resources and prompts in the same way. Do
not interpret a missing UI panel as protocol proof; use the repository MCP tests.
No Git, Jira, document, API-runner, database, Kafka, CI/CD, or test-management
tool should be exposed through Milestone 01.

See [integration troubleshooting](../troubleshooting/integration-errors.md) if
the server is absent or exits early.
