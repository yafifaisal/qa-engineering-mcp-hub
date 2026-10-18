# Data handling

## Data classes

| Class | Examples | Repository policy |
|---|---|---|
| Public framework | Source, sanitized schemas, generic templates | May be committed after review |
| Machine configuration | Paths, active profile, connection IDs, credential references | Store outside the repository |
| Company QA Workspace | Workflows, assertions, business docs, mappings | Keep in the authorized company workspace |
| Secrets | Tokens, passwords, cookies, private keys, credential-store values | Never store in normal config, workspace, logs, evidence, or MCP arguments |
| Sensitive evidence | Request/response data, database rows, events, logs, screenshots | Future: minimize, redact, encrypt/protect, retain by policy |

## M00 data flow

M00 processes version, server name, log level, transport, and capability metadata.
`hub_health` and `qa-hub://status` can return the configured server name, so it
must remain non-sensitive. M00 does not read provider data, QA Workspace content,
credentials, test output, or evidence, and it has no application-managed
persistence.

Stdio protocol data goes between the configured local client and subprocess.
Diagnostics belong on stderr; secret-shaped values must not be logged even in a
future debug mode.

## Milestone 01 configuration data

User configuration stores profile names, connection metadata, repository and
workspace paths, execution preferences, and opaque credential references. Secret
values are read from an OS keyring or an explicitly named environment variable at
the moment a local command needs them. They are not written to YAML, generated
Codex TOML, native VS Code JSON, logs, or exception text. Removing a local
reference does not revoke the credential at its provider.

## Milestone 02 repository data

Repository registration stores a normalized local path or a remote slug, a
connection id, include/exclude patterns, and an indexing permission. Validation
may read local Git branch, HEAD, origin URL, and dirty state. Origin userinfo is
removed before display. Credential presence is checked for a remote definition
and the value is not printed. File contents are not indexed.

## Configuration and examples

Files under [`config/examples/`](../../config/examples/) contain reference names
such as `QA_MCP_GITHUB_TOKEN`, not credential values. URLs use documentation-only
example hosts. The generic [QA Workspace template](../../templates/qa-workspace/README.md)
must never be populated with real company data inside the public repository.

## Future evidence handling

Before any evidence is persisted or published, the owning milestone must define:

- data minimization and allowed fields;
- secret and PII detection/redaction;
- profile-isolated storage and secure permissions;
- integrity hashes and provenance;
- retention, deletion, and backup behavior;
- publication preview, destination authorization, and idempotency;
- behavior when redaction or integrity verification fails.

A redaction failure invalidates the artifact. Do not publish first and attempt to
remove a leaked secret later.

## Accidental exposure response

Stop publication, revoke or rotate the exposed credential at its source, remove
the data from accessible artifacts and history using the repository owner's
approved incident process, and document impact without copying the secret into a
ticket or chat. Merely deleting a local file does not revoke a credential.

See [credential troubleshooting](../troubleshooting/credentials.md) and the
[threat model](THREAT_MODEL.md).
