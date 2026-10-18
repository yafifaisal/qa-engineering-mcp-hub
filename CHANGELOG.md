# Changelog

All notable changes are recorded here. The project follows semantic versioning once
its first public release is tagged.

## Unreleased

### Added

- Milestone 11 packages the Community Edition as a pinned wheel and source
  distribution, adds `qa-mcp workflows list`, and scans built artifacts. Company
  A and Company C profile separation is OFFLINE_VERIFIED through the CLI. The
  release workflow can publish only after an explicit approval input. This
  session did not publish, tag, or run the hosted CI matrix, so Windows, Linux,
  and live providers are not LIVE_VERIFIED.
- Milestone 10 collects sanitized evidence from checks that actually ran,
  rejects an overall PASS when mandatory evidence is missing, and publishes
  only after an explicit review and a single-use approval. Release
  recommendations stay unapproved. No live Jira, Xray, or TestRail
  publication was made, so this is not LIVE_VERIFIED.
- Milestone 09 maps Xray Cloud, Xray Data Center, TestRail, CSV, XLSX, and
  Google Sheets into one canonical case. Multiline steps, extra columns, and
  formula neutralization are OFFLINE_VERIFIED. `prepare_result_publication`
  does not call a provider. Result publication is not an MCP tool. No live
  Xray, TestRail, or Google Sheets system was contacted, so these providers
  are not LIVE_VERIFIED.
- Milestone 08 registered CI inspection for Bitbucket Pipelines, GitHub
  Actions, and Jenkins. Success, failure, cancellation, permission errors,
  expired artifacts, redacted logs, and exact Git revisions are
  OFFLINE_VERIFIED with mocked HTTP. `prepare_pipeline_trigger` does not call
  a provider. Remote triggering is not an MCP tool. No live CI system was
  contacted, so these providers are not LIVE_VERIFIED.
- Milestone 07 registered read-only database assertions, bounded Kafka
  observation, and E2E workflow verification. Fixture sessions and an in-memory
  observer are OFFLINE_VERIFIED. Live database and Kafka drivers are not
  bundled, so those providers are not LIVE_VERIFIED. An overall PASS requires
  every mandatory check to have run and passed.
- Milestone 06 registered Bruno and Newman execution for approved API
  workflows. Passing and failing fixtures, timeouts, cancellation, and
  redaction are OFFLINE_VERIFIED with a local stand-in runner. The pinned
  Bruno CLI 3 and Newman 6.2.2 flags were checked against current docs.
  Those installed CLIs were not executed, so runner support is not
  LIVE_VERIFIED.
- Milestone 05 local knowledge index for permitted Git checkouts, with keyword
  retrieval, partial dependency traces, and non-executable scenario drafts.
  Mocked and local-fixture tests are OFFLINE_VERIFIED. No complete call graph
  is claimed.
- Milestone 04 read-only Confluence and Google Docs retrieval, including space-
  limited search, document citations, and Google access-token refresh. Mocked
  tests are OFFLINE_VERIFIED. Live provider calls were not executed.
- Milestone 03 read-only GitHub, GitLab, Bitbucket Cloud/Data Center, and Jira
  Cloud/Data Center adapters, plus four MCP tools for code search, change reads,
  ticket analysis, and related-implementation lookup. Mocked tests are
  OFFLINE_VERIFIED. Live provider calls were not executed.
- Milestone 02 provider contracts, capability discovery, and a profile-scoped
  repository registry. Local Git metadata can be validated. Remote provider APIs
  and repository indexing remain unimplemented.
- Cursor `mcp.json` generation alongside the existing Codex and VS Code client
  contracts. The repository includes a project `.cursor/mcp.json`.
- Milestone 01 local setup wizard, profiles, connection records, credential
  references, atomic configuration migration, and Codex/VS Code client generation.
  Provider network connectivity and provider OAuth remain unimplemented.
- Frozen canonical architecture and manifest-driven structure auditing.
- Complete Milestone 00 FastMCP tool, resource, prompt, CLI, config, and packaging
  foundation.
- Provider, QA Workspace, security, CI, and future milestone scaffolding with
  explicit implementation status.

### Changed

- Migrated the CLI and configuration modules into canonical packages while keeping
  their public imports available.
- Reconciled documentation with the canonical module ownership model.

### Security

- Restricted Milestone 00 to stdio and non-secret settings.
- Added automated checks for suspicious hardcoded secrets and accidental future MCP
  tool exposure.
