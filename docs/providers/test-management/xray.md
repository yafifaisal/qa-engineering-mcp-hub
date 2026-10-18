# Xray provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **09**  
> Verification: documentation scaffold only; no provider request or file operation has occurred.

## 1. Provider overview

Xray is a supported test-management provider associated with Jira. The future adapter will normalize authorized test, set, plan, execution, and result records without assuming Cloud/Data Center parity.

## 2. Supported editions

Target editions are Xray Cloud and Xray Data Center. Supported versions, product tiers, and Jira compatibility require verification.

## 3. Cloud/self-hosted differences

Cloud and Data Center have distinct APIs, authentication, base URLs, schemas, and release lifecycles. They require separate transports and fixtures.

## 4. Supported API capabilities

Planned initial reads include tests, test sets/plans, executions, statuses, steps, and external IDs. Publication/import is a later explicitly approved capability, not an initial default.

These are planned capabilities, not current support.

## 5. Authentication methods

Xray Cloud and Data Center use different provider/Jira authentication mechanisms. Exact token exchange, headers, and Jira coupling require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Grant read access only to configured Jira projects and Xray entities. Import/result publication needs separate issue/project permissions and must remain disabled initially.

**Requires verification:** record exact scope, grant, role, or filesystem permissions in the implementation milestone.

## 7. Credential configuration

Configuration may contain only a credential reference. Secrets must be resolved inside the future adapter and must not appear in MCP arguments, logs, reports, exported files, or source control.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact Xray:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [xray-primary]
connections:
  - id: xray-primary
    provider: xray
    deployment: cloud
    base_url: https://xray.cloud.getxray.app
    account: qa-client
    auth_kind: api_token
    credential:
      store: keyring
      reference: xray-primary-token
      scope:
        profile: provider-example
        provider: xray
        connection_id: xray-primary
        host: xray.cloud.getxray.app
        account: qa-client
      kind: api_token
    enabled: false
```

## 9. Setup instructions

Select the edition, register Jira/Xray origins and approved projects, store credentials externally, define canonical field mappings, and use a future read-only diagnostic before considering publication.

Stop after M01 local configuration: no adapter can authenticate, connect, read, write, or execute.

## 10. Windows/macOS/Linux considerations

The API is cross-platform. Keyrings, OAuth/token workflows, proxies, enterprise CAs, and import-file paths differ across Windows, macOS, and Linux.

## 11. MCP tools using this provider

No MCP tool uses Xray through Milestone 01. Future test-management tools may search/read normalized cases and preview approved mappings; publication needs a separate authorized tool.

## 12. Read/write authorization behavior

Read-only first. Test creation, import, execution update, evidence attachment, or result publication requires preview, explicit approval, idempotency, and project allowlisting.

## 13. Pagination and rate limiting

Cloud and Data Center pagination/query behavior differs. Limits, cursors, Jira pagination, and API quotas require current official verification.

## 14. Timeout and retry behavior

Use bounded requests and page totals. Retry only safe reads or explicitly idempotent publication with a durable key; never duplicate test/result writes.

## 15. Expected error handling

Normalize Xray/Jira authentication, permission, project/entity not found, mapping loss, validation, throttling, duplicate external ID, and service availability errors.

## 16. Security considerations

Allowlist editions/origins/projects, minimize scopes, redact credentials and evidence PII, preserve external IDs, validate attachments, and isolate profile data.

## 17. Troubleshooting

Confirm edition, Xray/Jira base URLs, client/token flow, project permissions, entity IDs, field mappings, Jira issue security, quotas, proxy, and CA settings.

Because the provider is not implemented, current inability to connect or operate is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/test_management/xray.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned separate Cloud/Data Center contracts, pagination, permission, mapping/loss report, duplicate ID, publication-denial/idempotency, and gated live-read tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, file, query, parsing, publication, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Xray documentation portal](https://docs.getxray.app/)
- [Xray Cloud API overview](https://docs.getxray.app/display/XRAYCLOUD/Global+Settings%3A+API+Keys)
- [Xray Data Center documentation](https://docs.getxray.app/display/XRAY/REST+API)

Endpoint, version, permission, quota, and format details marked above require verification against current official sources before implementation.

