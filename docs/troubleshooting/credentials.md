# Credential troubleshooting

Milestone 01 resolves credentials locally from an OS keyring or an explicitly named
environment variable. No MCP tool accepts a raw credential, and configuration files
contain references only.

Start with:

```sh
qa-mcp config validate
qa-mcp profiles show
qa-mcp integrations list
qa-mcp integrations test --help
```

`integrations test` checks local connection validity and credential presence. A
`NOT_IMPLEMENTED` network result means the command did not call the provider.
That remains true after an adapter exists: this command does not open a socket.

For a keyring failure, capture only the backend name and sanitized exception. Check
that the OS keyring session is unlocked and usable and that profile, connection,
provider, host, account, and reference IDs match. The application will not silently
fall back to a plaintext file. On a headless Linux host, use a deliberately named
environment reference only when policy permits it.

Never print the returned value or put it in YAML, Codex arguments, native VS Code
JSON, source, logs, or a QA Workspace. Rotate a suspected leaked credential at the
provider as well as locally; removing a local reference is not revocation.

See [authentication architecture](../architecture/authentication.md) and
[data handling](../security/data-handling.md).
