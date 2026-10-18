# Test execution troubleshooting

Registered Bruno and Newman suites can run when the profile is not in dry-run
mode and the workflow is approved. Registered database and Kafka steps run only
when their assertion files are implemented and enabled. A missing assertion does
not count as verified. A missing `bru` or `newman` binary is an ERROR, not a
PASS. A database connection failure is an ERROR, not a failed assertion. A Kafka
retention gap or missing event is INCONCLUSIVE.

The repository tests use a local stand-in process, a fixture database session,
and an in-memory Kafka observer. They do not prove that PostgreSQL, MySQL, or
Kafka is reachable. `QA_MCP_LIVE_DATABASES` and `QA_MCP_LIVE_KAFKA` do not
bundle a driver. Set `QA_MCP_BRUNO_BIN` and `QA_MCP_NEWMAN_BIN` only to the
approved executables. Do not pass a shell string.

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
