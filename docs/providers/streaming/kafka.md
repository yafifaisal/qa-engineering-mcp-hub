# Kafka provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **07**  
> Verification: documentation scaffold only; no provider request or runner execution has occurred.

## 1. Provider overview

Apache Kafka is the supported streaming verification target. The future adapter will perform approved metadata and diagnostic correlation without disrupting application consumer groups.

## 2. Supported editions

Target scope starts with supported Apache Kafka versions and explicitly validated compatible managed distributions. Vendor-specific extensions are not implied.

## 3. Cloud/self-hosted differences

Self-managed and managed clusters can differ in brokers, TLS, SASL mechanisms, identity services, network endpoints, quotas, and admin APIs. Exact compatibility requires verification.

## 4. Supported API capabilities

Planned reads include allowlisted topic metadata and bounded diagnostic event lookup/correlation where policy and retention permit. Missing evidence may be INCONCLUSIVE rather than FAILED.

These are planned capabilities, not current support.

## 5. Authentication methods

Potential mechanisms include TLS client certificates and supported SASL methods. Mechanism names, client-library support, and managed-provider identity flows require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Grant describe/read access only to allowlisted diagnostic topics and groups as needed. Do not grant topic administration, writes, broad wildcard ACLs, or production consumer-group control.

**Requires verification:** record exact scope, grant, ACL, role, or process permissions in the implementation milestone.

## 7. Credential configuration

Only a credential reference may appear in configuration. Secrets must be resolved within the future adapter/runner and must not appear in MCP arguments, command lines, logs, reports, or source control.

## 8. Connection configuration example

M01 can validate this local identity, but Kafka authentication and connectivity are not implemented:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [kafka-uat]
connections:
  - id: kafka-uat
    provider: kafka
    deployment: self_managed
    account: qa-reader
    auth_kind: none
    enabled: false
```

M01's authentication contract does not model SASL secrets, client certificates, or
broker lists. Do not encode them as fake API-token references; the owning adapter
milestone must add a typed contract before any connection can be enabled.

## 9. Setup instructions

Choose a non-disruptive diagnostic strategy, configure allowlisted brokers/topics, provision least-privilege credentials, set TLS/SASL policy, and test only in an approved sandbox.

Stop after M01 local configuration: no adapter can authenticate, connect, or execute.

## 10. Windows/macOS/Linux considerations

Native Kafka client libraries, certificate paths, DNS, firewall policy, and binary wheels differ across Windows, macOS, and Linux. All native combinations remain unverified.

## 11. MCP tools using this provider

No MCP tool uses Kafka through Milestone 01. Future verification tools may query an approved correlation source or bounded diagnostic consumer by registered assertion ID.

## 12. Read/write authorization behavior

Producing records, creating/deleting topics, changing configs, joining application groups, and committing offsets are denied. Diagnostic consumers must avoid affecting live group state.

## 13. Pagination and rate limiting

Kafka is offset/partition based rather than page based. Searches need explicit partition/offset/time bounds, record and byte caps, and retention awareness; exact client behavior requires verification.

## 14. Timeout and retry behavior

Use monotonic deadlines for metadata, assignment, polling, and total correlation. Cap polls and records, close consumers reliably, and do not loop indefinitely.

## 15. Expected error handling

Normalize authentication, authorization, transport, metadata, unknown topic, retention gap, decoding, correlation timeout, and incomplete-observation outcomes. Absence alone is not automatic failure.

## 16. Security considerations

Allowlist brokers/topics, require encrypted transport where policy demands, protect credentials, avoid sensitive payload persistence, redact PII, isolate profiles, and never commit diagnostic offsets.

## 17. Troubleshooting

Check advertised listeners, DNS/firewall, TLS hostname and CA, SASL mechanism, ACLs, topic spelling, retention window, partition bounds, schema/encoding, and clock alignment.

Because the provider is not implemented, current inability to connect or execute is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/streaming/kafka.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned ACL, TLS/auth, metadata, bounded polling, no-offset-commit, retention-gap, decode, correlation, timeout, redaction, and authorized sandbox tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, process, query, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Apache Kafka documentation](https://kafka.apache.org/documentation/)
- [Kafka security](https://kafka.apache.org/documentation/#security)
- [Kafka protocol guide](https://kafka.apache.org/protocol.html)

Endpoint, version, permission, quota, and runner details marked above require verification against current official sources before implementation.

