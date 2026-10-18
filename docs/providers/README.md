# Provider documentation index

The QA Engineering MCP Hub recognizes only the provider families listed here.
At Milestone 00 every provider integration is **NOT_IMPLEMENTED**. The Python
files are ownership scaffolds: they contain no network clients, authentication
flows, subprocess runners, database sessions, Kafka consumers, or publication
logic.

Documentation examples describe a future target shape. They are not accepted by
the current runtime and are not evidence of a working connection.

## Status meanings

- **NOT_IMPLEMENTED**: no usable integration exists.
- **SCAFFOLDED**: a file documents future ownership but exposes no behavior.
- **OFFLINE_VERIFIED**: future adapter contract tests have passed without a live
  provider.
- **LIVE_VERIFIED**: a separately authorized sandbox check has passed.
- **BLOCKED**: validation could not proceed and the reason is recorded.

No provider on this page is currently OFFLINE_VERIFIED or LIVE_VERIFIED.

## Supported provider scope

| Category | Provider | Owning milestone | Status | Documentation |
|---|---|---:|---|---|
| Git | GitHub | 03 | NOT_IMPLEMENTED | [GitHub](git/github.md) |
| Git | GitLab | 03 | NOT_IMPLEMENTED | [GitLab](git/gitlab.md) |
| Git | Bitbucket | 03 | NOT_IMPLEMENTED | [Bitbucket](git/bitbucket.md) |
| Tickets | Jira | 03 | NOT_IMPLEMENTED | [Jira](tickets/jira.md) |
| Documentation | Confluence | 04 | NOT_IMPLEMENTED | [Confluence](documentation/confluence.md) |
| Documentation | Google Docs | 04 | NOT_IMPLEMENTED | [Google Docs](documentation/google-docs.md) |
| API automation | Bruno | 06 | NOT_IMPLEMENTED | [Bruno](api-automation/bruno.md) |
| API automation | Postman | 06 | NOT_IMPLEMENTED | [Postman](api-automation/postman.md) |
| Database | PostgreSQL | 07 | NOT_IMPLEMENTED | [PostgreSQL](database/postgresql.md) |
| Database | MySQL | 07 | NOT_IMPLEMENTED | [MySQL](database/mysql.md) |
| Streaming | Kafka | 07 | NOT_IMPLEMENTED | [Kafka](streaming/kafka.md) |
| CI/CD | Bitbucket Pipelines | 08 | NOT_IMPLEMENTED | [Bitbucket Pipelines](cicd/bitbucket-pipelines.md) |
| CI/CD | GitHub Actions | 08 | NOT_IMPLEMENTED | [GitHub Actions](cicd/github-actions.md) |
| CI/CD | Jenkins | 08 | NOT_IMPLEMENTED | [Jenkins](cicd/jenkins.md) |
| Test management | Xray | 09 | NOT_IMPLEMENTED | [Xray](test-management/xray.md) |
| Test management | TestRail | 09 | NOT_IMPLEMENTED | [TestRail](test-management/testrail.md) |
| Test management | CSV/XLSX spreadsheet | 09 | NOT_IMPLEMENTED | [Spreadsheet](test-management/spreadsheet.md) |
| Test management | Google Sheets | 09 | NOT_IMPLEMENTED | [Google Sheets](test-management/google-sheets.md) |

## Documentation and verification policy

Each provider page records the same 21 topics: editions, authentication,
permissions, configuration, authorization, operational behavior, security,
tests, status, and official references. Exact endpoints, scopes, editions,
limits, and runner versions must be checked against current official
documentation immediately before implementation. Unresearched details are
marked **Requires verification** rather than guessed.

Provider access will use named connections and credential references. Tokens,
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
