# Scaffold manifest

Machine manifest: `config/scaffold_manifest.yaml`

The machine manifest is the exact file allowlist consumed by
`scripts/structure_audit.py`. It accounts for every path in the frozen canonical
tree and for support files that make intentionally empty future directories
explainable and testable.

## Status meaning

- `IMPLEMENTED` describes a complete Milestone 00 artifact: working M00 source,
  tests, scripts, documentation, schemas, safe examples, or templates.
- `SCAFFOLDED` describes a future Python ownership boundary. Its module docstring
  declares purpose, milestone, ownership, dependencies, and expected tests, but it
  exposes no provider or domain behavior.

Provider documentation is implemented documentation about a `NOT_IMPLEMENTED`
integration. Likewise, a complete disabled template does not make its future runner
or workflow engine implemented.

## Completeness policy

Every expected file is listed exactly once. Parent directories are derived from the
file allowlist and audited for existence. Any repository file outside the allowlist
is a mandatory violation, excluding Git metadata, virtual environments, build
outputs, caches, and other generated paths explicitly ignored by the auditor.

`src/qa_mcp_hub/py.typed` is the only intentionally zero-byte file. Package
initializers are documented even where they expose no public initialization logic.
Future module placeholders are allowed only when their manifest and AST metadata say
`SCAFFOLDED`.

Meaningful README files preserve otherwise-empty QA Workspace and test directories.
The extra machine manifest and `STRUCTURE_AUDIT.json` provide deterministic input
and machine-readable output. The retained implementation manual and test strategy
were reconciled rather than deleted because they serve users without owning code.

## Legacy path migration

| Previous path | Canonical path | Compatibility impact |
|---|---|---|
| `qa_mcp_hub/cli.py` | `qa_mcp_hub/cli/main.py` | package re-exports preserve `qa_mcp_hub.cli` imports; entry point updated |
| `qa_mcp_hub/config.py` | `qa_mcp_hub/config/models.py`, `paths.py`, `loader.py` | package re-exports preserve established imports |
| `qa_mcp_hub/capabilities.py` | `qa_mcp_hub/core/capabilities.py` | internal imports updated |
| `adapters/api/` | `adapters/api_automation/` | empty obsolete paths removed |
| `documentation/` | `adapters/documentation/` | empty obsolete paths removed |
| `indexing/` | `knowledge/` | empty obsolete paths removed |
| `modules/*/tools.py` | `mcp/tools/*.py` | future tools remain unregistered |
| generic `services/` | owning domain packages | empty duplicate ownership removed |
| `release/coverage.py`, `risk.py` | `coverage_engine.py`, `risk_engine.py` | empty obsolete names removed |

The pre-existing credential protocol, keyring wrapper, and profile data models were
moved into canonical ownership and isolated from the M00 runtime. They remain
scaffolded and are not evidence that Milestone 01 works.

## Audit command

```sh
uv run python scripts/structure_audit.py
```

The command checks files/directories, empty or placeholder content, YAML/JSON/TOML,
declared schemas, local links, AST ownership, duplicate responsibility, unlisted
files, actual MCP discovery, and hardcoded-secret indicators. It rewrites
[`STRUCTURE_AUDIT.md`](STRUCTURE_AUDIT.md) and
[`STRUCTURE_AUDIT.json`](STRUCTURE_AUDIT.json) and exits non-zero for mandatory
violations.
