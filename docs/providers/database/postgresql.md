# PostgreSQL provider

> Current status: **OFFLINE_VERIFIED**  
> Owning milestone: **07**  
> Verification: registered read-only assertions are tested with fixture sessions. No live PostgreSQL server was contacted, so this is not LIVE_VERIFIED.

## 1. Provider overview

PostgreSQL checks run only from a registered assertion. The adapter applies `default_transaction_read_only`, a read-only transaction, and `statement_timeout`. A live driver is not bundled. `QA_MCP_LIVE_DATABASES=1` still refuses to invent a successful connection.

## 2. Supported editions

Target scope includes supported PostgreSQL server versions and explicitly validated PostgreSQL-compatible managed services. Versions and compatibility claims require verification.

## 3. Cloud/self-hosted differences

Self-managed and cloud-managed services can differ in TLS, identity authentication, extensions, proxies, replicas, and connection limits. Compatibility must be verified per connection.

## 4. Supported API capabilities

Registered SELECT statements use bound parameters, an allowlisted table, a row cap, and a statement timeout. The configured login must already be read-only. The hub does not grant that role.

## 5. Authentication methods

Potential methods include password, client certificate, or provider-specific short-lived identity credentials. Driver and managed-service mechanisms require verification before implementation.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Use a dedicated read-only role restricted to approved databases/schemas/tables, plus session and statement limits. Application SQL filtering is secondary defense, not a substitute for server permissions.

**Requires verification:** record exact scope, grant, ACL, role, or process permissions in the implementation milestone.

## 7. Credential configuration

Only a credential reference may appear in configuration. Secrets must be resolved within the future adapter/runner and must not appear in MCP arguments, command lines, logs, reports, or source control.

## 8. Connection configuration example

M01 can validate this local identity, but database authentication and connectivity are not implemented:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [postgresql-uat]
connections:
  - id: postgresql-uat
    provider: postgresql
    deployment: self_managed
    account: qa-reader
    auth_kind: none
    enabled: false
```

M01's authentication contract intentionally covers API tokens, PATs, and OAuth—not
database passwords, certificates, or connection strings. Do not encode those values
as fake API-token references; the owning adapter milestone must add a typed contract.

## 9. Setup instructions

Provision a least-privilege QA reader, require TLS as policy dictates, store the secret externally, register reviewed assertions in the QA Workspace, and validate against non-production data first.

Stop after M01 local configuration: no adapter can authenticate, connect, or execute.

## 10. Windows/macOS/Linux considerations

Database protocol behavior is portable, but native driver wheels, CA paths, keyring backends, DNS, and client certificates differ across Windows, macOS, and Linux.

## 11. MCP tools using this provider

No MCP tool uses PostgreSQL through Milestone 01. Future verification tools may execute an assertion by registered ID; they must never accept free-form SQL.

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

A live server was not contacted. Connection failures in fixture tests are reported separately from assertion mismatches.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/database/postgresql.py` — IMPLEMENTED session protections. No live driver is bundled.
- `src/qa_mcp_hub/security/sql_policy.py` — IMPLEMENTED SELECT-only policy.
- `src/qa_mcp_hub/providers/registry.py` — catalog status OFFLINE_VERIFIED. The generic `read_schema` port stays unavailable.

## 19. Related tests

`tests/unit/test_verification_m07.py` covers parameter binding, injection rejection, read-only session statements, timeout, and connection failure with a fixture session.

No test opens a live PostgreSQL connection.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, process, query, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [PostgreSQL current documentation](https://www.postgresql.org/docs/current/)
- [PostgreSQL client authentication](https://www.postgresql.org/docs/current/client-authentication.html)
- [PostgreSQL role privileges](https://www.postgresql.org/docs/current/ddl-priv.html)

Endpoint, version, permission, quota, and runner details marked above require verification against current official sources before implementation.

