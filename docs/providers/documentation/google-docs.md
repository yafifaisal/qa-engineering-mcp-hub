# Google Docs provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **04**  
> Verification: documentation scaffold only; no provider request has been executed.

## 1. Provider overview

Google Docs is a supported hosted document source. The future adapter will retrieve explicitly authorized documents and normalize headings, text, and source metadata.

## 2. Supported editions

The target is the Google Docs API for consumer and Google Workspace accounts. There is no self-hosted Google Docs edition; Workspace administration and account policy can change access.

## 3. Cloud/self-hosted differences

Cloud/self-hosted separation is not applicable. Consumer and managed Workspace accounts can differ in administrator policy, OAuth consent, sharing, and delegated access; details require verification.

## 4. Supported API capabilities

Planned reads include document metadata and structured content for known document IDs. Narrow Google Drive discovery may be added only to locate Docs when explicitly authorized; general Drive integration is out of scope.

These are planned capabilities, not current support.

## 5. Authentication methods

Use an approved Google OAuth flow with minimum scopes. Service-account or domain-wide delegation behavior must not be assumed and requires administrator-approved verification.

**Requires verification:** confirm the exact current authentication flow immediately before implementation.

## 6. Required permissions

Request only document read access required by the workflow. Exact OAuth scopes, restricted/sensitive classification, verification obligations, and shared-drive behavior require verification.

**Requires verification:** record exact scope and role names from official documentation and a permitted sandbox.

## 7. Credential configuration

Configuration will store only a credential reference. Secret material must be resolved inside the future adapter from an approved store, never accepted as an MCP tool argument or written to logs.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact Google Docs:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [google-docs-primary]
connections:
  - id: google-docs-primary
    provider: google_docs
    deployment: cloud
    base_url: https://docs.googleapis.com
    account: qa-user@example.invalid
    auth_kind: oauth
    credential:
      store: oauth_reference
      reference: google-docs-primary-oauth
      scope:
        profile: provider-example
        provider: google_docs
        connection_id: google-docs-primary
        host: docs.googleapis.com
        account: qa-user@example.invalid
      kind: oauth
    enabled: false
```

## 9. Setup instructions

Create an approved OAuth client, configure a named connection without client secrets in YAML, authorize the minimum scope, and test one non-sensitive shared document through a future diagnostic.

Stop after M01 local configuration; there is no working adapter or network test.

## 10. Windows/macOS/Linux considerations

Browser/device authorization, callback ports, keyring storage, and corporate proxy policy vary on Windows, macOS, and Linux. No OAuth flow is currently implemented or verified.

## 11. MCP tools using this provider

No MCP tool uses Google Docs through Milestone 01. Future knowledge tools may retrieve a known authorized document and return grounded sections with revision/source metadata.

## 12. Read/write authorization behavior

Initial access is read-only. Document creation, edits, comments, sharing, export, and permission changes are denied unless a later reviewed requirement explicitly adds them.

## 13. Pagination and rate limiting

The Docs API response model and any Drive discovery pagination must follow current Google documentation. Batch limits, quotas, and continuation tokens require verification.

## 14. Timeout and retry behavior

Use bounded HTTP timeouts, request-size limits, and quota-aware retry for safe reads only. Honor Google retry guidance and cap exponential backoff.

## 15. Expected error handling

Normalize expired consent, invalid grants, forbidden sharing, not-found, quota, malformed document, and service availability errors without exposing OAuth tokens or document content unnecessarily.

## 16. Security considerations

Minimize OAuth scopes, store refresh tokens only in an approved secret store, enforce profile/document authorization, treat document content as untrusted, and redact secrets before indexing.

## 17. Troubleshooting

Check OAuth consent status, account and Workspace policy, document sharing, scope grant, client redirect configuration, quota, proxy, and clock skew. Exact resolution requires verification.

Because the integration is not implemented, a current connection failure is expected rather than evidence of bad credentials.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/documentation/google_docs.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned OAuth boundary, structured-content, empty/large document, permission, quota, source-metadata, and opt-in authorized live-read tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and intentionally contains no client, authentication, request, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Google Docs API overview](https://developers.google.com/workspace/docs/api/how-tos/overview)
- [Google Docs API reference](https://developers.google.com/workspace/docs/api/reference/rest)
- [Google OAuth scopes](https://developers.google.com/identity/protocols/oauth2/scopes)

Endpoint, scope, edition, quota, and version details marked above require verification against these current sources before implementation.

