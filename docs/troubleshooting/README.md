# Troubleshooting

Start with the local foundation before investigating a client:

```sh
uv lock --check
uv sync --frozen
uv run qa-mcp --version
uv run qa-mcp doctor
uv run qa-mcp capabilities
uv run pytest tests/integration/test_mcp_protocol.py -v
```

Milestone 00 cannot diagnose an external provider. A Git, Jira, document, API
automation, database, Kafka, CI/CD, or test-management error is expected to remain
`NOT_IMPLEMENTED` until its milestone.

Focused guides:

- [credentials](credentials.md)
- [MCP and provider integration errors](integration-errors.md)
- [test execution](test-execution.md)

When reporting a defect, include the command, exit code, redacted error, operating
system, Python/uv versions, commit, and whether the evidence came from an in-memory
test, stdio subprocess, mock, or live environment. Never paste a token.
