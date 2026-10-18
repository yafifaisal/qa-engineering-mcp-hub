# Release readiness

Status: **not approved for public release**.

The Community Edition can be built and installed from this checkout. Publishing
to PyPI, pushing a release tag, and making a repository public still require an
explicit maintainer approval. This document does not grant that approval.

## What an external engineer can do

1. Install uv and Python 3.12.
2. From a checkout, run `uv sync --frozen` or install the wheel produced by
   `uv run python scripts/build_package.py`.
3. Run `qa-mcp setup`, `qa-mcp doctor`, `qa-mcp profiles list`,
   `qa-mcp integrations list`, `qa-mcp repositories list`, and
   `qa-mcp workflows list`.
4. Generate Codex TOML, Cursor JSON, or VS Code JSON with `qa-mcp clients`.
5. Connect a supported provider by adding a connection and a keyring or
   environment credential reference. Framework source does not need to change.
6. Use the registered MCP tools. Evidence comes from a stored execution.
   A release recommendation does not approve the release.

## What is not verified

| Claim | Status |
|---|---|
| Local macOS package install and test suite | OFFLINE_VERIFIED. 180 tests passed, 1 skipped, wheel install and uvx succeeded |
| OSV query of locked packages | QUERIED on 2026-10-18. 91 packages, 0 findings. Point-in-time only |
| Hosted Windows, macOS, and Linux runners | BLOCKED. The workflow file exists and was not observed |
| Python 3.13 on a hosted runner | BLOCKED |
| Any live provider, database, Kafka, CI, or test-management system | Not LIVE_VERIFIED |
| OS keyring write/read round trip | Not LIVE_VERIFIED. Tests use an injected backend |
| Docker image build | BLOCKED. Docker was not executed |
| PyPI publication | Not performed |

Company A (GitHub, Jira, Postman, PostgreSQL, Kafka, GitHub Actions, TestRail)
and Company C (GitLab, Jira, Bruno, MySQL, Kafka, Jenkins, Xray) are simulated
profiles. The simulation checks isolation. It does not call those vendors.

## Publish gate

`.github/workflows/release.yml` builds artifacts on a tag or on manual dispatch.
The publish job is skipped unless the dispatch input is `APPROVE_PUBLIC_RELEASE`
and the `pypi` environment allows trusted publishing. Do not run that job
without a separate approval.
