# Test strategy

1. Unit: data models, settings, paths, capability status.
2. MCP protocol: FastMCP in-memory Client discovers and calls real tools.
3. CLI: Typer CliRunner tests.
4. Quality: Ruff lint and format, mypy strict.
5. Distribution: uv build and isolated wheel install on connected host.
6. CI matrix after setup: Windows/macOS/Linux with Python 3.12 and 3.13.

Do not classify unexecuted tests as passed.
