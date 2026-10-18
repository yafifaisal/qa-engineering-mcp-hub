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

## Milestone 02 — implemented and offline verified

- [x] Typed provider ports, shared result models, and a catalog that matches the
  architecture document. Every provider operation on those ports raises a typed
  not-implemented error.
- [x] Multiple connections for one provider stay distinct, and a connection cannot
  be bound from another profile.
- [x] `qa-mcp repositories add/list/remove/discover/validate` registers local
  checkouts and remote definitions. Discovery and registration stay inside the
  profile workspace.
- [x] Local Git metadata reports branch, HEAD, redacted origin URL, and dirty
  state. Symlink escape and path traversal are rejected.
- [x] Indexing permission is recorded as a plan with status `NOT_EXECUTED`.
  File contents are not read.
- [x] MCP discovery remains two tools, one resource, and one prompt. Provider
  groups stay planned.

## Executed verification — Milestone 02

| Command | Exit | Result |
|---|---:|---|
| `uv sync --frozen` | 0 | lockfile used without dependency resolution changes |
| `uv lock --check` | 0 | lock matches project metadata |
| `uv run ruff check .` | 0 | all checks passed |
| `uv run ruff format --check .` | 0 | 285 files already formatted |
| `uv run mypy src` | 0 | no issues in 182 source files |
| `uv run pytest -q` | 0 | 84 passed, including the real stdio subprocess |
| `uv build` | 0 | wheel and source distribution built |
| `uv run python scripts/structure_audit.py` | 0 | 335 files, 100 directories, zero findings |
| `uv run qa-mcp capabilities` | 0 | provider contracts and repository registry implemented; provider groups planned |
| `uv run qa-mcp doctor` | 0 | local config valid; keyring backend name `Keyring`; provider network `NOT_IMPLEMENTED` |

Local Git metadata was read on this macOS machine. Windows and Linux path checks
are simulations. No GitHub, GitLab, or Bitbucket API was called. Repository
indexing was not executed.

## Milestone 03 — implemented and offline verified

- [x] Read-only GitHub, GitLab, and Bitbucket Cloud/Data Center adapters read
  repository metadata, commits, files, pull or merge requests, and diffs.
- [x] Read-only Jira Cloud uses `/rest/api/3/search/jql`. A self-managed
  connection uses `/rest/api/2/search`. Descriptions become plain text.
- [x] MCP tools `search_repository_code`, `get_repository_changes`,
  `analyze_jira_ticket`, and `find_related_implementation` resolve configured
  credentials. Tool arguments do not accept tokens.
- [x] Code hits carry a commit SHA and source URL. Local HEAD is recorded
  separately from the remote SHA.
- [ ] Live GitHub, GitLab, Bitbucket, and Jira calls were not executed.
  `QA_MCP_LIVE_PROVIDERS` was not set.

## Executed verification — Milestone 03

| Command | Exit | Result |
|---|---:|---|
| `uv sync --frozen` | 0 | lockfile used without dependency resolution changes |
| `uv lock --check` | 0 | lock matches project metadata |
| `uv run ruff check .` | 0 | all checks passed |
| `uv run ruff format --check .` | 0 | 288 files already formatted |
| `uv run mypy src` | 0 | no issues in 182 source files |
| `uv run pytest -q` | 0 | 97 passed, 1 skipped |
| `uv build` | 0 | wheel and source distribution built |
| `uv run python scripts/structure_audit.py` | 0 | 338 files, 100 directories, zero findings |

The skipped test is `tests/integration/test_provider_live.py`. `QA_MCP_LIVE_PROVIDERS`
was not set, so no GitHub, GitLab, Bitbucket, or Jira host was called. Those
reads are `OFFLINE_VERIFIED` from respx mocks and are not `LIVE_VERIFIED`.
Windows and Linux execution remains `BLOCKED`.

## Milestone 04 — implemented and offline verified

- [x] Confluence Cloud and Data Center search is limited to named spaces. Page
  reads include version, link, and plain text. Storage macros are omitted.
- [x] Google Docs reads headings, paragraphs, and tables. Drive is used only to
  find documents by name.
- [x] A stored Google refresh token can be exchanged for a short-lived access
  token. Tool results do not include the refresh token.
- [x] MCP tools `search_documents` and `read_document` return normalized
  citations. Document text is untrusted data.
- [ ] Live Confluence and Google calls were not executed.

## Executed verification — Milestone 04

| Command | Exit | Result |
|---|---:|---|
| `uv sync --frozen` | 0 | lockfile used without dependency resolution changes |
| `uv lock --check` | 0 | lock matches project metadata |
| `uv run ruff check .` | 0 | all checks passed |
| `uv run ruff format --check .` | 0 | 290 files already formatted |
| `uv run mypy src` | 0 | no issues in 182 source files |
| `uv run pytest -q` | 0 | 104 passed, 1 skipped |
| `uv build` | 0 | sdist and wheel built |
| `uv run python scripts/structure_audit.py` | 0 | PASS, 0 findings |

The skipped test is `tests/integration/test_provider_live.py`. `QA_MCP_LIVE_PROVIDERS`
was not set, so no Confluence or Google host was called. Those reads are
`OFFLINE_VERIFIED` from respx mocks and are not `LIVE_VERIFIED`. Windows and
Linux execution remains `BLOCKED`.

## Milestone 05 — implemented and offline verified

- [x] Permitted local Git checkouts can be indexed. Secret paths, generated
  artifacts, and untracked files are skipped.
- [x] Keyword search returns citations with path, lines, commit SHA, and
  retrieval time. Stale HEAD revisions produce a warning before refresh.
- [x] Python symbols use the standard-library parser. Go, Java, JavaScript, and
  TypeScript use pattern parsers labeled INFERRED. Other languages stay UNKNOWN.
- [x] Dependency traces stay partial. `complete_graph` is false.
- [x] Scenario drafts are not executable and do not create workflows.
- [ ] No hosted embedding service is included. No live provider call was made.

## Executed verification — Milestone 05

| Command | Exit | Result |
|---|---:|---|
| `uv sync --frozen` | 0 | lockfile used without dependency resolution changes |
| `uv lock --check` | 0 | lock matches project metadata |
| `uv run ruff check .` | 0 | all checks passed |
| `uv run ruff format --check .` | 0 | 292 files already formatted |
| `uv run mypy src` | 0 | no issues in 182 source files |
| `uv run pytest -q` | 0 | 113 passed, 1 skipped |
| `uv build` | 0 | sdist and wheel built |
| `uv run python scripts/structure_audit.py` | 0 | PASS, 342 files, 100 directories, 0 findings |

The skipped test is `tests/integration/test_provider_live.py`. `QA_MCP_LIVE_PROVIDERS`
was not set. Knowledge tests used local Git fixtures. No Confluence, Google, or
Git host was called. Windows and Linux execution remains `BLOCKED`.

## Milestone 06 — implemented and offline verified

- [x] Registered Bruno and Newman suites run through a fixed argument list.
- [x] Passing, failing, missing-binary, invalid-reporter, timeout, and
  cancellation fixtures are covered.
- [x] Workflow preview does not start a process. Cycles, duplicate ids, and
  missing assertions are rejected.
- [x] Database and Kafka steps stay unavailable and are not reported as verified.
- [x] Credential values are redacted and are not placed on the command line.
- [ ] Installed `bru` and `newman` were not executed. That remains not
  `LIVE_VERIFIED`.

## Executed verification — Milestone 06

| Command | Exit | Result |
|---|---:|---|
| `uv sync --frozen` | 0 | lockfile used without dependency resolution changes |
| `uv lock --check` | 0 | lock matches project metadata |
| `uv run ruff check .` | 0 | all checks passed |
| `uv run ruff format --check .` | 0 | 293 files already formatted |
| `uv run mypy src` | 0 | no issues in 182 source files |
| `uv run pytest -q` | 0 | 123 passed, 1 skipped |
| `uv build` | 0 | sdist and wheel built |
| `uv run python scripts/structure_audit.py` | 0 | PASS, 348 files, 101 directories, 0 findings |

The skipped test is `tests/integration/test_provider_live.py`. `QA_MCP_LIVE_PROVIDERS`
was not set. API execution tests used a local stand-in process. No Bruno CLI,
Newman CLI, Confluence, Google, or Git host was called. Windows and Linux
execution remains `BLOCKED`.

## Milestone 07 — implemented and offline verified

- [x] Registered PostgreSQL and MySQL assertions bind parameters and reject
  injected SQL.
- [x] Read-only session statements, timeouts, and connection failures stay
  distinct from assertion mismatches.
- [x] Kafka observation validates registered schemas, reports retention gaps,
  missing events, and DLQ hits, and does not commit offsets.
- [x] An E2E workflow records PASS, FAIL, INCONCLUSIVE, and BLOCKED. A missing
  mandatory check cannot become PASS.
- [ ] Live PostgreSQL, MySQL, and Kafka were not contacted. Drivers are not
  bundled, so this is not `LIVE_VERIFIED`.

## Executed verification — Milestone 07

| Command | Exit | Result |
|---|---:|---|
| `uv sync --frozen` | 0 | lockfile used without dependency resolution changes |
| `uv lock --check` | 0 | lock matches project metadata |
| `uv run ruff check .` | 0 | all checks passed |
| `uv run ruff format --check .` | 0 | 295 files already formatted |
| `uv run mypy src` | 0 | no issues in 183 source files |
| `uv run pytest -q` | 0 | 131 passed, 1 skipped |
| `uv build` | 0 | sdist and wheel built |
| `uv run python scripts/structure_audit.py` | 0 | PASS, 354 files, 101 directories, 0 findings |

The skipped test is `tests/integration/test_provider_live.py`. `QA_MCP_LIVE_PROVIDERS`
was not set. Database and Kafka tests used fixture sessions and an in-memory
observer. No PostgreSQL, MySQL, Kafka, Bruno CLI, Newman CLI, Confluence,
Google, or Git host was called. Windows and Linux execution remains `BLOCKED`.

## Milestones 08–11

CI/CD, test management, evidence publication, and release intelligence remain
`SCAFFOLDED` or `NOT_IMPLEMENTED`. Native Windows/Linux execution and Python
3.13 execution remain `BLOCKED`. Writes, Google Sheets, and interactive browser
OAuth are not implemented.
