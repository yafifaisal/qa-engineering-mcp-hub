# Jenkins provider

> Current status: **OFFLINE_VERIFIED**  
> Owning milestone: **08**  
> Verification: mocked Jenkins HTTP tests. No live Jenkins controller was contacted, so this is not LIVE_VERIFIED.

## 1. Provider overview

Jenkins reads are implemented for one registered job name on an HTTPS controller. The adapter lists builds, reads one build, bounds console text, and returns artifact names. UNSTABLE is a pipeline failure, not a QA assertion failure.

## 2. Supported editions

Target scope is supported Jenkins releases and explicitly validated distributions exposing compatible remote APIs. Plugin and distribution compatibility require verification.

## 3. Cloud/self-hosted differences

Jenkins is normally self-hosted; managed distributions and installations vary by version, plugins, reverse proxy, context path, authentication realm, and security policy.

## 4. Supported API capabilities

Reads use `GET /job/{name}/api/json` with a bounded tree, `GET /job/{name}/{number}/api/json`, and `GET /job/{name}/{number}/consoleText`. Artifact bytes are not downloaded. A build trigger uses one form POST to `buildWithParameters` after a crumb read, and only when policy allows it. That trigger is not an MCP tool. Job names with path traversal are rejected.

## 5. Authentication methods

Potential mechanisms include instance-approved API tokens, HTTP authentication, and client certificates through a proxy. Exact support and CSRF behavior require verification per controller.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Grant Overall/Read and the minimum Job/Build/Artifact reads for allowlisted jobs. Build, cancel, replay, configure, credential, script, and administrative permissions are initially denied.

**Requires verification:** record exact scope, grant, role, or filesystem permissions in the implementation milestone.

## 7. Credential configuration

Configuration may contain only a credential reference. Secrets must be resolved inside the future adapter and must not appear in MCP arguments, logs, reports, exported files, or source control.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact Jenkins:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [jenkins-primary]
connections:
  - id: jenkins-primary
    provider: jenkins
    deployment: self_managed
    base_url: https://jenkins.example.invalid/
    account: qa-reader
    auth_kind: api_token
    credential:
      store: keyring
      reference: jenkins-primary-token
      scope:
        profile: provider-example
        provider: jenkins
        connection_id: jenkins-primary
        host: jenkins.example.invalid
        account: qa-reader
      kind: api_token
    enabled: false
```

## 9. Setup instructions

Allowlist the controller origin and context path, provision a read-only service identity, identify approved folders/jobs, store credentials externally, and run a future harmless read diagnostic.

Stop after M01 local configuration: no adapter can authenticate, connect, read, write, or execute.

## 10. Windows/macOS/Linux considerations

The HTTP API is portable, while enterprise CAs/proxies, keyrings, path separators for artifacts, and controller/agent OS behavior vary. Client OS verification is pending.

## 11. MCP tools using this provider

`list_pipeline_runs`, `get_pipeline_status`, `get_pipeline_artifacts`, and `prepare_pipeline_trigger` accept a registered job id. The prepare tool does not call Jenkins.

## 12. Read/write authorization behavior

Parameters must be names and values listed on the registered job. A remote build is not registered as an MCP tool. When a guarded dispatch is used, the crumb request may be retried as a read, and the build POST is not retried.

## 13. Pagination and rate limiting

Jenkins APIs often use tree/depth selection rather than one universal pagination model; plugins can differ. Result bounding and exact behavior require controller verification.

## 14. Timeout and retry behavior

Use bounded HTTP and artifact/log deadlines, progressive caps, and safe read retry only. Queue/build polling needs a monotonic total deadline.

## 15. Expected error handling

Normalize authentication, permission, CSRF/crumb where relevant, missing job/build, queued/running status, truncated log, expired artifact, plugin/schema mismatch, and unavailable controller.

## 16. Security considerations

Allowlist origin/folders/jobs, prevent SSRF through artifact links, redact credentials/build parameters/log secrets, cap responses, preserve revision, and never expose script endpoints.

## 17. Troubleshooting

Check context path, reverse proxy, TLS chain, authentication realm/token, folder-encoded job path, permissions, CSRF configuration, plugins, controller version, and artifact retention.

A 403 is a permission error. Console text is redacted and truncated. An artifact marked expired is not downloaded.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/cicd/jenkins.py` — IMPLEMENTED read adapter.
- `src/qa_mcp_hub/mcp/tools/cicd.py` — IMPLEMENTED inspection tools.
- `templates/qa-workspace/ci/registered-jobs.yaml` — approved job registry.

## 19. Related tests

`tests/contracts/test_jenkins.py` covers success, failure, cancellation, unstable, exact revision, permission, timeout, invalid job names, invalid parameters, expired artifacts, redacted logs, and a single approved POST.

## 20. Current implementation status

**OFFLINE_VERIFIED** with mocked HTTP. Live Jenkins is not claimed. Plugin-specific controllers still need a separate live check.

## 21. Official documentation references

- [Jenkins Remote Access API](https://www.jenkins.io/doc/book/using/remote-access-api/)
- [Jenkins security](https://www.jenkins.io/doc/book/security/)
- [Jenkins CSRF protection](https://www.jenkins.io/doc/book/security/csrf-protection/)

Endpoint, version, permission, quota, and format details marked above require verification against current official sources before implementation.

