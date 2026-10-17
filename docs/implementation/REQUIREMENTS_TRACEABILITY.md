# Requirements traceability — M00

| Requirement | Source | Test |
|---|---|---|
| Python package and CLI | `pyproject.toml`, `src/qa_mcp_hub/cli.py` | `tests/integration/test_cli.py` |
| Health tool | `src/qa_mcp_hub/server.py` | `tests/unit/test_core.py`, `tests/integration/test_mcp_protocol.py` |
| Capability catalog | `src/qa_mcp_hub/capabilities.py` | Both unit and MCP protocol tests |
| Typed settings | `src/qa_mcp_hub/config.py` | `tests/unit/test_core.py` |
| Windows/macOS/Linux config paths | `src/qa_mcp_hub/config.py` | `tests/unit/test_core.py` |
| Package build | `pyproject.toml` | `uv build` (pending online validation) |
