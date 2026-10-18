# Changelog

All notable changes are recorded here. The project follows semantic versioning once
its first public release is tagged.

## Unreleased

### Added

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
