# Permissions and authorization

Milestone 00 is local and read-only. Authentication and permission to reach a
process are different from authorization to perform a QA operation; future
provider writes require a separate explicit decision.

## M00 permission matrix

| Component | Reads | Writes / external effects |
|---|---|---|
| `qa-mcp --help` | Packaged CLI metadata | None |
| `qa-mcp doctor` | Validated non-secret environment settings and native config path | None |
| `qa-mcp capabilities` | Static local capability catalog | None |
| `hub_health` | Version and non-secret local settings | None |
| `hub_capabilities` | Static local capability catalog | None |
| `qa-hub://status` | Same local health/capability facts | None |
| `qa_hub_orientation` | Static prompt text | None |

`qa-mcp serve` starts a local stdio subprocess. It does not listen on a port,
read a repository, invoke a provider, execute a test suite, query a database,
consume Kafka, trigger CI, or publish evidence.

## Future authorization defaults

- Deny access until a profile, connection, workspace, and requested capability
  are explicitly configured.
- Scope file access to normalized allowlisted roots.
- Scope outbound traffic to the selected provider scheme and host.
- Resolve credentials only after authorization, never from an MCP argument.
- Prefer read-only provider scopes and read-only database accounts.
- Restrict suite execution, SQL, topics, workflows, and CI jobs to registries.
- Require preview and explicit user approval for provider writes, CI triggers,
  imports, overwrites, and evidence publication.
- Keep approval narrow, time-bound, profile-bound, and operation-specific.

An API token with broad permissions does not broaden the Hub's authorized scope.
The Hub must still deny any operation not enabled by its policy.

## Client configuration

Use absolute executable/project paths and a trusted checkout. Do not pass secrets
in client `args` or commit them to Codex TOML or VS Code JSON. Codex registration
is described in [Codex and VS Code setup](../getting-started/codex-vscode.md).

Provider-specific least-privilege requirements will be documented under
[`docs/providers/`](../providers/) while each integration remains
`NOT_IMPLEMENTED` in M00.
