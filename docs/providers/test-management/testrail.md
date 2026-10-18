# TestRail provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **09**  
> Verification: documentation scaffold only; no provider request or file operation has occurred.

## 1. Provider overview

TestRail is a supported test-management provider. The future adapter will normalize authorized projects, suites, sections, cases, runs, tests, and results.

## 2. Supported editions

Target editions are currently supported TestRail Cloud and server-hosted offerings where an official compatible API exists. Product availability and supported versions require verification.

## 3. Cloud/self-hosted differences

Cloud and server deployments can differ in base URL, version, authentication policy, features, limits, and administrative controls. Compatibility cannot be inferred from the product name alone.

## 4. Supported API capabilities

Planned initial reads include project/suite/section/case hierarchy, runs/tests/results, fields, statuses, and external IDs. Approved case/result publication is later and disabled by default.

These are planned capabilities, not current support.

## 5. Authentication methods

Use a currently supported TestRail API authentication method approved by the instance administrator. Email/key, token, SSO interactions, and server options require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Grant read access only to configured projects/suites/runs. Case creation, run creation, result publication, attachments, and administrative actions need separate permissions and approval.

**Requires verification:** record exact scope, grant, role, or filesystem permissions in the implementation milestone.

## 7. Credential configuration

Configuration may contain only a credential reference. Secrets must be resolved inside the future adapter and must not appear in MCP arguments, logs, reports, exported files, or source control.

## 8. Connection configuration example

Illustrative future shape only; Milestone 00 does not load or validate this connection:

```yaml
connections:
  - id: testrail-primary
    provider: testrail
    base_url: https://testrail.example.invalid
    credential_ref: personal-dev/testrail/testrail.example.invalid/qa-reader
    enabled: true
```

## 9. Setup instructions

Register the exact instance and approved projects, provision a least-privilege API identity, store credentials externally, define field mappings, and run a future harmless read diagnostic.

Stop during Milestone 00: the scaffold cannot authenticate, connect, read, write, or execute.

## 10. Windows/macOS/Linux considerations

The API is OS-neutral. Enterprise CAs/proxies, keyrings, browser SSO constraints, and local import/export paths vary across Windows, macOS, and Linux.

## 11. MCP tools using this provider

No MCP tool uses TestRail in Milestone 00. Future tools may search/read normalized cases and preview mappings; publication requires a separate approval-aware operation.

## 12. Read/write authorization behavior

Read-only first. Creating/updating cases, suites, runs, results, attachments, or users is denied until preview, explicit approval, idempotency, and project allowlists exist.

## 13. Pagination and rate limiting

Future code must implement the currently documented TestRail pagination shape and result limits. Endpoint coverage and edition/version differences require verification.

## 14. Timeout and retry behavior

Use bounded request/page totals and safe-read retries only. Publication retries require provider-supported idempotency or local duplicate prevention.

## 15. Expected error handling

Normalize authentication, project permission, missing entity, pagination/schema, validation, duplicate external ID, throttling, attachment, and availability failures.

## 16. Security considerations

Allowlist instance/projects, minimize permissions, redact auth and PII, validate attachments, preserve external IDs, prevent CSV formula injection during export, and isolate profiles.

## 17. Troubleshooting

Check instance URL/path, edition/version, API enablement, identity/token, project role, custom fields, pagination, proxy/CA, and throttling. Requires installation verification.

Because the provider is not implemented, current inability to connect or operate is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/test_management/testrail.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned pagination, hierarchy, custom-field mapping, permission, duplicate ID, publication-denial/idempotency, sanitized-error, and gated live-read tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, file, query, parsing, publication, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [TestRail API introduction](https://support.testrail.com/hc/en-us/articles/7077083596436-Introduction-to-the-TestRail-API)
- [TestRail API reference](https://support.testrail.com/hc/en-us/sections/7077179429268-TestRail-API)
- [TestRail documentation](https://support.testrail.com/hc/en-us)

Endpoint, version, permission, quota, and format details marked above require verification against current official sources before implementation.

