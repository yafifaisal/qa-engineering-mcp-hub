# Architecture overview

The authoritative design is [Canonical architecture](CANONICAL_ARCHITECTURE.md),
and structural rationale belongs in [Architecture decisions](ARCHITECTURE_DECISIONS.md).
This page is a short navigation aid, not a competing architecture.

## Three separate domains

1. The **QA Engineering MCP Hub** is reusable package code and protocol/CLI
   surfaces.
2. A **QA Workspace** contains company-specific approved workflows, suites,
   assertions, policies, mappings, and knowledge.
3. **User configuration** contains machine paths, profiles, connection identities,
   the selected workspace, and credential references — never credential values.

Company content must not enter the public package, and machine configuration must
not be baked into a QA Workspace.

## Dependency direction

```text
MCP / CLI surface
       |
       v
domain services and deterministic policies
       |
       v
provider contracts
       |
       v
provider adapters (future milestones)
```

Tools are thin. They do not call vendor HTTP APIs, provider CLIs, databases, or
Kafka directly. The explicit MCP registry prevents a future scaffold module from
becoming callable merely because a file exists.

## Implemented local surface

The local stdio server registers exactly two tools (`hub_health`,
`hub_capabilities`), one read-only resource (`qa-hub://status`), and one reusable
prompt (`qa_hub_orientation`). All external providers and domain execution paths
remain `NOT_IMPLEMENTED` or `SCAFFOLDED`.

MCP tools are invoked operations. Resources are URI-addressed client context.
Prompts are client-requested message templates. None of the four M00 components
tests an external integration.

Milestone 01 adds versioned local YAML, profiles and connection identities, scoped
credential references, OS-keyring/environment backends, redaction, migration,
setup/profile/integration/config/client CLI commands, and client configuration
generation. These capabilities establish local readiness only. They do not create a
provider adapter or prove network connectivity.

## Why local stdio first?

A local MCP client owns the subprocess lifecycle. Protocol messages use stdout,
so diagnostics must go to stderr. The local server opens no listener. M01 includes
testable OAuth infrastructure but no provider OAuth flow or remote transport.

## Supporting architecture guides

- [Configuration](configuration.md)
- [Authentication](authentication.md)
- [Knowledge engine](knowledge-engine.md)
- [Workflow engine](workflow-engine.md)
- [Evidence engine](evidence-engine.md)
- [Threat model](../security/THREAT_MODEL.md)

Protocol terminology follows the [Model Context Protocol
documentation](https://modelcontextprotocol.io/docs/getting-started/intro).
