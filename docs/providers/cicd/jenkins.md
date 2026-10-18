# Jenkins provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **08**  
> Verification: documentation scaffold only; no provider request or file operation has occurred.

## 1. Provider overview

Jenkins is a supported CI/CD provider. The future adapter will translate authorized controller job, queue, build, bounded console, and artifact data into normalized records.

## 2. Supported editions

Target scope is supported Jenkins releases and explicitly validated distributions exposing compatible remote APIs. Plugin and distribution compatibility require verification.

## 3. Cloud/self-hosted differences

Jenkins is normally self-hosted; managed distributions and installations vary by version, plugins, reverse proxy, context path, authentication realm, and security policy.

## 4. Supported API capabilities

Planned reads include configured job identity, queue/build state, parameters with secret filtering, revision metadata where available, bounded console text, and artifact metadata/download.

These are planned capabilities, not current support.

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

No MCP tool uses Jenkins through Milestone 01. Future CI/CD tools may list/read approved jobs, builds, console excerpts, and artifacts through normalized services.

## 12. Read/write authorization behavior

Read-only first. Scheduling, rebuilding, cancelling, input approval, configuration, credentials, scripts, and plugin actions require distinct authorization and explicit confirmation.

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

Because the provider is not implemented, current inability to connect or operate is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/cicd/jenkins.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned folder/job routing, queue/build states, permission, crumb policy, schema variance, log cap, artifact redirect/expiry, trigger-denial, and gated live-read tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, file, query, parsing, publication, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Jenkins Remote Access API](https://www.jenkins.io/doc/book/using/remote-access-api/)
- [Jenkins security](https://www.jenkins.io/doc/book/security/)
- [Jenkins CSRF protection](https://www.jenkins.io/doc/book/security/csrf-protection/)

Endpoint, version, permission, quota, and format details marked above require verification against current official sources before implementation.

