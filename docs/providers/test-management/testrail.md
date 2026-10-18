# TestRail provider

> Current status: **OFFLINE_VERIFIED**  
> Owning milestone: **09**  
> Verification: mocked TestRail case and run tests. No live TestRail call was made, so this is not LIVE_VERIFIED.

## 1. Provider overview

TestRail reads map projects, suites, sections, cases, and runs into the canonical models. Separated steps keep their newlines. Priority ids must appear in the mapping. The read uses a Bearer token and `index.php?/api/v2/get_cases/{project}` with the page size kept in that query string.

## 2. Supported editions

Target editions are currently supported TestRail Cloud and server-hosted offerings where an official compatible API exists. Product availability and supported versions require verification.

## 3. Cloud/self-hosted differences

Cloud and server deployments can differ in base URL, version, authentication policy, features, limits, and administrative controls. Compatibility cannot be inferred from the product name alone.

## 4. Supported API capabilities

Planned initial reads include project/suite/section/case hierarchy, runs/tests/results, fields, statuses, and external IDs. Approved case/result publication is later and disabled by default.

These are planned capabilities, not current support.

## 5. Authentication methods

Use a currently supported TestRail API authentication method approved by the instance administrator. Email/key, token, SSO interactions, and server options require verification.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Grant read access only to configured projects/suites/runs. Case creation, run creation, result publication, attachments, and administrative actions need separate permissions and approval.

**Requires verification:** record exact scope, grant, role, or filesystem permissions in the implementation milestone.

## 7. Credential configuration

Configuration may contain only a credential reference. Secrets must be resolved inside the future adapter and must not appear in MCP arguments, logs, reports, exported files, or source control.

## 8. Connection configuration example

M01 can validate this local shape, but the disabled connection cannot contact TestRail:

```yaml
schema_version: 1
active_profile: provider-example
profiles:
  provider-example:
    connection_ids: [testrail-primary]
connections:
  - id: testrail-primary
    provider: testrail
    deployment: self_managed
    base_url: https://testrail.example.invalid
    account: qa-reader
    auth_kind: api_token
    credential:
      store: environment
      reference: QA_MCP_TESTRAIL_TOKEN
      scope:
        profile: provider-example
        provider: testrail
        connection_id: testrail-primary
        host: testrail.example.invalid
        account: qa-reader
      kind: api_token
    enabled: false
```

## 9. Setup instructions

Register the exact instance and approved projects, provision a least-privilege API identity, store credentials externally, define field mappings, and run a future harmless read diagnostic.

Stop after M01 local configuration: no adapter can authenticate, connect, read, write, or execute.

## 10. Windows/macOS/Linux considerations

The API is OS-neutral. Enterprise CAs/proxies, keyrings, browser SSO constraints, and local import/export paths vary across Windows, macOS, and Linux.

## 11. MCP tools using this provider

No MCP tool uses TestRail through Milestone 01. Future tools may search/read normalized cases and preview mappings; publication requires a separate approval-aware operation.

## 12. Read/write authorization behavior

Read-only first. Creating/updating cases, suites, runs, results, attachments, or users is denied until preview, explicit approval, idempotency, and project allowlists exist.

## 13. Pagination and rate limiting

Future code must implement the currently documented TestRail pagination shape and result limits. Endpoint coverage and edition/version differences require verification.

## 14. Timeout and retry behavior

Use bounded request/page totals and safe-read retries only. Publication retries require provider-supported idempotency or local duplicate prevention.

## 15. Expected error handling

Normalize authentication, project permission, missing entity, pagination/schema, validation, duplicate external ID, throttling, attachment, and availability failures.

## 16. Security considerations

Allowlist instance/projects, minimize permissions, redact auth and PII, validate attachments, preserve external IDs, prevent CSV formula injection during export, and isolate profiles.

## 17. Troubleshooting

Check instance URL/path, edition/version, API enablement, identity/token, project role, custom fields, pagination, proxy/CA, and throttling. Requires installation verification.

Because publication is not an MCP tool, a preview cannot add TestRail results. The guarded dispatch path is the only POST, and the example mapping leaves it disabled.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/test_management/testrail.py` — IMPLEMENTED case, suite, section, and run reads.
- `src/qa_mcp_hub/adapters/test_management/base.py` — IMPLEMENTED canonical models and column mapping.
- `src/qa_mcp_hub/mcp/tools/test_management.py` — search, compare, preview, export, and publication preview.

## 19. Related tests

`tests/contracts/test_testrail.py` covers separated steps, suite and plan ids, priority rejection, permission failure, run ids, and comparison with an Xray case.

No live TestRail call was made.

## 20. Current implementation status

**OFFLINE_VERIFIED.** Mocked HTTP tests cover case and run reads. Result publication stays off unless a mapping sets `allow_publish` and a separate approval is consumed. This is not LIVE_VERIFIED.

## 21. Official documentation references

- [TestRail API introduction](https://support.testrail.com/hc/en-us/articles/7077083596436-Introduction-to-the-TestRail-API)
- [TestRail API reference](https://support.testrail.com/hc/en-us/sections/7077179429268-TestRail-API)
- [TestRail documentation](https://support.testrail.com/hc/en-us)

Endpoint, version, permission, quota, and format details marked above require verification against current official sources before implementation.

