# Configuration architecture

Configuration is split between safe framework settings, future per-machine user
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

## Scaffolded for later milestones

The files under [`config/examples/`](../../config/examples/) and
[`templates/qa-workspace/`](../../templates/qa-workspace/) define reviewable
formats, but the M00 runtime does not load or write them. Their presence does not
implement profiles, repositories, connections, migrations, or a setup wizard.

Future user configuration will contain:

- named profiles and multiple connection IDs for the same provider;
- cloud or self-managed edition data per connection;
- local repository and QA Workspace paths;
- opaque credential references;
- explicit authorization and approval policy.

Secret values belong in an OS credential store or an explicitly approved process
environment. They do not belong in YAML, TOML, JSON, command arguments, MCP tool
arguments, or workspace files.

## Resolution rules for future implementation

Future precedence must be deterministic and documented before activation. It must
never merge a raw secret from ordinary configuration, silently fall back to a
different profile, or infer a provider edition from an untrusted URL. Invalid
schemas and unsupported newer versions must fail closed with a clear error.

References:

- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [platformdirs](https://platformdirs.readthedocs.io/)
- [Configuration examples](../../config/examples/config.example.yaml)
