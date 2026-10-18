# Bruno provider

> Current status: **OFFLINE_VERIFIED**  
> Owning milestone: **06**  
> Verification: Bruno CLI 3 flags were checked against the official `bru run` options on 2026-10-18. Tests use a local stand-in process. Installed `bru` was not executed.

## 1. Provider overview

Bruno is a supported API automation runner target. The future adapter will execute only registered Bruno suites through a pinned, approved CLI and normalize deterministic assertion results.

## 2. Supported editions

The intended baseline is the locally installed Bruno CLI and repository-managed collections. Desktop, commercial, cloud-sync, and CLI feature/version relationships require verification.

## 3. Cloud/self-hosted differences

Execution is primarily local rather than a cloud/self-hosted API split. Any Bruno cloud service, sync feature, or remote workspace behavior is outside the initial runner and requires verification.

## 4. Supported API capabilities

Registered collections can be discovered, executed with the pinned `bru run` argument list, and normalized from the JSON reporter. `--sandbox safe`, `--reporter-json`, `--reporter-skip-all-headers`, `--reporter-skip-body`, `--env`, and `--env-file` are the flags used. `--env-var` is not used.

These checks are OFFLINE_VERIFIED with a stand-in process. An installed Bruno CLI was not executed.

## 5. Authentication methods

The runner itself may not require provider authentication, while the API requests inside a suite can. Suite secrets must come from an approved credential/environment resolver; exact CLI environment support requires verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Permit execution only for registered suite IDs, approved working directories, environments, and binaries. Do not grant arbitrary filesystem, network, command, or production-environment access.

**Requires verification:** record exact scope, grant, ACL, role, or process permissions in the implementation milestone.

## 7. Credential configuration

Only a credential reference may appear in configuration. Secrets must be resolved within the future adapter/runner and must not appear in MCP arguments, command lines, logs, reports, or source control.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot execute Bruno:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [bruno-local]
connections:
  - id: bruno-local
    provider: bruno
    deployment: local
    auth_kind: none
    enabled: false
```

## 9. Setup instructions

Pin and verify an approved Bruno CLI version, register suite paths in the future QA Workspace, map non-secret environments, resolve secrets at execution time, and run harmless local fixtures before any sandbox.

Stop after M01 local configuration: no adapter can authenticate, connect, or execute.

## 10. Windows/macOS/Linux considerations

Executable names, installation paths, process termination, quoting, and child-process behavior differ across Windows, macOS, and Linux. All three require native runner tests.

## 11. MCP tools using this provider

`list_registered_suites`, `list_workflows`, `explain_workflow`, `submit_test_run`, and `get_test_run` use the registered suite. They do not accept a shell command.

## 12. Read/write authorization behavior

Running a suite can mutate a target system even when the adapter does not edit Bruno files. Execution must require an allowlisted suite/environment and policy approval; arbitrary CLI arguments are forbidden.

## 13. Pagination and rate limiting

Local reporter output is not paginated, but result size must be capped. Any future Bruno remote API pagination or service quotas are out of initial scope and require verification.

## 14. Timeout and retry behavior

Use a monotonic wall-clock deadline, bounded stdout/stderr, concurrency limits, and reliable process-tree termination. Automatic reruns must not hide flaky or destructive behavior.

## 15. Expected error handling

Distinguish missing executable, unsupported version/reporter, invalid suite, denied path/environment, timeout, process failure, parser failure, and failed test assertions.

## 16. Security considerations

Use argument arrays without a shell, sanitize the environment, constrain cwd and paths, redact request secrets and response PII, cap artifacts, and keep operation success separate from assertion pass.

## 17. Troubleshooting

Check the pinned executable/version, registered suite ID, working directory, reporter format, environment mapping, network policy, and redaction. Exact CLI flags require verification.

Because the provider is not implemented, current inability to connect or execute is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/api_automation/bruno.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned registered-suite success/failure, malicious ID, path escape, timeout, missing binary, output cap, secret-redaction, parser, and native-OS smoke tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, process, query, parsing, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Bruno documentation](https://docs.usebruno.com/)
- [Bruno CLI overview](https://docs.usebruno.com/bru-cli/overview)
- [Bruno CLI command options](https://docs.usebruno.com/bru-cli/commandOptions)

Endpoint, version, permission, quota, and runner details marked above require verification against current official sources before implementation.

