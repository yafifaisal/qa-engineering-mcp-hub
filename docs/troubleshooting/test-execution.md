# Test execution troubleshooting

Registered Bruno and Newman suites can run through Milestone 06 when the profile
is not in dry-run mode and the workflow is an approved API-only workflow.
Database and Kafka steps do not run. A missing `bru` or `newman` binary is an
ERROR, not a PASS.

The repository tests use a local stand-in process. They do not prove that an
installed Bruno CLI or Newman binary is present. Set `QA_MCP_BRUNO_BIN` and
`QA_MCP_NEWMAN_BIN` only to the approved executables. Do not pass a shell string.

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
