# GitHub Actions provider

> Current status: **OFFLINE_VERIFIED**  
> Owning milestone: **08**  
> Verification: mocked GitHub Actions HTTP tests. No live GitHub host was contacted, so this is not LIVE_VERIFIED.

## 1. Provider overview

GitHub Actions reads are implemented for a registered repository workflow. The adapter lists workflow runs, reads one run, bounds the first job log, and returns artifact metadata. A successful workflow is not a QA assertion pass.

## 2. Supported editions

Target editions are GitHub.com Actions and supported GitHub Enterprise Server versions where Actions and required APIs are enabled. Version support requires verification.

## 3. Cloud/self-hosted differences

GitHub.com and GHES can differ in API base URL, Actions availability, enabled features, retention, runner policy, and version. Enterprise routing must be explicit.

## 4. Supported API capabilities

Reads use `GET /repos/{owner}/{repo}/actions/workflows/{workflow}/runs`, the run, jobs, job logs, and artifact metadata endpoints on `api.github.com`. The client sends `X-GitHub-Api-Version: 2022-11-28`. At most two pages are read. Artifact bytes are not downloaded. Workflow dispatch exists only behind a single-use approval and is not an MCP tool.

## 5. Authentication methods

Potential methods include a GitHub App or appropriately scoped token. Exact Actions/repository permissions and GHES support require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Grant metadata, Actions, contents, and artifact read access only where required. Workflow dispatch, rerun, cancellation, secrets, and variables are separate write permissions and initially denied.

**Requires verification:** record exact scope, grant, role, or filesystem permissions in the implementation milestone.

## 7. Credential configuration

Configuration may contain only a credential reference. Secrets must be resolved inside the future adapter and must not appear in MCP arguments, logs, reports, exported files, or source control.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact GitHub Actions:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [github-actions-primary]
connections:
  - id: github-actions-primary
    provider: github_actions
    deployment: cloud
    base_url: https://api.github.com
    account: qa-app
    auth_kind: pat
    credential:
      store: keyring
      reference: github-actions-primary-token
      scope:
        profile: provider-example
        provider: github_actions
        connection_id: github-actions-primary
        host: api.github.com
        account: qa-app
      kind: pat
    enabled: false
```

## 9. Setup instructions

Register the GitHub edition, repositories, workflows, and API origin; store credentials externally; then run a future read-only diagnostic against a harmless completed workflow.

Stop after M01 local configuration: no adapter can authenticate, connect, read, write, or execute.

## 10. Windows/macOS/Linux considerations

The API is portable, but keyrings, GHES CAs/proxies, log/artifact paths, and self-hosted runner diagnostics differ across Windows, macOS, and Linux.

## 11. MCP tools using this provider

`list_pipeline_runs`, `get_pipeline_status`, `get_pipeline_artifacts`, and `prepare_pipeline_trigger` accept a registered job id. `prepare_pipeline_trigger` does not call GitHub. Dispatch is not a registered MCP tool.

## 12. Read/write authorization behavior

Reads are allowed for an enabled registered job. Remote dispatch stays disabled unless the job sets `allow_trigger`, the profile allows mutations, the caller confirms, and a single-use approval matches the parameter digest. A failed dispatch is not retried. Inputs outside the job registry are rejected.

## 13. Pagination and rate limiting

Run/job endpoints are paginated and API rate limits apply. Link handling, filters, attempts, and artifact retention behavior require verification.

## 14. Timeout and retry behavior

Bound metadata, logs, and artifact transfers; cap sizes; retry safe reads according to GitHub guidance. Never auto-dispatch or rerun workflows.

## 15. Expected error handling

Normalize authentication, permission, hidden/not-found workflow, rate limit, queued/in-progress terminality, missing/expired artifact, truncation, and service failures.

## 16. Security considerations

Allowlist organizations/repositories/workflows, redact authorization and logs, validate artifact redirects, cap downloads, preserve commit SHA, and isolate profiles.

## 17. Troubleshooting

Check GitHub.com versus GHES base URL/version, App installation or token access, Actions enablement, repository/workflow identity, retention, rate limits, proxy, and CA.

A 403 is a permission error. An expired artifact is reported and not downloaded. A log that contains a token is redacted and truncated.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/cicd/github_actions.py` — IMPLEMENTED read adapter.
- `src/qa_mcp_hub/mcp/tools/cicd.py` — IMPLEMENTED inspection tools.
- `templates/qa-workspace/ci/registered-jobs.yaml` — approved job registry.

## 19. Related tests

`tests/contracts/test_github_actions.py` covers success, failure, cancellation, exact revision, permission, timeout, rate limit, expired artifacts, redacted logs, and disabled or single-use dispatch.

## 20. Current implementation status

**OFFLINE_VERIFIED** with mocked HTTP. The generic `read_pipeline` port stays unavailable. Live GitHub Actions is not claimed.

## 21. Official documentation references

- [GitHub Actions REST API](https://docs.github.com/en/rest/actions)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)

Endpoint, version, permission, quota, and format details marked above require verification against current official sources before implementation.

