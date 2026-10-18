# MySQL provider

> Current status: **OFFLINE_VERIFIED**  
> Owning milestone: **07**  
> Verification: registered read-only assertions are tested with fixture sessions. No live MySQL server was contacted, so this is not LIVE_VERIFIED.

## 1. Provider overview

MySQL checks run only from a registered assertion. The adapter applies a read-only session transaction and `MAX_EXECUTION_TIME`. A live driver is not bundled.

## 2. Supported editions

Target scope includes supported MySQL Community/Enterprise versions and explicitly validated managed MySQL services. MariaDB or other protocol-compatible systems are not implied.

## 3. Cloud/self-hosted differences

Self-managed and managed offerings can differ in TLS, authentication plugins, identity tokens, replicas, SQL modes, and resource limits. Each connection requires verification.

## 4. Supported API capabilities

Registered SELECT statements use bound parameters, an allowlisted table, a row cap, and `MAX_EXECUTION_TIME`. The configured login must already be read-only.

## 5. Authentication methods

Potential methods include password, TLS client certificates, and managed-service identity plugins. Supported connector/plugin combinations require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Use a dedicated account with SELECT only on required schemas/tables and no administrative grants. Server-side permissions remain the primary control.

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
    connection_ids: [mysql-uat]
connections:
  - id: mysql-uat
    provider: mysql
    deployment: self_managed
    account: qa-reader
    auth_kind: none
    enabled: false
```

M01's authentication contract intentionally covers API tokens, PATs, and OAuth—not
database passwords, certificates, or connection strings. Do not encode those values
as fake API-token references; the owning adapter milestone must add a typed contract.

## 9. Setup instructions

Provision a read-only QA account, configure TLS and network policy, store credentials outside YAML, register reviewed assertions, and validate only against approved non-production data.

Stop after M01 local configuration: no adapter can authenticate, connect, or execute.

## 10. Windows/macOS/Linux considerations

Connector wheels, authentication plugins, CA paths, DNS behavior, and keyrings differ on Windows, macOS, and Linux. Native compatibility is not yet verified.

## 11. MCP tools using this provider

No MCP tool uses MySQL through Milestone 01. A future verification tool may execute an allowlisted assertion ID but cannot accept SQL text.

## 12. Read/write authorization behavior

DML, DDL, stored-program invocation, multiple statements, arbitrary queries, and production targets are denied. Session read-only flags and grants must reinforce this.

## 13. Pagination and rate limiting

Return only bounded result sets. Row caps and bounded fetch behavior replace open-ended pagination; connector cursor semantics require verification.

## 14. Timeout and retry behavior

Enforce connect, read, statement/session, and overall polling deadlines. Retry only clearly safe connection establishment/read scenarios under policy.

## 15. Expected error handling

Normalize DNS/TLS, authentication plugin, permission, timeout, invalid assertion, row-limit, type-decoding, and service-unavailable errors while redacting secrets and row data.

## 16. Security considerations

Use bound parameters, reviewed assertions, server read-only grants, TLS, network allowlists, result minimization, profile isolation, redaction, and audit logging.

## 17. Troubleshooting

Check host/port, TLS mode, CA/hostname, authentication plugin, account host restrictions, schema grants, replica lag, SQL mode, timeout, and connector version.

A live server was not contacted. Connection failures in fixture tests are reported separately from assertion mismatches.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/database/mysql.py` — IMPLEMENTED session protections. No live driver is bundled.
- `src/qa_mcp_hub/security/sql_policy.py` — IMPLEMENTED SELECT-only policy.
- `src/qa_mcp_hub/providers/registry.py` — catalog status OFFLINE_VERIFIED. The generic `read_schema` port stays unavailable.

## 19. Related tests

`tests/unit/test_verification_m07.py` covers MySQL session protections and bound parameters with a fixture session.

No test opens a live MySQL connection.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, process, query, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [MySQL reference manual](https://dev.mysql.com/doc/refman/8.4/en/)
- [MySQL access control and account management](https://dev.mysql.com/doc/refman/8.4/en/access-control.html)
- [MySQL Connector/Python](https://dev.mysql.com/doc/connector-python/en/)

Endpoint, version, permission, quota, and runner details marked above require verification against current official sources before implementation.

