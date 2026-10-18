# Bitbucket Pipelines provider

> Current status: **OFFLINE_VERIFIED**  
> Owning milestone: **08**  
> Verification: mocked Bitbucket Cloud HTTP tests. No live Bitbucket host was contacted, so this is not LIVE_VERIFIED.

## 1. Provider overview

Bitbucket Pipelines reads are implemented for one Cloud repository. The adapter lists pipeline runs, reads one run, bounds the first step log, and returns artifact metadata declared on the step. A successful pipeline is not a QA assertion pass.

## 2. Supported editions

Initial target is Bitbucket Pipelines in Bitbucket Cloud. Bitbucket Data Center does not imply equivalent Pipelines APIs; any related CI product is outside scope unless separately approved.

## 3. Cloud/self-hosted differences

Cloud is the defined target. Self-hosted runners can execute Cloud pipeline steps but do not convert the control-plane API into a self-hosted edition. Details require verification.

## 4. Supported API capabilities

Reads use `GET /2.0/repositories/{workspace}/{repo}/pipelines`, one pipeline, its steps, and the first step log on `api.bitbucket.org`. At most two pages are followed. Artifact bytes are not downloaded. A pipeline trigger is not an MCP tool.

## 5. Authentication methods

Use a currently supported Bitbucket Cloud authentication method with minimum repository/pipeline access. Exact token mechanisms and headers require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Grant read access only to configured workspaces/repositories and pipeline data. Pipeline triggering, variables, deployments, and repository writes require separate permissions and are initially denied.

**Requires verification:** record exact scope, grant, ACL, role, or process permissions in the implementation milestone.

## 7. Credential configuration

Only a credential reference may appear in configuration. Secrets must be resolved within the future adapter/runner and must not appear in MCP arguments, command lines, logs, reports, or source control.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact Bitbucket Pipelines:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [bitbucket-pipelines-primary]
connections:
  - id: bitbucket-pipelines-primary
    provider: bitbucket_pipelines
    deployment: cloud
    base_url: https://api.bitbucket.org/2.0
    account: qa-user
    auth_kind: api_token
    credential:
      store: environment
      reference: QA_MCP_BITBUCKET_PIPELINES_TOKEN
      scope:
        profile: provider-example
        provider: bitbucket_pipelines
        connection_id: bitbucket-pipelines-primary
        host: api.bitbucket.org
        account: qa-user
      kind: api_token
    enabled: false
```

## 9. Setup instructions

Register the workspace/repositories and Cloud API origin, store credentials externally, allowlist pipeline identities, and perform a future read-only diagnostic against a harmless run.

Stop after M01 local configuration: no adapter can authenticate, connect, or execute.

## 10. Windows/macOS/Linux considerations

The REST API is portable. Keyring storage, proxy/CA configuration, artifact paths, and any self-hosted runner diagnostics vary across Windows, macOS, and Linux.

## 11. MCP tools using this provider

`list_pipeline_runs`, `get_pipeline_status`, `get_pipeline_artifacts`, and `prepare_pipeline_trigger` accept a registered job id. The prepare tool does not call Bitbucket.

## 12. Read/write authorization behavior

The workspace example denies triggering. A remote trigger is not registered as an MCP tool. Arbitrary pipeline selectors are not accepted.

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

A 403 is a permission error. An expired artifact is reported and not downloaded. Logs are redacted and truncated.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/cicd/bitbucket_pipelines.py` — IMPLEMENTED read adapter.
- `src/qa_mcp_hub/mcp/tools/cicd.py` — IMPLEMENTED inspection tools.
- `templates/qa-workspace/ci/registered-jobs.yaml` — approved job registry.

## 19. Related tests

`tests/contracts/test_bitbucket_pipelines.py` covers success, failure, cancellation, pagination, permission, rate limit, exact revision, expired artifacts, redacted logs, and a denied trigger.

## 20. Current implementation status

**OFFLINE_VERIFIED** with mocked HTTP. Live Bitbucket Pipelines is not claimed.

## 21. Official documentation references

- [Bitbucket Pipelines REST API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pipelines/)
- [Bitbucket Pipelines documentation](https://support.atlassian.com/bitbucket-cloud/docs/get-started-with-bitbucket-pipelines/)
- [Bitbucket Cloud access tokens](https://support.atlassian.com/bitbucket-cloud/docs/access-tokens/)

Endpoint, version, permission, quota, and runner details marked above require verification against current official sources before implementation.

