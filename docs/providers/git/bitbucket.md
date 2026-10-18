# Bitbucket provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **03**  
> Verification: documentation scaffold only; no provider request has been executed.

## 1. Provider overview

Bitbucket supplies Git repository and pull-request collaboration. The future adapter must model Bitbucket Cloud and Bitbucket Data Center as distinct implementations behind one provider family.

## 2. Supported editions

Target editions are Bitbucket Cloud and Bitbucket Data Center. Supported Data Center versions require verification; no assumption is made about discontinued or legacy products.

## 3. Cloud/self-hosted differences

Cloud and Data Center have different hosts, REST paths, authentication choices, pagination shapes, and release lifecycles. They must not share hardcoded endpoints.

## 4. Supported API capabilities

Planned reads include repository metadata, branches, commits, exact-revision files, pull requests, and diffs. Capability parity between Cloud and Data Center requires verification.

These are planned capabilities, not current support.

## 5. Authentication methods

Cloud and Data Center support different credential mechanisms. The approved token or OAuth method and required headers must be verified for the configured edition before coding.

**Requires verification:** confirm the exact current authentication flow immediately before implementation.

## 6. Required permissions

Use repository and pull-request read access only. Exact workspace, project, repository, and token permissions require verification with current official documentation.

**Requires verification:** record exact scope and role names from official documentation and a permitted sandbox.

## 7. Credential configuration

Configuration will store only a credential reference. Secret material must be resolved inside the future adapter from an approved store, never accepted as an MCP tool argument or written to logs.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact Bitbucket:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [bitbucket-primary]
connections:
  - id: bitbucket-primary
    provider: bitbucket
    deployment: cloud
    base_url: https://api.bitbucket.org/2.0
    account: qa-user
    auth_kind: api_token
    credential:
      store: environment
      reference: QA_MCP_BITBUCKET_TOKEN
      scope:
        profile: provider-example
        provider: bitbucket
        connection_id: bitbucket-primary
        host: api.bitbucket.org
        account: qa-user
      kind: api_token
    enabled: false
```

## 9. Setup instructions

Record an explicit edition and allowlisted base URL in the future connection model, store credentials externally, and run an edition-specific read diagnostic. Current configuration cannot perform these steps.

Stop after M01 local configuration; there is no working adapter or network test.

## 10. Windows/macOS/Linux considerations

The APIs are cross-platform; keyring backends, enterprise certificates, proxies, and filesystem paths are not. Windows, macOS, and Linux live verification is pending.

## 11. MCP tools using this provider

No MCP tool uses Bitbucket through Milestone 01. Future vendor-neutral tools may read repositories and revisions, analyze pull-request changes, and ground QA findings.

## 12. Read/write authorization behavior

Repository and pull-request writes are denied by default. Any later comment, branch, or merge action needs a distinct permission model and explicit approval.

## 13. Pagination and rate limiting

Cloud and Data Center pagination differ and must have separate parsers. Rate-limit headers and server-side limits require verification for the chosen edition.

## 14. Timeout and retry behavior

Use finite HTTP timeouts and bounded retries for safe reads only. Respect provider retry guidance; never retry a merge or other mutation automatically.

## 15. Expected error handling

Map edition-specific authentication, permission, missing-object, throttling, validation, and availability failures to sanitized provider-neutral outcomes.

## 16. Security considerations

Prevent Cloud/Data Center endpoint confusion, allowlist hosts, validate redirects, redact credentials, encode workspace/project/repository identifiers, and pin file evidence to commits.

## 17. Troubleshooting

Confirm the edition, API root, workspace or project key, repository slug, token permissions, Data Center version, proxy, and CA chain. Requires verification against that installation.

Because the integration is not implemented, a current connection failure is expected rather than evidence of bad credentials.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/git/bitbucket.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned separate Cloud and Data Center contract suites plus opt-in live reads under `tests/integration/live/`. These files do not yet exist.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and intentionally contains no client, authentication, request, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Bitbucket Cloud REST API](https://developer.atlassian.com/cloud/bitbucket/rest/intro/)
- [Bitbucket Data Center REST resources](https://developer.atlassian.com/server/bitbucket/rest/)
- [Bitbucket Cloud authentication](https://support.atlassian.com/bitbucket-cloud/docs/access-tokens/)

Endpoint, scope, edition, quota, and version details marked above require verification against these current sources before implementation.

