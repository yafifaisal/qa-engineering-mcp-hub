# PostgreSQL provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **07**  
> Verification: documentation scaffold only; no provider request or runner execution has occurred.

## 1. Provider overview

PostgreSQL is a supported database verification target. The future adapter will execute only registered, parameterized, read-only assertions using a database account that is read-only at the server.

## 2. Supported editions

Target scope includes supported PostgreSQL server versions and explicitly validated PostgreSQL-compatible managed services. Versions and compatibility claims require verification.

## 3. Cloud/self-hosted differences

Self-managed and cloud-managed services can differ in TLS, identity authentication, extensions, proxies, replicas, and connection limits. Compatibility must be verified per connection.

## 4. Supported API capabilities

Planned capability is bounded execution of pre-reviewed SELECT-style assertions with bound parameters, row caps, statement timeouts, and normalized values. Arbitrary SQL is out of scope.

These are planned capabilities, not current support.

## 5. Authentication methods

Potential methods include password, client certificate, or provider-specific short-lived identity credentials. Driver and managed-service mechanisms require verification before implementation.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Use a dedicated read-only role restricted to approved databases/schemas/tables, plus session and statement limits. Application SQL filtering is secondary defense, not a substitute for server permissions.

**Requires verification:** record exact scope, grant, ACL, role, or process permissions in the implementation milestone.

## 7. Credential configuration

Only a credential reference may appear in configuration. Secrets must be resolved within the future adapter/runner and must not appear in MCP arguments, command lines, logs, reports, or source control.

## 8. Connection configuration example

Illustrative future shape only; Milestone 00 does not load or validate this connection:

```yaml
connections:
  - id: postgresql-uat
    provider: postgresql
    base_url: postgresql://db.example.invalid:5432/qa
    credential_ref: personal-dev/postgresql/db.example.invalid/qa-reader
    enabled: true
```

## 9. Setup instructions

Provision a least-privilege QA reader, require TLS as policy dictates, store the secret externally, register reviewed assertions in the QA Workspace, and validate against non-production data first.

Stop during Milestone 00: the scaffold cannot authenticate, connect, or execute.

## 10. Windows/macOS/Linux considerations

Database protocol behavior is portable, but native driver wheels, CA paths, keyring backends, DNS, and client certificates differ across Windows, macOS, and Linux.

## 11. MCP tools using this provider

No MCP tool uses PostgreSQL in Milestone 00. Future verification tools may execute an assertion by registered ID; they must never accept free-form SQL.

## 12. Read/write authorization behavior

All writes, DDL, multi-statements, unregistered queries, and production connections are denied. Read-only transaction/session settings and server grants must enforce the policy.

## 13. Pagination and rate limiting

Results are not exposed as unbounded pages. Future assertions must impose a row cap and may use bounded server-side fetches; cursor semantics require driver verification.

## 14. Timeout and retry behavior

Apply connection, pool-acquire, statement, and overall polling deadlines. Cancel timed-out work, discard unsafe sessions, and never retry non-idempotent behavior.

## 15. Expected error handling

Normalize connection, TLS, authentication, permission, timeout, invalid assertion, row-limit, type-decoding, and unavailable outcomes without leaking connection strings or data.

## 16. Security considerations

Use parameter binding, reviewed query files, read-only accounts, network allowlists, TLS, secret redaction, per-profile isolation, data minimization, and audit records.

## 17. Troubleshooting

Check DNS/port, TLS root and hostname, credential expiry, database/schema grants, replica state, statement timeout, connection cap, and driver compatibility. Requires environment verification.

Because the provider is not implemented, current inability to connect or execute is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/database/postgresql.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned policy rejection, parameter binding, read-only transaction, row cap, timeout, type normalization, redaction, and opt-in read-only UAT tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, process, query, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [PostgreSQL current documentation](https://www.postgresql.org/docs/current/)
- [PostgreSQL client authentication](https://www.postgresql.org/docs/current/client-authentication.html)
- [PostgreSQL role privileges](https://www.postgresql.org/docs/current/ddl-priv.html)

Endpoint, version, permission, quota, and runner details marked above require verification against current official sources before implementation.

