# Known limitations

- External provider integrations are not implemented.
- `doctor` checks only local package readiness, not external connections.
- Local stdio only; remote HTTP/OAuth not configured.
- No credential handling, test execution or evidence persistence.
- Authoring environment could not download managed Python/dependencies due DNS access restriction.
- Runtime and MCP protocol integration tests require dependency installation on a connected workstation.
