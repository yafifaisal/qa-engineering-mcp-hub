# Credential troubleshooting

Provider credential resolution is not implemented in Milestone 00. The runtime has
no token/password setting, and no MCP tool accepts a credential. Configuration
examples contain reference names only.

If `qa-mcp doctor` works but a future credential command described elsewhere is
absent, that is the expected M00 boundary, not proof of a broken provider token.
Do not work around it by writing a token into YAML, Codex arguments, VS Code JSON,
source, logs, or a QA Workspace.

For future keyring failures, capture only the backend name and sanitized exception.
Check that the OS keyring session is available and that profile/connection/reference
IDs match. Never print the returned value. Rotate a suspected leaked credential at
the provider; removing a local reference is not revocation.

See [authentication architecture](../architecture/authentication.md) and
[data handling](../security/data-handling.md).
