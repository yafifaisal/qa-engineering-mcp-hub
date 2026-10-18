# Confluence provider

> Current status: **OFFLINE_VERIFIED** read-only Cloud and Data Center adapter  
> Owning milestone: **04**  
> Verification: mocked HTTP tests. No live Confluence request has been executed.

## 1. Provider overview

Confluence is a supported documentation source. The future adapter will return authorized page content with stable page, version, and canonical-link provenance.

## 2. Supported editions

Target editions are Confluence Cloud and Confluence Data Center. Supported Data Center versions and content formats require verification.

## 3. Cloud/self-hosted differences

Cloud and Data Center differ in REST APIs, content representations, search behavior, authentication, deployment paths, and version cadence. Edition-specific parsing is required.

## 4. Supported API capabilities

Planned reads include constrained page search, page retrieval, title, body, version, space identity, and canonical URL. Attachments and writes are not initial capabilities.

Search requires one or more space keys and builds CQL inside the adapter.
Page body storage markup becomes plain text. Macros are omitted. Mocked tests
are OFFLINE_VERIFIED. Live calls are not claimed.

## 5. Authentication methods

Cloud and Data Center authentication options differ and may include OAuth, API tokens, or approved personal access tokens. Exact mechanisms and headers require verification.

**Requires verification:** confirm the exact current authentication flow immediately before implementation.

## 6. Required permissions

Grant view access only to explicitly authorized spaces and pages. The adapter must preserve page restrictions; exact OAuth scopes and Data Center permissions require verification.

**Requires verification:** record exact scope and role names from official documentation and a permitted sandbox.

## 7. Credential configuration

Configuration will store only a credential reference. Secret material must be resolved inside the future adapter from an approved store, never accepted as an MCP tool argument or written to logs.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact Confluence:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [confluence-primary]
connections:
  - id: confluence-primary
    provider: confluence
    deployment: cloud
    base_url: https://example.atlassian.net/wiki
    account: qa-user@example.invalid
    auth_kind: api_token
    credential:
      store: keyring
      reference: confluence-primary-token
      scope:
        profile: provider-example
        provider: confluence
        connection_id: confluence-primary
        host: example.atlassian.net
        account: qa-user@example.invalid
      kind: api_token
    enabled: false
```

## 9. Setup instructions

Register an edition-specific allowlisted origin, store credentials outside YAML,
and identify allowed spaces. M01 can test local credential presence only.

Stop after M01 local configuration; there is no working adapter or network test.

## 10. Windows/macOS/Linux considerations

The API is cross-platform, while keyrings, OAuth browser callbacks, enterprise CAs, and proxies vary by OS. Windows, macOS, and Linux remain unverified.

## 11. MCP tools using this provider

No MCP tool uses Confluence through Milestone 01. Future knowledge tools may search and retrieve grounded documents through a service that enforces profile and page authorization.

## 12. Read/write authorization behavior

Initial integration is read-only. Page creation, edits, comments, labels, attachments, or permission changes remain denied unless separately specified and approved.

## 13. Pagination and rate limiting

Search and content endpoints require edition-specific pagination. Cursor formats, expansions, result caps, and Cloud rate limits require verification.

## 14. Timeout and retry behavior

Use bounded timeouts, cap document sizes, and retry only safe reads according to provider guidance. Large-page processing must not create unbounded memory or latency.

## 15. Expected error handling

Normalize authentication, forbidden/restricted, not-found, throttled, malformed-content, and unavailable outcomes while preserving whether access restrictions caused uncertainty.

## 16. Security considerations

Treat document text as untrusted data, not instructions; allowlist origins/spaces, preserve restriction boundaries, sanitize HTML, redact secrets, and record page version/source.

## 17. Troubleshooting

Verify edition, `/wiki` or Data Center context path, page and space permissions, token scope, content representation, proxy/CA settings, and page size. Requires verification per deployment.

Because the integration is not implemented, a current connection failure is expected rather than evidence of bad credentials.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/documentation/confluence.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned Cloud/Data Center search, pagination, restricted-page, content-normalization, source-link, and separately gated live-read tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and intentionally contains no client, authentication, request, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Confluence Cloud REST API](https://developer.atlassian.com/cloud/confluence/rest/v2/intro/)
- [Confluence Data Center REST API](https://developer.atlassian.com/server/confluence/confluence-rest-api-examples/)
- [Confluence Cloud security](https://developer.atlassian.com/cloud/confluence/security-overview/)

Endpoint, scope, edition, quota, and version details marked above require verification against these current sources before implementation.

