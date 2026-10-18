# Threat model

Status: Milestone 00 local stdio scope plus Milestone 01 local configuration and
credential references. Provider calls remain unimplemented.

## Scope and assets

M00 protects the integrity of the local MCP process, protocol output, package
configuration, capability claims, and the user's workstation context. It exposes
two local tools, one resource, and one prompt. It has no provider credentials,
external provider calls, workflow execution, evidence persistence, or remote
listener.

Future milestones add higher-value assets: credential references and secret-store
values, company repositories/documents, profiles, QA Workspace assets, database
and Kafka observations, CI/CD controls, test-management records, and evidence.

## Trust boundaries

```text
MCP client --stdio--> local QA Hub process
                         |
                         +--> process environment / native config path
                         +--> OS keyring or named environment variable

Future only:
local process --> authorized provider
local process --> allowlisted repository / QA Workspace / evidence storage
```

The client, environment, repository content, tickets, documents, provider
responses, and imported test data may all contain untrusted input. Provider text
is data, not agent instruction.

## Threats and control status

| Threat | Required control | Status |
|---|---|---|
| Accidental capability overclaim | Fixed capability catalog and exact registry | Implemented |
| Future tool exposed by file discovery | Explicit M00 registration allowlist | Implemented |
| Protocol corruption through stdout logging | Stdio-only entry point; diagnostics use stderr | Implemented boundary |
| Malicious environment setting | Typed settings and restricted transport/log-level values | Implemented |
| Plaintext credential disclosure | Opaque references, redaction, and no plaintext fallback | Implemented for local M01 configuration |
| Prompt injection from external content | Treat content as untrusted and preserve sources | Future enforcement; no ingestion in M00 |
| Path traversal or unauthorized repository access | Normalize and enforce configured roots | SCAFFOLDED |
| SSRF or redirect to an unapproved host | Connection scheme/host allowlist and safe redirects | SCAFFOLDED |
| Shell or process injection | Registered argument arrays, fixed executables, bounded environment | SCAFFOLDED |
| SQL injection or database mutation | Registered parameterized SELECT-only assertions plus read-only account | SCAFFOLDED |
| Kafka consumer disruption | Approved topics, bounded reads, no production offset commits | SCAFFOLDED |
| Cross-profile credential leak | Profile-bound credential scope and one connection owner | Implemented for local credential lookup; provider adapters remain scaffolded |
| Unauthorized provider write or CI trigger | Deny by default, preview, explicit approval, idempotency | SCAFFOLDED |
| Evidence tampering or secret leakage | Hash manifests, redaction, secure permissions, retention | SCAFFOLDED |
| Resource exhaustion | Time, row, byte, concurrency, and pagination limits | SCAFFOLDED |

## M00 residual risks

- A local user who can modify the checkout or selected Python environment can
  alter the server. Package and environment integrity remain workstation duties.
- A client can repeatedly call local introspection components; M00 has no remote
  rate limiter because it opens no network listener.
- The server name comes from a local environment variable and is returned by
  health/status. Do not put sensitive data in it.
- Dependency and supply-chain risk is reduced by `uv.lock`, not eliminated.
- Container files are optional scaffolding and are not evidence of a hardened
  production deployment.

## Security acceptance for future milestones

A future integration must have threat-specific tests, least-privilege provider
documentation, error redaction, authorization behavior, timeout/retry policy, and
live validation where credentials are available. Mocked HTTP or file fixtures do
not establish live authentication or provider permissions.

See [permissions](permissions.md), [data handling](data-handling.md), and the
[canonical architecture](../architecture/CANONICAL_ARCHITECTURE.md).
