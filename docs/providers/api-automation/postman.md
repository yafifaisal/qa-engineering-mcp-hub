# Postman provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **06**  
> Verification: documentation scaffold only; no provider request or runner execution has occurred.

## 1. Provider overview

Postman is a supported API automation target. The future adapter will run only registered collections through one explicitly selected and pinned supported runner.

## 2. Supported editions

Potential runners include the Postman CLI or Newman, subject to an architecture decision and current licensing/support verification. Postman cloud workspaces are not automatically part of local execution.

## 3. Cloud/self-hosted differences

Local collection execution and Postman cloud APIs have different authentication, data access, and lifecycle concerns. The initial adapter must not silently upload or synchronize collections.

## 4. Supported API capabilities

Planned capabilities are registered collection discovery, fixed runner invocation, approved environment selection, bounded output, supported result parsing, and normalized assertions.

These are planned capabilities, not current support.

## 5. Authentication methods

Collection requests may need target-system credentials; cloud collection discovery may need a Postman API key if later approved. Secret injection and exact runner authentication require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Allow only registered collection/environment IDs, approved executables, fixed arguments, bounded filesystem access, and permitted target environments. Do not accept arbitrary commands or file paths.

**Requires verification:** record exact scope, grant, ACL, role, or process permissions in the implementation milestone.

## 7. Credential configuration

Only a credential reference may appear in configuration. Secrets must be resolved within the future adapter/runner and must not appear in MCP arguments, command lines, logs, reports, or source control.

## 8. Connection configuration example

Illustrative future shape only; Milestone 00 does not load or validate this connection:

```yaml
connections:
  - id: postman-local
    provider: postman
    enabled: true
```

## 9. Setup instructions

Choose and pin the supported runner, register collection paths in the future QA Workspace, keep environments free of plaintext secrets, inject approved credentials at runtime, and validate local fixtures.

Stop during Milestone 00: the scaffold cannot authenticate, connect, or execute.

## 10. Windows/macOS/Linux considerations

Node/runtime availability, executable names, path quoting, certificate stores, and process-tree cleanup differ across Windows, macOS, and Linux. Native tests are required.

## 11. MCP tools using this provider

No MCP tool uses Postman in Milestone 00. Future execution tools may list allowlisted suites, submit a policy-approved run, and retrieve normalized results.

## 12. Read/write authorization behavior

Collection execution may write to tested systems. Only approved suites/environments may run, production is denied by default, and cloud publication or collection modification needs separate approval.

## 13. Pagination and rate limiting

Local runner output is not paginated but must be size-limited. Postman API pagination and usage quotas apply only if a future cloud-discovery feature is approved and require verification.

## 14. Timeout and retry behavior

Enforce wall-clock, output-size, and concurrency limits; terminate process trees safely. Do not automatically rerun mutating requests or reinterpret runner completion as assertion success.

## 15. Expected error handling

Distinguish missing/unsupported runner, invalid registration, denied environment, timeout, runner exit, reporter parse error, request error, and assertion failure.

## 16. Security considerations

Avoid shell execution, sanitize environment variables, constrain paths, redact secrets and response PII, validate certificates, and prevent unapproved collection upload or sync.

## 17. Troubleshooting

Confirm the selected runner/version, collection schema, registered paths, environment, certificates, network policy, reporter output, and secret resolution. Requires verification for exact flags.

Because the provider is not implemented, current inability to connect or execute is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/api_automation/postman.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned runner contract, success/failure, timeout, path escape, environment sanitization, output cap, redaction, unsupported version, and native-OS smoke tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, process, query, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Postman CLI documentation](https://learning.postman.com/docs/postman-cli/postman-cli-overview/)
- [Newman documentation](https://learning.postman.com/docs/collections/using-newman-cli/command-line-integration-with-newman/)
- [Postman API overview](https://learning.postman.com/docs/developer/postman-api/intro-api/)

Endpoint, version, permission, quota, and runner details marked above require verification against current official sources before implementation.

