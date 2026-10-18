# Initial repository audit

Audit date: 2026-10-18 (Asia/Jakarta)  
Baseline commit: `59126915a5c44f7f32ad026786a583aabcdca597`  
Branch: `feature/canonical-architecture-m00`  
Audit scope: repository state before the canonical architecture migration

## Classification key

- **VERIFIED** — observed in source, Git state, or command output.
- **INFERRED** — a conclusion supported by observed evidence but not yet exercised end to end.
- **UNKNOWN** — not established by the baseline repository or available execution.
- **CONFLICTING** — two repository sources make incompatible claims.

## Repository state

**VERIFIED:** The worktree was clean at the start of the audit. The repository had
106 tracked files. The top-level implementation consisted of `pyproject.toml`,
`uv.lock`, a `src/qa_mcp_hub` package, tests, and a small documentation set. Local
ignored virtual-environment, cache, and `dist/` artifacts were present and were not
treated as source.

The requested canonical tree contains 300 named files and 91 directories. At the
baseline, 42 of those files and 26 of those directories existed. Therefore 258
named files and 65 directories were absent.

## Existing implementation inventory

**VERIFIED:** Eight Python modules contained implementation code:

- `src/qa_mcp_hub/__init__.py` — package version.
- `src/qa_mcp_hub/server.py` — FastMCP server and two tools.
- `src/qa_mcp_hub/cli.py` — Typer commands.
- `src/qa_mcp_hub/config.py` — minimal settings and path selection.
- `src/qa_mcp_hub/capabilities.py` — implemented/planned catalog.
- `src/qa_mcp_hub/core/models.py` — partial future profile models.
- `src/qa_mcp_hub/auth/contracts.py` — credential-store protocol.
- `src/qa_mcp_hub/auth/keyring_store.py` — partial future keyring store.

The server exposed exactly `hub_health` and `hub_capabilities`. Both returned typed
Pydantic models. The CLI exposed `serve`, `doctor`, and `capabilities`. Configuration
accepted `QA_MCP_` environment variables and provided simulated Windows, macOS, and
Linux path behavior.

**VERIFIED:** No provider adapter was implemented or registered. No shell runner,
SQL execution path, Kafka operation, CI/CD trigger, remote listener, or plaintext
secret was found in working Milestone 00 code.

## Empty and placeholder content

**VERIFIED:** The repository contained 81 zero-byte tracked files: 79 Python files,
one Markdown file, and the allowed `py.typed` marker. After allowing the two empty
package initializers, 69 source placeholders were invalid under the requested
completeness rules. Eight zero-byte test modules and
`docs/getting-started/windows.md` were also invalid. These files neither documented
ownership nor provided tests.

## Existing tests and baseline behavior

**VERIFIED:** Three non-empty test files collected 11 tests. With Python 3.12.15 on
macOS, all 11 passed. They covered direct health/capability behavior, environment
validation, simulated configuration paths, Typer commands, and in-memory FastMCP
tool discovery/invocation.

**VERIFIED:** Baseline command results, using `UV_CACHE_DIR=/tmp/qa_mcp_uv_cache`
because the sandbox cannot write the default user cache, were:

| Command | Baseline result |
|---|---|
| `uv lock --check` | exit 0; 89 packages resolved |
| `uv run ruff check .` | exit 1; two findings in `core/models.py` |
| `uv run ruff format --check .` | exit 1; two files require formatting |
| `uv run mypy src` | exit 0; no issues in 78 source files |
| `uv run pytest -v` | exit 0; 11 passed |
| `uv run qa-mcp --help` | exit 0 |
| `uv run qa-mcp doctor` | exit 0 |
| `uv run qa-mcp capabilities` | exit 0 |

**VERIFIED:** `qa-mcp --version` exited 2 with “Missing command”; the eager option
only worked when followed by a command. `python -m qa_mcp_hub` failed because the
package had no `__main__.py`.

**VERIFIED:** FastMCP discovery returned no resources and no prompts. Only an
in-memory protocol test existed; no stdio subprocess protocol test existed.

## Dependency and tool versions

**VERIFIED:** The environment used Python 3.12.15 and uv 0.13.1. Direct resolved
versions were:

| Runtime dependency | Version |
|---|---:|
| FastMCP | 4.1.0 |
| HTTPX | 0.28.1 |
| keyring | 25.7.0 |
| platformdirs | 4.13.3 |
| Pydantic | 2.14.1 |
| pydantic-settings | 2.16.0 |
| PyYAML | 6.0.3 |
| Rich | 14.3.4 |
| Typer | 0.27.3 |

| Development dependency | Version |
|---|---:|
| mypy | 1.20.2 |
| pytest | 9.1.1 |
| pytest-asyncio | 1.4.0 |
| respx | 0.23.1 |
| Ruff | 0.17.1 |

The build backend was `uv_build>=0.13.1,<0.14.0`. `uv.lock` existed and passed its
consistency check.

## Packaging state

**VERIFIED:** The project used a `src/` layout and declared the `qa-mcp` entry point.
The ignored wheel already in `dist/` predated current source and metadata: it
contained only six package files and omitted several declared dependencies and all
newer core/auth files. It is stale evidence and must not be used to claim the
current package is valid.

**UNKNOWN:** A fresh baseline build and isolated installation were deliberately not
performed during the read-only audit. They are required after migration.

## Architecture gaps and conflicts

**VERIFIED:** The following name collisions make a piecemeal migration unsafe:

- `cli.py` coexists with a `cli/` directory. Adding `cli/__init__.py` changes import
  resolution and can break the entry point.
- `config.py` coexists with a `config/` directory and has the same risk.

The following baseline locations conflict with the requested canonical ownership:

| Previous location | Canonical ownership |
|---|---|
| `capabilities.py` | `core/capabilities.py` |
| `adapters/api/` | `adapters/api_automation/` |
| `documentation/` | `adapters/documentation/` |
| `indexing/` | `knowledge/` |
| `modules/*/tools.py` | `mcp/tools/*.py` |
| generic `services/` | corresponding domain packages |
| `release/coverage.py`, `release/risk.py` | `coverage_engine.py`, `risk_engine.py` |

**CONFLICTING:** `PROGRESS.md` and `KNOWN_LIMITATIONS.md` said dependencies,
`uv.lock`, and tests were unavailable, while the lockfile was valid and the local
test environment passed. The roadmap said Milestone 01 had not started even though
partial profile and keyring code existed. The test strategy claimed strict mypy,
but no strict configuration was declared. The package description remained the
placeholder “Add your description here.”

**VERIFIED:** The implementation manual described the old module layout and would
create duplicate ownership if followed after the canonical migration.

## Missing documentation and structure

**VERIFIED:** Both authoritative architecture documents, both audit/manifest
documents, all 19 requested provider documentation paths (index plus 18 provider
pages), security documentation, complete getting-started documentation,
troubleshooting documentation, QA Workspace templates, user configuration examples,
schemas, scripts, CI workflows, and infrastructure notes were absent.

## Existing behavior to preserve

The migration must preserve these verified interfaces:

- Tool names `hub_health` and `hub_capabilities`.
- Typed health and capability payloads.
- `qa-mcp serve`, `doctor`, and `capabilities`.
- `QA_MCP_` environment settings.
- The public imports `qa_mcp_hub.config.HubSettings` and
  `qa_mcp_hub.config.default_config_dir` through package re-exports.
- Local stdio as the only transport enabled in Milestone 00.
- An explicit distinction between implemented and planned capabilities.

Partial Milestone 01 types must either be migrated without being exposed at runtime
or documented as historical prototype code; they must not be represented as a
completed integration.

## Safe migration plan

1. Freeze module boundaries and record architecture decisions.
2. Add regression coverage for current tools, payloads, CLI commands, settings, and
   path behavior, including the broken standalone version flag.
3. Migrate `cli.py` and `config.py` atomically into packages and update the entry
   point in the same change; retain compatibility re-exports.
4. Move responsibilities to canonical packages, removing duplicate zero-byte legacy
   paths only after their canonical replacements exist.
5. Keep Milestone 01–11 modules unregistered and mark them `SCAFFOLDED` or
   `NOT_IMPLEMENTED`; do not fabricate provider responses.
6. Create the QA Workspace template, safe machine configuration examples, provider
   documentation, and the full scaffold manifest.
7. Add AST/schema/link/secret-aware automated structure auditing.
8. Reconcile the manual, roadmap, progress, limitations, and traceability against the
   canonical architecture.
9. Run every quality gate, rebuild from source, test MCP through a real stdio
   subprocess, and install the fresh wheel in isolation.

## Audit conclusion

**INFERRED:** The two existing Milestone 00 tools and basic CLI/settings code are a
sound starting point, but the baseline does not meet the assignment definition of
done. The primary risks are import shadowing during migration, undocumented empty
scaffolds, stale packaging evidence, and contradictory status documentation.
