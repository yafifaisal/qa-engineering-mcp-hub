# Configuration architecture

Configuration is split between safe framework settings, per-machine user
configuration, and a separate company QA Workspace. See the
[canonical architecture](CANONICAL_ARCHITECTURE.md) for the governing boundary.

## Implemented in Milestone 00

Pydantic Settings validates only these non-secret process settings:

| Environment variable | Default | Constraint |
|---|---|---|
| `QA_MCP_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `QA_MCP_SERVER_NAME` | `QA Engineering MCP Hub` | non-empty text |
| `QA_MCP_TRANSPORT` | `stdio` | `stdio` only |

Unknown environment keys are ignored. There are no password, token, cookie, or
private-key fields. Settings are loaded through `qa_mcp_hub.config.load_settings`.

The native configuration directory comes from `platformdirs`:

- Windows: `%APPDATA%\qa-mcp-hub`;
- macOS: `~/Library/Application Support/qa-mcp-hub`;
- Linux: `${XDG_CONFIG_HOME}/qa-mcp-hub`, or `~/.config/qa-mcp-hub`.

Only macOS execution can be evidenced by the current local environment. Windows
and Linux path tests are deterministic simulations, not live OS verification.

## Implemented in Milestone 01

M01 loads, validates, migrates, and atomically writes one versioned `config.yaml` in
the native user configuration directory. It contains profiles, global connection
records, repository references, workspace references, and execution preferences in
one transaction. A QA Workspace remains a separate directory; its path is a
reference rather than embedded company data.

User configuration can contain:

- named profiles and multiple connection IDs for the same provider;
- cloud or self-managed edition data per connection;
- local repository and QA Workspace paths;
- opaque credential references;
- execution preferences; and
- explicit authorization and approval policy.

Multiple connection IDs may name the same provider. Each connection ID belongs to
at most one profile, which prevents ambiguous credential ownership. Profile and
connection IDs are stable identifiers rather than display names.

Secret values belong in an OS credential store or an explicitly approved process
environment. They do not belong in YAML, TOML, JSON, command arguments, MCP tool
arguments, or workspace files.

## Resolution and validation

Precedence is highest to lowest:

1. an explicit CLI option;
2. an approved environment override;
3. the active profile;
4. user configuration;
5. the application default.

Resolution retains provenance and returns an immutable snapshot. Switching the
active profile changes later resolutions only; an already-running execution keeps
its original configuration. Resolution never merges a raw secret from YAML,
silently selects another profile, or infers a provider edition from an untrusted
URL.

Validation rejects malformed YAML, unsupported versions, invalid enum values,
unknown providers, duplicate connection IDs, ambiguous connection ownership, and
missing profile references. `qa-mcp config validate` performs local validation and
does not contact providers. `qa-mcp config show` presents a redacted view.

## Persistence and migration

Writes use a temporary file in the destination directory, flush it, and atomically
replace the target. Schema migration creates a backup first. If validation or
replacement fails, the previous bytes are restored and the error is reported
without secrets. Re-running setup with an already-valid configuration is safe and
does not create duplicate profile or connection IDs.

The files under [`config/examples/`](../../config/examples/) are sanitized examples
of the accepted contracts. [`templates/qa-workspace/`](../../templates/qa-workspace/)
remains generic workspace input; its later execution capabilities are still
`NOT_IMPLEMENTED`.

References:

- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [platformdirs](https://platformdirs.readthedocs.io/)
- [Configuration examples](../../config/examples/config.example.yaml)
