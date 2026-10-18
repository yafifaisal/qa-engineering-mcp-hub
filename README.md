# QA Engineering MCP Hub

QA Engineering MCP Hub is a local-first FastMCP server for governed QA workflows.
Milestone 11 packages the Community Edition. An external engineer can install the
built wheel, configure a profile, register an MCP client, and use the tools that
earlier milestones implemented. This repository has not been published to PyPI,
and no provider in it is LIVE_VERIFIED. Live CI, database, Kafka, Xray, TestRail,
Google Sheets, and evidence publication were not contacted.

## What works through Milestone 11

- `qa-mcp serve` starts a standalone FastMCP 4 server over stdio.
- The registered tools cover health, read-only providers, knowledge, registered
  API and E2E runs, CI inspection, test-case mapping, evidence, and release
  recommendations. A release recommendation does not approve a release.
- `qa-mcp doctor`, `qa-mcp setup`, `qa-mcp profiles list`,
  `qa-mcp integrations list`, `qa-mcp repositories list`,
  `qa-mcp workflows list`, and `qa-mcp clients install` are the onboarding
  commands. `workflows list` does not execute a workflow.
- Credentials are referenced through an OS keyring or an explicitly named
  environment variable. Resolved values are redacted and are not written to
  YAML or generated client configuration.
- Cursor JSON, Codex TOML, and native VS Code JSON can be generated without
  provider credentials.
- `uv build` produces a wheel and a source distribution. `scripts/build_package.py`
  also writes a CycloneDX SBOM and scans those artifacts. It does not publish.
- `qa-mcp repositories` registers, lists, removes, discovers, and validates
  repositories. Discovery stays inside the profile workspace. Validation can
  read local Git branch, HEAD, remote URL, and dirty state.
- `search_repository_code`, `get_repository_changes`, `analyze_jira_ticket`, and
  `find_related_implementation` read Git and Jira through a configured credential.
  Repository and ticket text is untrusted data. Mocked tests are
  `OFFLINE_VERIFIED`. Live provider calls were not executed.
- `search_documents` and `read_document` read Confluence pages in named spaces
  and Google Docs. Results include a source link, revision, and retrieval time.
  Document text is untrusted data. A Google refresh token is not returned.
- `search_knowledge`, `find_implementation`, `trace_cross_repo_flow`,
  `analyze_change_impact`, and `generate_test_scenario_draft` use the local
  index. Results cite path, lines, and commit SHA. Traces do not claim a
  complete call graph. Scenario drafts are not executable tests.
- `list_registered_suites`, `list_workflows`, `explain_workflow`,
  `submit_test_run`, and `get_test_run` use the QA Workspace suite registry.
  A preview does not start a process. Execution uses a fixed Bruno or Newman
  argument list, never a caller shell command. API evidence does not claim
  database or Kafka verification. Local runner fixtures are `OFFLINE_VERIFIED`.
  The installed Bruno and Newman CLIs were not executed in this session.
- `list_registered_assertions`, `run_database_assertion`, `find_kafka_event`,
  and `verify_e2e_workflow` run registered checks. They do not accept SQL text
  or commit Kafka offsets. Fixture tests are `OFFLINE_VERIFIED`. A PASS does
  not claim a check that did not run. Live PostgreSQL, MySQL, and Kafka are
  not `LIVE_VERIFIED`.
- `list_pipeline_runs`, `get_pipeline_status`, `get_pipeline_artifacts`, and
  `prepare_pipeline_trigger` inspect a registered CI job. A green pipeline is
  not a QA pass. `prepare_pipeline_trigger` does not call the provider.
  Mocked HTTP tests are `OFFLINE_VERIFIED`. Live Bitbucket, GitHub Actions,
  and Jenkins were not contacted.
- `search_test_cases`, `compare_test_cases`, `preview_test_case_import`,
  `export_test_cases`, and `prepare_result_publication` use a reviewed mapping.
  Extra columns are preserved. Unknown priority and result values fail.
  Export prefixes formula-like cells. A dry-run does not write.
  `prepare_result_publication` does not call a provider. Mocked and local-file
  tests are `OFFLINE_VERIFIED`. Live Xray, TestRail, and Google Sheets were
  not contacted.
- `generate_evidence`, `validate_evidence_completeness`,
  `prepare_evidence_publication`, and `publish_approved_evidence` use a stored
  execution and a reviewed policy. API-only evidence does not claim database
  or Kafka results. `prepare_evidence_publication` does not call a provider.
  Checked-in policies deny external publication.
- `assess_release_readiness` and `generate_release_report` use mapped cases
  that executed. The recommendation does not approve the release.

Interactive browser OAuth, Git and Jira writes, remote CI triggering, and
unapproved result publication are not implemented. A release recommendation
does not sign off a release. Google
Docs can refresh an access token from a stored refresh token. Suite execution
stays inside an approved workflow and a dry-run profile does not start a runner.

## Prerequisites and setup

Install Python 3.12 or newer and [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync --frozen
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp capabilities
uv run qa-mcp setup
uv run qa-mcp config validate
```

Start the server:

```sh
uv run qa-mcp serve
```

A stdio MCP server waits for a client and normally appears silent. stdout is
reserved for MCP protocol messages.

## Codex registration

Use absolute paths for both uv and this repository:

```sh
codex mcp add qa_hub -- /ABSOLUTE/PATH/TO/uv run --project /ABSOLUTE/PATH/TO/qa-engineering-mcp-hub qa-mcp serve
codex mcp list
```

Cursor uses `.cursor/mcp.json`. Codex uses `.codex/config.toml`. Native VS Code
uses `.vscode/mcp.json`. These are separate dialects. See the
[client setup guide](docs/getting-started/codex-vscode.md)
and [platform guides](docs/getting-started/README.md).

## Architecture

The project deliberately separates:

1. the reusable framework in `src/qa_mcp_hub/`;
2. company-specific assets created from `templates/qa-workspace/`;
3. per-machine user configuration and credential references.

Read the [canonical architecture](docs/architecture/CANONICAL_ARCHITECTURE.md),
[decisions](docs/architecture/ARCHITECTURE_DECISIONS.md), and
[scaffold manifest](docs/implementation/SCAFFOLD_MANIFEST.md) before structural
changes. Provider status and documentation are indexed in
[`docs/providers/README.md`](docs/providers/README.md).

## Validation

```sh
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
uv run python scripts/structure_audit.py
uv build
```

The [progress report](docs/implementation/PROGRESS.md) records actual executed
evidence. Simulated path tests do not constitute live Windows or Linux verification.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and
[AGENTS.md](AGENTS.md). Never commit credentials, customer data, local workspace
content, or fabricated integration results.

## License

QA Engineering MCP Hub is available under the [MIT License](LICENSE).
