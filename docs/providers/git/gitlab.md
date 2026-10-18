# GitLab provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **03**  
> Verification: documentation scaffold only; no provider request has been executed.

## 1. Provider overview

GitLab provides Git repository hosting and development collaboration. The future adapter will translate authorized project and merge-request reads into provider-neutral records.

## 2. Supported editions

Target editions are GitLab.com and self-managed GitLab. Supported self-managed versions and paid-tier feature assumptions require verification.

## 3. Cloud/self-hosted differences

SaaS and self-managed installations use different hosts and may run different API versions or feature sets. Project paths require correct encoding, and instance-specific authentication policy must not be guessed.

## 4. Supported API capabilities

Planned read scope: project metadata, branches and commits, files at exact revisions, merge-request metadata/diffs, and relevant pipeline or status links. Exact endpoints require verification.

These are planned capabilities, not current support.

## 5. Authentication methods

Potential methods include supported access-token types and OAuth where appropriate. Token type, headers, expiry, and self-managed policy require verification against current GitLab documentation.

**Requires verification:** confirm the exact current authentication flow immediately before implementation.

## 6. Required permissions

Grant only read access to the configured projects and API data required by QA workflows. Exact scopes and role requirements require verification for the selected edition and token type.

**Requires verification:** record exact scope and role names from official documentation and a permitted sandbox.

## 7. Credential configuration

Configuration will store only a credential reference. Secret material must be resolved inside the future adapter from an approved store, never accepted as an MCP tool argument or written to logs.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact GitLab:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [gitlab-primary]
connections:
  - id: gitlab-primary
    provider: gitlab
    deployment: cloud
    base_url: https://gitlab.com
    account: qa-user
    auth_kind: pat
    credential:
      store: environment
      reference: QA_MCP_GITLAB_TOKEN
      scope:
        profile: provider-example
        provider: gitlab
        connection_id: gitlab-primary
        host: gitlab.com
        account: qa-user
      kind: pat
    enabled: false
```

## 9. Setup instructions

Register the exact GitLab host and connection ID, store credentials outside YAML, then use a future read-only diagnostic to identify the user, edition, and visible projects. No diagnostic exists now.

Stop after M01 local configuration; there is no working adapter or network test.

## 10. Windows/macOS/Linux considerations

API behavior is OS-independent, but local keyrings, enterprise CA bundles, proxies, and path quoting differ on Windows, macOS, and Linux. Native execution is unverified.

## 11. MCP tools using this provider

No MCP tool uses GitLab through Milestone 01. Future vendor-neutral capabilities may search authorized code, read exact revisions, analyze changes, and resolve related merge requests.

## 12. Read/write authorization behavior

Start read-only. Creating branches, commits, merge requests, comments, or pipeline runs must remain denied unless separately designed, allowlisted, and approved.

## 13. Pagination and rate limiting

Future code must implement GitLab's documented pagination and rate-limit behavior. Headers, keyset support, and instance-specific limits require verification.

## 14. Timeout and retry behavior

Apply bounded timeouts and retry only idempotent reads when the documented response permits it. Retries must be capped and observable.

## 15. Expected error handling

Normalize authentication, permission, not-found, rate-limit, validation, and availability failures. Sanitize response bodies and distinguish genuine absence from inaccessible projects when possible.

## 16. Security considerations

Allowlist the self-managed host, validate redirects, redact private-token and authorization headers, encode project identifiers safely, and retain exact revision provenance.

## 17. Troubleshooting

Verify the host includes the correct deployment root, token scope and expiry, project membership, proxy/CA settings, encoded project path, and instance version. Requires verification per installation.

Because the integration is not implemented, a current connection failure is expected rather than evidence of bad credentials.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/git/gitlab.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned: `tests/contracts/adapters/git/test_gitlab_contract.py` and an opt-in self-managed/SaaS sandbox suite. These files do not yet exist.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and intentionally contains no client, authentication, request, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [GitLab REST API](https://docs.gitlab.com/api/rest/)
- [GitLab authentication](https://docs.gitlab.com/api/rest/authentication/)
- [GitLab self-managed documentation](https://docs.gitlab.com/install/)

Endpoint, scope, edition, quota, and version details marked above require verification against these current sources before implementation.

