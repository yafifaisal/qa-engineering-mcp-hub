# Implementation progress

Last verified: 2026-10-18 (Asia/Jakarta)
Local environment: macOS, Python 3.12.12, uv 0.8.22

## Milestone 00 — implemented and offline verified

- [x] Initial clean-baseline audit captured at commit `5912691`.
- [x] One canonical architecture and decision log established.
- [x] All canonical paths plus documented support files accounted for by the machine
  manifest.
- [x] Future modules contain ownership/status/dependency/test metadata and are not
  registered as runtime behavior.
- [x] All 18 supported providers have complete M00 documentation and
  `NOT_IMPLEMENTED` status.
- [x] Generic QA Workspace, cross-platform configuration examples, schemas, agent
  prompts/skills, CI, container, and infrastructure scaffolds exist.
- [x] FastMCP registers exactly two tools, one resource, and one prompt.
- [x] Typer/Rich CLI help, version, serve, doctor, and capabilities behavior works.
- [x] Pydantic Settings and portable configuration paths are implemented without
  secret fields.
- [x] In-memory and real stdio MCP discovery/invocation pass.
- [x] Manifest-driven structure/config/schema/link/ownership/MCP/secret audit passes.
- [x] Direct dependencies are pinned and `uv.lock` is current.
- [x] Fresh wheel/sdist build and isolated exact-wheel smoke test pass.

## Executed verification

| Command | Exit | Result |
|---|---:|---|
| `uv sync --frozen` | 0 | lockfile used without dependency resolution changes |
| `uv lock --check` | 0 | lock matches project metadata |
| `uv run ruff check .` | 0 | all checks passed |
| `uv run ruff format --check .` | 0 | 278 files formatted |
| `uv run mypy src` | 0 | no issues in 181 source files |
| `uv run pytest -v` | 0 | 22 tests passed, including real stdio subprocess |
| `uv run python scripts/structure_audit.py` | 0 | 326 files, 99 directories, zero findings |
| `uv run qa-mcp --help` | 0 | expected commands displayed |
| `uv run qa-mcp doctor` | 0 | local-only readiness reported |
| `uv run qa-mcp capabilities` | 0 | implemented/planned split reported |
| `uv build` | 0 | wheel and source distribution built |
| isolated wheel import/help/smoke | 0 | version, console entry point, and MCP registry passed |

The final commands above must be rerun whenever source, tests, manifest, or package
metadata changes; the table records the final handoff run for this architecture
freeze.

## Cross-platform status

- macOS/Python 3.12: `OFFLINE_VERIFIED` locally.
- Windows 10/11 paths: `OFFLINE_VERIFIED` by simulation; native execution `BLOCKED`
  because no hosted runner was available in this session.
- Linux paths: `OFFLINE_VERIFIED` by simulation; native execution `BLOCKED` for the
  same reason.
- Python 3.13: CI-configured, execution `BLOCKED` in this session.

## Milestone 01 — implemented and offline verified

- [x] Versioned user configuration supports multiple profiles and multiple
  connections to the same provider.
- [x] Setup, profile, integration, config, client, and doctor commands operate
  on local files and credential references.
- [x] Precedence is explicit CLI option, environment override, active profile,
  user configuration, then application default. A resolved snapshot stays frozen
  when the active profile later changes.
- [x] Writes are atomic. Schema migration creates a backup and restores the
  original bytes when replacement fails.
- [x] Credentials resolve only for the bound profile, provider, connection, host,
  and account. Environment storage is read-only. A missing keyring backend
  returns an actionable error and does not write plaintext.
- [x] OAuth PKCE/state and token-lifecycle decisions are local infrastructure.
  Provider OAuth and provider network checks remain `NOT_IMPLEMENTED`.
- [x] Generated Cursor JSON, Codex TOML, and native VS Code JSON parse and contain
  no provider credential values. This repository includes `.cursor/mcp.json`.
- [x] Milestone 00 serve, doctor, capabilities, help, version, and stdio protocol
  tests still pass.

## Executed verification — Milestone 01

| Command | Exit | Result |
|---|---:|---|
| `uv sync --frozen` | 0 | lockfile used without dependency resolution changes |
| `uv lock --check` | 0 | lock matches project metadata |
| `uv run ruff check .` | 0 | all checks passed |
| `uv run ruff format --check .` | 0 | 282 files already formatted |
| `uv run mypy src` | 0 | no issues in 182 source files |
| `uv run pytest -q` | 0 | 62 passed, including the real stdio subprocess |
| `uv build` | 0 | wheel and source distribution built |
| `uv run python scripts/structure_audit.py` | 0 | 332 files, 100 directories, zero findings |
| `uv run qa-mcp --help` | 0 | setup, profiles, integrations, config, clients, doctor, serve, and capabilities listed |
| `uv run qa-mcp doctor` | 0 | local config absent; keyring backend name `Keyring` reported; provider network `NOT_IMPLEMENTED` |
| `uv run qa-mcp capabilities` | 0 | local setup capabilities implemented; provider groups planned |

`qa-mcp doctor` observed a usable macOS keyring backend without reading a secret.
No credential was written to Keychain, Windows Credential Manager, or a Linux
secret service in this session, so those stores are not `LIVE_VERIFIED`.

## Milestones 02–11

All remain `SCAFFOLDED` or `NOT_IMPLEMENTED`. No external integration is claimed as
working. Native Windows/Linux execution and Python 3.13 execution remain `BLOCKED`
on hosted-runner access.
