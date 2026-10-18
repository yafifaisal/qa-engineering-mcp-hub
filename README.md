# QA Engineering MCP Hub

QA Engineering MCP Hub is a local-first, cross-platform FastMCP foundation for
governed QA workflows. Milestones 00 and 01 provide the MCP foundation and secure
local configuration control plane. All external providers and QA execution features
remain explicitly `NOT_IMPLEMENTED` or `SCAFFOLDED`.

## What works through Milestone 01

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

No provider adapter, provider OAuth exchange, repository or ticket read, test
execution, database query, Kafka operation, CI/CD action, test-management action,
evidence publication, or release approval is implemented.

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
