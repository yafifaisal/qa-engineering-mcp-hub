# Permissions and authorization

Milestone 00 is local and read-only. Authentication and permission to reach a
process are different from authorization to perform a QA operation; future
provider writes require a separate explicit decision.

## M00 permission matrix

| Component | Reads | Writes / external effects |
|---|---|---|
| `qa-mcp --help` | Packaged CLI metadata | None |
| `qa-mcp doctor` | Validated non-secret environment settings, native config path, local YAML validity, and keyring backend name | None; no secret is read |
| `qa-mcp capabilities` | Static local capability catalog | None |
| `hub_health` | Version and non-secret local settings | None |
| `hub_capabilities` | Static local capability catalog | None |
| `qa-hub://status` | Same local health/capability facts | None |
| `qa_hub_orientation` | Static prompt text | None |

`qa-mcp serve` starts a local stdio subprocess. It does not listen on a port,
read a repository, invoke a provider, execute a test suite, query a database,
consume Kafka, trigger CI, or publish evidence.

## Milestone 01 local permissions

| Command | Local effect | Explicitly not allowed |
|---|---|---|
| `qa-mcp setup` | Create or reuse a profile and optional workspace path | Writing a secret into YAML |
| `qa-mcp profiles` | Create, show, select, edit, or remove an empty profile | Deleting a profile that still owns integrations |
| `qa-mcp integrations add/list` | Store or display connection metadata | Contacting the provider |
| `qa-mcp integrations auth` | Store a keyring value or record an environment/OAuth reference | Printing the value or starting a provider OAuth flow |
| `qa-mcp integrations test` | Check configuration and credential presence | Treating presence as network connectivity |
| `qa-mcp integrations rotate/remove` | Replace or delete the exact scoped keyring value | Revoking the credential at the provider |
| `qa-mcp config show/validate` | Redacted display and strict local validation | Provider calls |
| `qa-mcp clients generate` | Print Codex TOML or VS Code JSON | Embedding provider credentials |
| `qa-mcp clients install` | Merge `qa_hub` into an explicit destination, with backup | Replacing unrelated client settings |

## Milestone 02 repository permissions

| Command | Local effect | Explicitly not allowed |
|---|---|---|
| `qa-mcp repositories add` | Store a local path or remote definition on one profile | Registering a path outside that profile's workspace |
| `qa-mcp repositories list/remove` | Show or delete only the selected profile's repositories | Reading another profile's repository list |
| `qa-mcp repositories discover` | List Git checkouts inside the approved workspace | Following a symlink outside that workspace or registering matches |
| `qa-mcp repositories validate` | Read local Git metadata or check that a credential reference resolves | Calling a Git host API or printing a credential value |

Indexing permission is stored only. File contents are not indexed in this milestone.
Mandatory secret-path patterns stay excluded from any later indexing plan.

## Future authorization defaults

- Deny access until a profile, connection, workspace, and requested capability
  are explicitly configured.
- Scope file access to normalized allowlisted roots.
- Scope outbound traffic to the selected provider scheme and host.
- Resolve credentials only after authorization, never from an MCP argument.
- Prefer read-only provider scopes and read-only database accounts.
- Git and Jira MCP tools send only GET requests, plus the Jira search POST that
  reads issues. They do not accept a token argument.
- Confluence search is limited to space keys supplied for that call. Google
  Drive queries are limited to Google Docs in the user corpus. Document text
  cannot change tool permissions.
- Restrict suite execution, SQL, topics, workflows, and CI jobs to registries.
- Require preview and explicit user approval for provider writes, CI triggers,
  imports, overwrites, and evidence publication.
- Keep approval narrow, time-bound, profile-bound, and operation-specific.

An API token with broad permissions does not broaden the Hub's authorized scope.
The Hub must still deny any operation not enabled by its policy.

## Client configuration

Use absolute executable/project paths and a trusted checkout. Do not pass secrets
in client `args` or commit them to Cursor JSON, Codex TOML, or VS Code JSON.
Registration for each client is described in
[Cursor, Codex, and VS Code setup](../getting-started/codex-vscode.md).

Provider-specific least-privilege requirements will be documented under
[`docs/providers/`](../providers/) while each integration remains
`NOT_IMPLEMENTED` in M00.
