# Authentication architecture

Status: **M01 local credential infrastructure is implemented; provider
authentication remains NOT_IMPLEMENTED.** The MCP tools, resource, and prompt do
not require a provider credential.

## Credential boundary

Normal configuration stores an opaque reference such as an approved environment
variable name or keyring record ID. The adapter resolves a credential only after
the active profile, provider connection, and requested capability are authorized.
Raw credentials must never be accepted as an MCP argument.

```text
MCP tool -> service authorization -> connection -> credential reference
                                                -> approved store lookup
                                                -> provider adapter
```

Tool results, logs, exceptions, evidence, and audit records must redact
authorization headers, cookies, tokens, passwords, and private keys.

## Credential stores

M01 provides two explicit backends:

- `keyring` delegates storage to Python keyring and therefore to a usable Windows
  Credential Manager, macOS Keychain, or Linux keyring backend;
- `environment` reads the exact configured environment-variable name and is
  read-only—the value is never copied to YAML.

A missing or unusable keyring backend produces an actionable error. It never
silently falls back to plaintext, an environment variable, or another profile.
Native backend behavior must be separately verified on each claimed operating
system; mocked stores are offline test evidence only.

## Scope and lifecycle

Every lookup is bound to profile, connection, provider, host, and account. The
stored reference is opaque and non-secret. Missing or expired metadata fails closed
before any future provider operation.

M01 authentication contracts describe API tokens, personal access tokens, and
OAuth credentials. OAuth state, PKCE, callback, and token-lifecycle types can be
tested locally, but no provider authorization endpoint, exchange, refresh, or
revocation flow is implemented or claimed.

Local lifecycle behavior follows these rules:

- Bind each reference to a profile, connection, provider, host, and account.
- Request the minimum provider permissions and distinguish cloud/self-managed
  authentication schemes.
- Never echo a secret during setup, diagnostics, rotation, or failure handling.
- Refresh or rotate with bounded retry and without overwriting another profile.
- Delete only after explicit confirmation and record a sanitized audit event.
- Fail closed when a store is unavailable; do not silently fall back to plaintext.

`qa-mcp integrations auth`, `test`, `rotate`, and `remove` operate on local
configuration and credential storage. `test` validates the selected connection and
credential presence; its provider network result remains `NOT_IMPLEMENTED` until
the provider adapter exists. Removing a local value does not revoke it at the
provider.

External write capabilities require their own authorization decision in addition
to successful authentication. A valid token is not permission to mutate data.

See [credential troubleshooting](../troubleshooting/credentials.md),
[permissions](../security/permissions.md), and the
[Python keyring documentation](https://keyring.readthedocs.io/).
