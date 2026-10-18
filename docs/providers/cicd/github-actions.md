# GitHub Actions provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **08**  
> Verification: documentation scaffold only; no provider request or file operation has occurred.

## 1. Provider overview

GitHub Actions is the supported GitHub CI/CD service. The future adapter will normalize authorized workflow runs, jobs, bounded logs, artifacts, and source revisions.

## 2. Supported editions

Target editions are GitHub.com Actions and supported GitHub Enterprise Server versions where Actions and required APIs are enabled. Version support requires verification.

## 3. Cloud/self-hosted differences

GitHub.com and GHES can differ in API base URL, Actions availability, enabled features, retention, runner policy, and version. Enterprise routing must be explicit.

## 4. Supported API capabilities

Planned reads include workflow identity, runs, attempts, jobs, conclusions, commit/branch links, bounded logs, and artifact metadata/download.

These are planned capabilities, not current support.

## 5. Authentication methods

Potential methods include a GitHub App or appropriately scoped token. Exact Actions/repository permissions and GHES support require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Grant metadata, Actions, contents, and artifact read access only where required. Workflow dispatch, rerun, cancellation, secrets, and variables are separate write permissions and initially denied.

**Requires verification:** record exact scope, grant, role, or filesystem permissions in the implementation milestone.

## 7. Credential configuration

Configuration may contain only a credential reference. Secrets must be resolved inside the future adapter and must not appear in MCP arguments, logs, reports, exported files, or source control.

## 8. Connection configuration example

Illustrative future shape only; Milestone 00 does not load or validate this connection:

```yaml
connections:
  - id: github-actions-primary
    provider: github_actions
    base_url: https://api.github.com
    credential_ref: personal-dev/github_actions/github.com/qa-app
    enabled: true
```

## 9. Setup instructions

Register the GitHub edition, repositories, workflows, and API origin; store credentials externally; then run a future read-only diagnostic against a harmless completed workflow.

Stop during Milestone 00: the scaffold cannot authenticate, connect, read, write, or execute.

## 10. Windows/macOS/Linux considerations

The API is portable, but keyrings, GHES CAs/proxies, log/artifact paths, and self-hosted runner diagnostics differ across Windows, macOS, and Linux.

## 11. MCP tools using this provider

No MCP tool uses GitHub Actions in Milestone 00. Future CI/CD tools may list/read approved workflow runs, jobs, logs, and artifacts through normalized services.

## 12. Read/write authorization behavior

Read-only first. Dispatch, rerun, cancellation, approval, environment deployment, secret, or variable changes require separate policy, explicit confirmation, and idempotency.

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

Because the provider is not implemented, current inability to connect or operate is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/cicd/github_actions.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned state/attempt normalization, pagination, permission, rate-limit, log cap, artifact expiry/redirect, dispatch-denial, sanitized-error, and gated live-read tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, file, query, parsing, publication, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [GitHub Actions REST API](https://docs.github.com/en/rest/actions)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)

Endpoint, version, permission, quota, and format details marked above require verification against current official sources before implementation.

