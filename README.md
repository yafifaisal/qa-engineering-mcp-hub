# QA Engineering MCP Hub

QA Engineering MCP Hub is a local-first, cross-platform FastMCP foundation for
governed QA workflows. Milestones 00 and 01 provide the MCP foundation and secure
local configuration control plane. Milestone 02 adds provider contracts and local
repository registration. Milestone 03 adds read-only GitHub, GitLab, Bitbucket,
and Jira access. Milestone 04 adds read-only Confluence and Google Docs
retrieval. Milestone 05 adds a local knowledge index over approved Git
checkouts. Milestone 06 runs registered Bruno and Newman suites from approved
API workflows. Database, Kafka, CI/CD, and release features remain
`NOT_IMPLEMENTED` or `SCAFFOLDED`.

## What works through Milestone 06

- `qa-mcp serve` starts a standalone FastMCP 4 server over stdio.
- `hub_health` reports local process readiness.
- `hub_capabilities` separates callable features from future work.
- `qa-hub://status` is a read-only JSON MCP resource.
- `qa_hub_orientation` is a reusable MCP prompt.
- `qa-mcp doctor`, `qa-mcp capabilities`, `qa-mcp --help`, and
  `qa-mcp --version` provide local CLI diagnostics.
- Pydantic Settings validates non-secret `QA_MCP_` environment configuration.
- Portable configuration paths and simulated Windows/macOS/Linux behavior are
  tested.
- Versioned YAML supports named profiles, multiple connections per provider,
  repository/workspace references, execution preferences, and strict validation.
- Credentials are referenced through an OS keyring or explicitly named environment
  variables; resolved values are redacted and never serialized.
- `setup`, `profiles`, `integrations`, `config`, and `clients` commands manage and
  inspect local readiness. Integration tests do not make provider network calls.
- Cursor JSON, Codex TOML, and native VS Code JSON can be generated without
  provider credentials. This repository includes `.cursor/mcp.json` for Cursor.
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

Interactive browser OAuth, Git and Jira writes, database query, Kafka operation,
CI/CD action, test-management action, evidence publication, and release approval
are not implemented. Google Docs can refresh an access token from a stored
refresh token. Suite execution stays inside an approved workflow and a dry-run
profile does not start a runner.

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
