# Test execution troubleshooting

API suite, database, Kafka, CI/CD, workflow, and end-to-end execution are not
implemented in Milestone 00. Only the repository's local unit/protocol/CLI/package
tests can run.

Use the locked environment and preserve the first real diagnostic:

```sh
uv sync --frozen
uv run pytest -v
```

If uv cannot write its cache in a sandbox, set a task-specific writable cache such
as `UV_CACHE_DIR=/tmp/qa-mcp-uv-cache`; this does not prove network access. If a test
uses a mock or fixture, report it as offline evidence. A passing simulated Windows
path test is not a live Windows run, and an in-memory MCP client does not prove stdio
subprocess behavior.

Do not silence a failure, loosen an assertion, or invent provider success. Record a
genuine external dependency restriction as `BLOCKED`, with the command and reason.
