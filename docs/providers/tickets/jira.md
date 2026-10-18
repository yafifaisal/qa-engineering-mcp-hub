# Jira provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **03**  
> Verification: documentation scaffold only; no provider request has been executed.

## 1. Provider overview

Jira is the supported ticket provider. The future adapter will retrieve authorized issues and related QA context while preserving issue identity and source links.

## 2. Supported editions

Target editions are Jira Cloud and Jira Data Center. Supported Data Center versions and product variants require verification.

## 3. Cloud/self-hosted differences

Cloud and Data Center differ in REST roots, API versions, user identifiers, authentication, deployment URLs, and feature availability. An edition-specific adapter path is required.

## 4. Supported API capabilities

Planned reads include issue lookup, constrained search, selected fields, comments, and linked issues needed for QA analysis. Field schemas and endpoint coverage require verification.

These are planned capabilities, not current support.

## 5. Authentication methods

Potential Cloud and Data Center mechanisms differ and may include API tokens, OAuth, or instance-approved personal access tokens. Exact support requires verification.

**Requires verification:** confirm the exact current authentication flow immediately before implementation.

## 6. Required permissions

Use browse/read permissions for only the configured projects and fields. Comment visibility and issue security can further restrict results; exact project permissions require verification.

**Requires verification:** record exact scope and role names from official documentation and a permitted sandbox.

## 7. Credential configuration

Configuration will store only a credential reference. Secret material must be resolved inside the future adapter from an approved store, never accepted as an MCP tool argument or written to logs.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact Jira:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [jira-primary]
connections:
  - id: jira-primary
    provider: jira
    deployment: cloud
    base_url: https://example.atlassian.net
    account: qa-user@example.invalid
    auth_kind: api_token
    credential:
      store: keyring
      reference: jira-primary-token
      scope:
        profile: provider-example
        provider: jira
        connection_id: jira-primary
        host: example.atlassian.net
        account: qa-user@example.invalid
      kind: api_token
    enabled: false
```

## 9. Setup instructions

Create an edition-specific connection, keep the credential in an approved secret store, choose allowlisted projects, and run a future read diagnostic. Do not paste Jira credentials into configuration or MCP arguments.

Stop after M01 local configuration; there is no working adapter or network test.

## 10. Windows/macOS/Linux considerations

Jira HTTP APIs are OS-neutral. Keyring support, browser OAuth callbacks, proxies, enterprise CAs, and shell quoting vary; no native OS flow is verified.

## 11. MCP tools using this provider

No MCP tool uses Jira through Milestone 01. Future vendor-neutral capabilities may read issues and analyze ticket context; write-oriented tools are not part of the initial adapter.

## 12. Read/write authorization behavior

Initial access is read-only. Comments, transitions, edits, attachments, and issue creation require separate requirements, project allowlists, idempotency, and explicit user approval.

## 13. Pagination and rate limiting

Search endpoints are paginated and Cloud behavior can evolve. Page tokens, field expansion, limits, and rate-limit responses require verification for the selected edition.

## 14. Timeout and retry behavior

Use bounded timeouts and conservative retry for idempotent reads only. Honor documented throttling and do not retry invalid queries or authorization failures.

## 15. Expected error handling

Normalize unauthorized, forbidden, hidden/not-found, invalid-query, rate-limited, and unavailable results. Never expose headers, tokens, private comments, or unrestricted raw payloads.

## 16. Security considerations

Allowlist the Jira origin and project scope, prevent arbitrary JQL from MCP callers, redact credentials and sensitive fields, and preserve issue-level permission boundaries.

## 17. Troubleshooting

Check Cloud versus Data Center, context path, account/token pairing, project permissions, issue security, custom-field visibility, proxy/CA settings, and throttling. Requires installation-specific verification.

Because the integration is not implemented, a current connection failure is expected rather than evidence of bad credentials.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/tickets/jira.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned Cloud/Data Center contract, pagination, field, issue-security, and sanitized-error tests plus separately authorized sandbox reads.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and intentionally contains no client, authentication, request, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Jira Cloud platform REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
- [Jira Data Center REST APIs](https://developer.atlassian.com/server/jira/platform/rest-apis/)
- [Atlassian authorization overview](https://developer.atlassian.com/cloud/jira/platform/security-overview/)

Endpoint, scope, edition, quota, and version details marked above require verification against these current sources before implementation.

