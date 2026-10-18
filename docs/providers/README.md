# Provider documentation index

The QA Engineering MCP Hub recognizes only the provider families listed here.
Milestone 02 publishes typed contracts and a registry for every family below.
GitHub, GitLab, Bitbucket, Jira, Confluence, and Google Docs have read-only
adapters marked **OFFLINE_VERIFIED**. Bruno and Postman registered-suite execution
is **OFFLINE_VERIFIED** with local fixtures. PostgreSQL, MySQL, and Kafka
registered checks are **OFFLINE_VERIFIED** with fixture sessions and an in-memory
observer. Bitbucket Pipelines, GitHub Actions, and Jenkins reads are
**OFFLINE_VERIFIED** with mocked HTTP. Their generic provider ports still
return contract stubs. No live database, Kafka, or CI system was contacted.
Test management and publication flows are not opened.

Documentation examples use the versioned M01 configuration shape, contain only
credential references, and remain disabled. A schema-valid local connection is not
evidence of provider connectivity.

## Status meanings

- **NOT_IMPLEMENTED**: no usable integration exists.
- **SCAFFOLDED**: a file documents future ownership but exposes no behavior.
- **OFFLINE_VERIFIED**: future adapter contract tests have passed without a live
  provider.
- **LIVE_VERIFIED**: a separately authorized sandbox check has passed.
- **BLOCKED**: validation could not proceed and the reason is recorded.

The table above is the status source. No provider on this page is
`LIVE_VERIFIED`.

## Supported provider scope

| Category | Provider | Owning milestone | Status | Documentation |
|---|---|---:|---|---|
| Git | GitHub | 03 | OFFLINE_VERIFIED | [GitHub](git/github.md) |
| Git | GitLab | 03 | OFFLINE_VERIFIED | [GitLab](git/gitlab.md) |
| Git | Bitbucket | 03 | OFFLINE_VERIFIED | [Bitbucket](git/bitbucket.md) |
| Tickets | Jira | 03 | OFFLINE_VERIFIED | [Jira](tickets/jira.md) |
| Documentation | Confluence | 04 | OFFLINE_VERIFIED | [Confluence](documentation/confluence.md) |
| Documentation | Google Docs | 04 | OFFLINE_VERIFIED | [Google Docs](documentation/google-docs.md) |
| API automation | Bruno | 06 | OFFLINE_VERIFIED | [Bruno](api-automation/bruno.md) |
| API automation | Postman | 06 | OFFLINE_VERIFIED | [Postman](api-automation/postman.md) |
| Database | PostgreSQL | 07 | OFFLINE_VERIFIED | [PostgreSQL](database/postgresql.md) |
| Database | MySQL | 07 | OFFLINE_VERIFIED | [MySQL](database/mysql.md) |
| Streaming | Kafka | 07 | OFFLINE_VERIFIED | [Kafka](streaming/kafka.md) |
| CI/CD | Bitbucket Pipelines | 08 | OFFLINE_VERIFIED | [Bitbucket Pipelines](cicd/bitbucket-pipelines.md) |
| CI/CD | GitHub Actions | 08 | OFFLINE_VERIFIED | [GitHub Actions](cicd/github-actions.md) |
| CI/CD | Jenkins | 08 | OFFLINE_VERIFIED | [Jenkins](cicd/jenkins.md) |
| Test management | Xray | 09 | OFFLINE_VERIFIED | [Xray](test-management/xray.md) |
| Test management | TestRail | 09 | OFFLINE_VERIFIED | [TestRail](test-management/testrail.md) |
| Test management | CSV/XLSX spreadsheet | 09 | OFFLINE_VERIFIED | [Spreadsheet](test-management/spreadsheet.md) |
| Test management | Google Sheets | 09 | OFFLINE_VERIFIED | [Google Sheets](test-management/google-sheets.md) |

## Documentation and verification policy

Each provider page records the same 21 topics: editions, authentication,
permissions, configuration, authorization, operational behavior, security,
tests, status, and official references. Exact endpoints, scopes, editions,
limits, and runner versions must be checked against current official
documentation immediately before implementation. Unresearched details are
marked **Requires verification** rather than guessed.

Provider access will use named connections and credential references. M01 stores
and validates those local records but does not consume them through an adapter. Tokens,
passwords, private keys, and connection strings containing secrets must remain
outside plaintext project and user configuration. Future write operations must
be separately allowlisted and explicitly approved; scaffolding never grants
write authority.

## Implementation boundary

Vendor-neutral MCP tools will remain thin. They will resolve an authorized
profile and connection, call a typed adapter/service, and return normalized
results with source and verification status. Provider adapters will own vendor
protocol translation. No arbitrary URL, shell command, SQL statement, topic, or
publication target may be supplied directly through an MCP tool.
