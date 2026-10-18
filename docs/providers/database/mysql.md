# MySQL provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **07**  
> Verification: documentation scaffold only; no provider request or runner execution has occurred.

## 1. Provider overview

MySQL is a supported database verification target. The future adapter will execute only registered, parameterized, read-only assertions under a server-enforced least-privilege account.

## 2. Supported editions

Target scope includes supported MySQL Community/Enterprise versions and explicitly validated managed MySQL services. MariaDB or other protocol-compatible systems are not implied.

## 3. Cloud/self-hosted differences

Self-managed and managed offerings can differ in TLS, authentication plugins, identity tokens, replicas, SQL modes, and resource limits. Each connection requires verification.

## 4. Supported API capabilities

Planned capability is bounded execution of reviewed SELECT-style assertions with bound parameters, row limits, session safeguards, and normalized results. Arbitrary SQL is prohibited.

These are planned capabilities, not current support.

## 5. Authentication methods

Potential methods include password, TLS client certificates, and managed-service identity plugins. Supported connector/plugin combinations require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Use a dedicated account with SELECT only on required schemas/tables and no administrative grants. Server-side permissions remain the primary control.

**Requires verification:** record exact scope, grant, ACL, role, or process permissions in the implementation milestone.

## 7. Credential configuration

Only a credential reference may appear in configuration. Secrets must be resolved within the future adapter/runner and must not appear in MCP arguments, command lines, logs, reports, or source control.

## 8. Connection configuration example

Illustrative future shape only; Milestone 00 does not load or validate this connection:

```yaml
connections:
  - id: mysql-uat
    provider: mysql
    base_url: mysql://db.example.invalid:3306/qa
    credential_ref: personal-dev/mysql/db.example.invalid/qa-reader
    enabled: true
```

## 9. Setup instructions

Provision a read-only QA account, configure TLS and network policy, store credentials outside YAML, register reviewed assertions, and validate only against approved non-production data.

Stop during Milestone 00: the scaffold cannot authenticate, connect, or execute.

## 10. Windows/macOS/Linux considerations

Connector wheels, authentication plugins, CA paths, DNS behavior, and keyrings differ on Windows, macOS, and Linux. Native compatibility is not yet verified.

## 11. MCP tools using this provider

No MCP tool uses MySQL in Milestone 00. A future verification tool may execute an allowlisted assertion ID but cannot accept SQL text.

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

Because the provider is not implemented, current inability to connect or execute is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/database/mysql.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned injection resistance, permission, read-only session, timeout, row cap, type normalization, redaction, plugin failure, and opt-in read-only UAT tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, process, query, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [MySQL reference manual](https://dev.mysql.com/doc/refman/8.4/en/)
- [MySQL access control and account management](https://dev.mysql.com/doc/refman/8.4/en/access-control.html)
- [MySQL Connector/Python](https://dev.mysql.com/doc/connector-python/en/)

Endpoint, version, permission, quota, and runner details marked above require verification against current official sources before implementation.

