# Architecture — Milestone 00

Codex/other MCP client -> FastMCP stdio -> typed Python health/capability tools.

The package has no external integrations, secrets, execution runners or remote transport yet.

The planned layers are: `server.py` (protocol), `core` (contracts/policy),
`modules` (QA use cases), `adapters` (provider APIs), `auth` (credentials),
`cli` (onboarding), `runners` (execution), `storage` (evidence).

Milestone 00 deliberately exposes only real implemented tools.

## Why stdio first?

Local clients start and communicate with a subprocess. MCP protocol messages use stdout.
Diagnostics and errors must not print to stdout while serving.

## Why src layout?

A built wheel contains the package independently of the current working directory.

## Security boundary

No provider credential input, remote listening socket, database write, Kafka consume,
or CI/CD trigger is implemented in M00.
