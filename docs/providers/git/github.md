# GitHub provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **03**  
> Verification: documentation scaffold only; no provider request has been executed.

## 1. Provider overview

GitHub is a Git hosting and collaboration provider. The future adapter is limited to grounded repository and pull-request reads needed by QA workflows.

## 2. Supported editions

Target editions are GitHub.com and GitHub Enterprise Server (GHES). Supported GHES versions and any GitHub Enterprise Cloud-specific behavior require verification before implementation.

## 3. Cloud/self-hosted differences

GitHub.com and GHES can use different API base URLs, enabled features, and release versions. An enterprise hostname must come from an allowlisted connection; the adapter must not infer endpoint compatibility.

## 4. Supported API capabilities

Planned read scope: repository metadata, branches and revisions, file content at an exact revision, commits, pull-request metadata/diffs, and relevant status information. Endpoint availability and response fields require verification.

These are planned capabilities, not current support.

## 5. Authentication methods

Potential mechanisms include GitHub Apps and appropriately scoped personal access tokens. The selected mechanism, token lifetime, and GHES support require verification against the current official documentation.

**Requires verification:** confirm the exact current authentication flow immediately before implementation.

## 6. Required permissions

Use repository read permissions only, including content and pull-request metadata needed by the configured workflow. Exact GitHub App and fine-grained token permission names require verification.

**Requires verification:** record exact scope and role names from official documentation and a permitted sandbox.

## 7. Credential configuration

Configuration will store only a credential reference. Secret material must be resolved inside the future adapter from an approved store, never accepted as an MCP tool argument or written to logs.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact GitHub:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [github-primary]
connections:
  - id: github-primary
    provider: github
    deployment: cloud
    base_url: https://api.github.com
    account: qa-user
    auth_kind: pat
    credential:
      store: environment
      reference: QA_MCP_GITHUB_TOKEN
      scope:
        profile: provider-example
        provider: github
        connection_id: github-primary
        host: api.github.com
        account: qa-user
      kind: pat
    enabled: false
```

## 9. Setup instructions

Create a named connection, allowlist its host, and store the credential through the future credential resolver rather than YAML. A future diagnostic must confirm identity, edition, permissions, and repository visibility without writing.

Stop after M01 local configuration; there is no working adapter or network test.

## 10. Windows/macOS/Linux considerations

The HTTP API is platform-neutral. Windows, macOS, and Linux still differ in keyring availability, CA trust, proxy configuration, and path handling; none has been live-verified.

## 11. MCP tools using this provider

No MCP tool uses GitHub through Milestone 01. Future vendor-neutral capabilities may include repository search, exact-revision reads, change analysis, and related pull-request lookup.

## 12. Read/write authorization behavior

Initial implementation must be read-only. Repository changes, comments, checks, workflow dispatches, or other writes are outside this adapter scope unless a later requirement adds a separate allowlist and approval.

## 13. Pagination and rate limiting

Future code must follow GitHub's documented pagination mechanism and inspect rate-limit responses. Page sizes, headers, GraphQL costs, and secondary limits require verification.

## 14. Timeout and retry behavior

Use bounded connect/read timeouts. Retry only safe idempotent reads with bounded backoff and provider guidance; never retry authorization failures or writes automatically.

## 15. Expected error handling

Normalize unauthenticated, forbidden, not-found, rate-limited, invalid-response, and unavailable outcomes without leaking response credentials. Preserve whether a missing object could be hidden by permissions.

## 16. Security considerations

Constrain hosts and redirects to the configured GitHub service, redact authorization headers, pin source claims to repository and revision, and never accept an arbitrary URL from an MCP argument.

## 17. Troubleshooting

Check the API base URL, token expiry, organization policy, SSO authorization, repository access, GHES certificate chain, and rate-limit state. Exact remediation requires verification for the configured edition.

Because the integration is not implemented, a current connection failure is expected rather than evidence of bad credentials.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/git/github.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned: `tests/contracts/adapters/git/test_github_contract.py` and an opt-in sandbox test under `tests/integration/live/`. These files do not yet exist.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and intentionally contains no client, authentication, request, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [GitHub REST API](https://docs.github.com/en/rest)
- [GitHub authentication](https://docs.github.com/en/authentication)
- [GitHub Enterprise Server](https://docs.github.com/en/enterprise-server)

Endpoint, scope, edition, quota, and version details marked above require verification against these current sources before implementation.

