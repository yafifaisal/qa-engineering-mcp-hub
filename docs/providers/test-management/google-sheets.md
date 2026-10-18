# Google Sheets provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **09**  
> Verification: documentation scaffold only; no provider request or file operation has occurred.

## 1. Provider overview

Google Sheets is the supported hosted spreadsheet provider. The future adapter will map explicitly authorized ranges to canonical test cases and keep it distinct from local CSV/XLSX handling.

## 2. Supported editions

The target is the Google Sheets API for consumer and Google Workspace accounts. There is no self-hosted edition; Workspace administrator policy can restrict access.

## 3. Cloud/self-hosted differences

Cloud/self-hosted separation is not applicable. Consumer and managed Workspace accounts differ in consent, sharing, service-account policy, and delegation; exact behavior requires verification.

## 4. Supported API capabilities

Planned initial reads include spreadsheet metadata and explicitly configured ranges with normalized values. Previewed, approved updates may be added later; general Drive browsing is out of scope.

These are planned capabilities, not current support.

## 5. Authentication methods

Use an approved Google OAuth flow with minimum Sheets scopes. Service accounts and domain-wide delegation must not be assumed and require administrator-approved verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Request read-only spreadsheet access initially and enforce configured spreadsheet/range allowlists. Write scopes are separate and remain disabled until explicit approval controls exist.

**Requires verification:** record exact scope, grant, role, or filesystem permissions in the implementation milestone.

## 7. Credential configuration

Configuration may contain only a credential reference. Secrets must be resolved inside the future adapter and must not appear in MCP arguments, logs, reports, exported files, or source control.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact Google Sheets:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [google-sheets-primary]
connections:
  - id: google-sheets-primary
    provider: google_sheets
    deployment: cloud
    base_url: https://sheets.googleapis.com
    account: qa-user@example.invalid
    auth_kind: oauth
    credential:
      store: oauth_reference
      reference: google-sheets-primary-oauth
      scope:
        profile: provider-example
        provider: google_sheets
        connection_id: google-sheets-primary
        host: sheets.googleapis.com
        account: qa-user@example.invalid
      kind: oauth
    enabled: false
```

## 9. Setup instructions

Create an approved OAuth client, configure named spreadsheet/range mappings, store tokens externally, authorize minimum read scope, and use a future preview against non-sensitive data.

Stop after M01 local configuration: no adapter can authenticate, connect, read, write, or execute.

## 10. Windows/macOS/Linux considerations

OAuth browser/device flow, callback ports, keyrings, proxies, and local export paths differ across Windows, macOS, and Linux. Native flows are unverified.

## 11. MCP tools using this provider

No MCP tool uses Google Sheets through Milestone 01. Future test-management tools may preview range imports and, only after approval, publish mapped values to allowlisted ranges.

## 12. Read/write authorization behavior

Read-only first. Cell updates, append, formatting, sheet creation/deletion, sharing, and Drive operations require separate scopes, range allowlists, previews, and explicit approval.

## 13. Pagination and rate limiting

Sheets uses ranges, batch requests, grid limits, and quotas rather than ordinary page lists. Batch sizes, quota units, and continuation behavior require verification.

## 14. Timeout and retry behavior

Use bounded HTTP deadlines, range/cell limits, and quota-aware retries for safe reads. Writes need idempotency/duplicate prevention and must not be blindly retried.

## 15. Expected error handling

Normalize OAuth consent/expiry, forbidden sharing, missing spreadsheet/range, invalid mapping, quota, partial batch, duplicate ID, and unavailable service outcomes.

## 16. Security considerations

Minimize OAuth scopes, store refresh tokens securely, allowlist spreadsheet/ranges, prevent formula injection, treat cells as untrusted data, redact PII, and isolate profiles.

## 17. Troubleshooting

Check OAuth consent, Workspace policy, sharing, spreadsheet ID, range notation, protected ranges, quota, mapping headers, proxy, and clock skew. Requires verification.

Because the provider is not implemented, current inability to connect or operate is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/test_management/google_sheets.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned OAuth boundary, range mapping, batch/quota, protected range, formula safety, duplicate ID, write-denial/idempotency, and opt-in authorized live-read tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, file, query, parsing, publication, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Google Sheets API overview](https://developers.google.com/workspace/sheets/api/guides/concepts)
- [Google Sheets API reference](https://developers.google.com/workspace/sheets/api/reference/rest)
- [Google OAuth scopes](https://developers.google.com/identity/protocols/oauth2/scopes)

Endpoint, version, permission, quota, and format details marked above require verification against current official sources before implementation.

