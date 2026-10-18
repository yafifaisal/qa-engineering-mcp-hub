# Bitbucket Pipelines provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **08**  
> Verification: documentation scaffold only; no provider request or runner execution has occurred.

## 1. Provider overview

Bitbucket Pipelines is the supported Bitbucket Cloud CI/CD service. The future adapter will normalize authorized pipeline runs, steps, logs, and artifacts.

## 2. Supported editions

Initial target is Bitbucket Pipelines in Bitbucket Cloud. Bitbucket Data Center does not imply equivalent Pipelines APIs; any related CI product is outside scope unless separately approved.

## 3. Cloud/self-hosted differences

Cloud is the defined target. Self-hosted runners can execute Cloud pipeline steps but do not convert the control-plane API into a self-hosted edition. Details require verification.

## 4. Supported API capabilities

Planned reads include pipeline definitions/identities, recent runs, step state, bounded logs, commit linkage, and artifact metadata/download when authorized.

These are planned capabilities, not current support.

## 5. Authentication methods

Use a currently supported Bitbucket Cloud authentication method with minimum repository/pipeline access. Exact token mechanisms and headers require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Grant read access only to configured workspaces/repositories and pipeline data. Pipeline triggering, variables, deployments, and repository writes require separate permissions and are initially denied.

**Requires verification:** record exact scope, grant, ACL, role, or process permissions in the implementation milestone.

## 7. Credential configuration

Only a credential reference may appear in configuration. Secrets must be resolved within the future adapter/runner and must not appear in MCP arguments, command lines, logs, reports, or source control.

## 8. Connection configuration example

Illustrative future shape only; Milestone 00 does not load or validate this connection:

```yaml
connections:
  - id: bitbucket-pipelines-primary
    provider: bitbucket_pipelines
    base_url: https://api.bitbucket.org/2.0
    credential_ref: personal-dev/bitbucket_pipelines/bitbucket.org/qa-user
    enabled: true
```

## 9. Setup instructions

Register the workspace/repositories and Cloud API origin, store credentials externally, allowlist pipeline identities, and perform a future read-only diagnostic against a harmless run.

Stop during Milestone 00: the scaffold cannot authenticate, connect, or execute.

## 10. Windows/macOS/Linux considerations

The REST API is portable. Keyring storage, proxy/CA configuration, artifact paths, and any self-hosted runner diagnostics vary across Windows, macOS, and Linux.

## 11. MCP tools using this provider

No MCP tool uses Bitbucket Pipelines in Milestone 00. Future CI/CD tools may list/read approved runs, steps, logs, and artifacts through normalized services.

## 12. Read/write authorization behavior

Read-only first. Triggering, stopping, rerunning, deployment promotion, variable changes, or artifact mutation require explicit allowlists, user confirmation, and idempotency controls.

## 13. Pagination and rate limiting

Future code must follow Bitbucket Cloud pagination and rate-limit responses for runs, steps, and artifacts. Exact fields and limits require verification.

## 14. Timeout and retry behavior

Bound all API and artifact transfers, cap log/artifact sizes, and retry safe reads only according to provider guidance. Do not automatically trigger or rerun pipelines.

## 15. Expected error handling

Normalize authentication, repository/pipeline permission, missing/expired artifact, throttling, invalid run state, truncation, and service availability errors.

## 16. Security considerations

Allowlist workspace/repository/run identities, redact auth and variable values, cap logs/artifacts, validate download redirects, preserve commit provenance, and isolate profiles.

## 17. Troubleshooting

Check Cloud workspace/repository identity, token permissions, pipeline availability, artifact expiry, rate limits, self-hosted runner relevance, proxy, and CA settings.

Because the provider is not implemented, current inability to connect or execute is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/cicd/bitbucket_pipelines.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned run-state, pagination, permission, log truncation, artifact expiry/redirect, trigger-denial, sanitized-error, and opt-in live-read tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, process, query, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Bitbucket Pipelines REST API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pipelines/)
- [Bitbucket Pipelines documentation](https://support.atlassian.com/bitbucket-cloud/docs/get-started-with-bitbucket-pipelines/)
- [Bitbucket Cloud access tokens](https://support.atlassian.com/bitbucket-cloud/docs/access-tokens/)

Endpoint, version, permission, quota, and runner details marked above require verification against current official sources before implementation.

