# Contributing

Thank you for helping build QA Engineering MCP Hub. Start by reading
[`AGENTS.md`](AGENTS.md), the
[`canonical architecture`](docs/architecture/CANONICAL_ARCHITECTURE.md), and the
[`roadmap`](docs/implementation/ROADMAP.md).

## Development setup

Install Python 3.12+ and uv, then run:

```sh
uv sync --frozen
uv run qa-mcp --help
uv run qa-mcp config validate
```

Keep changes within the owning milestone and module. A future provider scaffold is
not permission to implement that provider. External-system tests must be opt-in and
must identify whether they are mocked, offline, or live.

Milestone 01 configuration tests must use temporary directories and fake credential
stores. Never read, overwrite, or assert against a developer's real user config or
OS credential records. A local credential-presence result is not provider
connectivity evidence.

## Required checks

```sh
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
uv run python scripts/structure_audit.py
uv run python scripts/build_package.py
```

`build_package.py` writes a wheel, a source distribution, an SBOM, and a local
provenance file. It does not publish. Add `--query-osv` only when you intend to
contact the OSV API. Never commit credentials, customer content, local workspace
data, or fabricated verification evidence. Do not push a release tag or publish
to PyPI without an explicit maintainer approval.
