# Contributing

Thank you for helping build QA Engineering MCP Hub. Start by reading
[`AGENTS.md`](AGENTS.md), the
[`canonical architecture`](docs/architecture/CANONICAL_ARCHITECTURE.md), and the
[`roadmap`](docs/implementation/ROADMAP.md).

## Development setup

Install Python 3.12+ and uv, then run:

```sh
uv sync --locked
uv run qa-mcp --help
```

Keep changes within the owning milestone and module. A future provider scaffold is
not permission to implement that provider. External-system tests must be opt-in and
must identify whether they are mocked, offline, or live.

## Required checks

```sh
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
uv run python scripts/structure_audit.py
uv build
```

Update requirements traceability, progress, known limitations, and any affected
architecture decision in the same pull request. Never commit credentials, customer
content, local workspace data, or fabricated verification evidence.
