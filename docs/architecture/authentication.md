# Authentication architecture

Status: **SCAFFOLDED; provider authentication is not implemented in Milestone
00.** The M00 tools, resource, and prompt require no provider credential.

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

## Current scaffold

`auth/credential_store.py` defines a future contract, and a small pre-existing
keyring wrapper is retained behind the M00 boundary. The runtime does not import
or register it. This is not proof of complete Keychain, Windows Credential
Manager, Linux Secret Service, environment-store, OAuth, rotation, or expiration
support.

## Future lifecycle requirements

- Bind each reference to a profile, connection, provider, host, and account.
- Request the minimum provider permissions and distinguish cloud/self-managed
  authentication schemes.
- Never echo a secret during setup, diagnostics, rotation, or failure handling.
- Refresh or rotate with bounded retry and without overwriting another profile.
- Delete only after explicit confirmation and record a sanitized audit event.
- Fail closed when a store is unavailable; do not silently fall back to plaintext.

External write capabilities require their own authorization decision in addition
to successful authentication. A valid token is not permission to mutate data.

See [credential troubleshooting](../troubleshooting/credentials.md),
[permissions](../security/permissions.md), and the
[Python keyring documentation](https://keyring.readthedocs.io/).
