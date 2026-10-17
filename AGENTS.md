# QA Engineering MCP Hub Agent Rules

- Use Python 3.12+, `uv`, standalone `fastmcp`, Pydantic v2, Typer, pytest.
- Work milestone by milestone. Never claim unimplemented integrations work.
- MCP tools must be thin; future external systems use typed adapters and services.
- Prefer deterministic assertions; AI conclusions are not PASS/FAIL evidence.
- Never expose tokens or execute unrestricted shell/SQL from MCP tools.
- Separate VERIFIED, INFERRED, UNKNOWN, and CONFLICTING findings.
- Before finishing changes run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest`, `uv build`.
- Keep `docs/implementation/PROGRESS.md` and `KNOWN_LIMITATIONS.md` factual.
- If dependencies or external systems cannot be accessed, report the blocker; do not invent successful tests.
