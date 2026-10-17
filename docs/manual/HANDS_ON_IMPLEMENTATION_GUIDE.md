# QA Engineering MCP Hub — Hands-on Implementation Manual

**Audience:** QA engineers learning to implement the platform manually.  
**Scope:** Milestones 00–11, Community Edition, Python 3.12+, `uv`, standalone `fastmcp`, Typer, Pydantic.  
**Source baseline:** The Milestone 00 project distributed alongside this manual.  
**Rule:** Never mark a requirement PASS because code exists. PASS requires a passing automated test plus (where applicable) provider sandbox verification.

## 0. How to work through this manual

Follow milestones in order. For EACH new file: (1) understand its responsibility, (2) create it, (3) type the code, (4) run one focused unit test, (5) run the milestone suite, (6) record results in `docs/implementation/PROGRESS.md`. Commit after each passing milestone. Do not commit tokens, provider payloads containing PII, `.env`, `.venv`, or evidence files.

**Terms:** MCP *tool* exposes a callable capability to Codex. An *adapter* implements a vendor API. A *service* executes QA rules. A *profile* selects a company's configured connections. A *credential store* keeps secrets independently from the profile. An *assertion* deterministically decides whether a test condition passes.

### A. Install prerequisites

macOS Terminal:
```bash
brew install uv git
uv python install 3.12
uv --version
```
Windows PowerShell:
```powershell
winget install --id astral-sh.uv -e
uv python install 3.12
uv --version
```
Linux (approved installation method): see https://docs.astral.sh/uv/getting-started/installation/; then `uv python install 3.12`.

Extract the supplied ZIP, open its project root in VS Code, and run:
```bash
uv sync
uv run qa-mcp --help
uv run qa-mcp doctor
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```
**Stop if any command fails.** Investigate the actual diagnostic. Commit `uv.lock` after a successful sync. `uv run qa-mcp serve` uses stdio; its lack of terminal output is normal.

### B. Universal completion commands

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q
uv build
```
For every adapter also run a *separate*, opt-in smoke test against a permitted sandbox, with credentials configured. Offline mocks prove contract handling, **not** live authentication, permission boundaries, or third-party availability.

### C. Common failure modes

| Symptom | Diagnose | Resolution |
|---|---|---|
| `uv: command not found` | `which uv` / `Get-Command uv` | Reopen terminal, fix PATH |
| Python mismatch | `uv run python --version` | `uv python install 3.12`, `uv sync --python 3.12` |
| Import error | `uv run python -c 'import qa_mcp_hub'` | Run inside project; verify build backend and source layout |
| MCP tool absent | `uv run pytest tests/integration` | Check decorator + server registration; restart Codex session |
| Credential missing | `qa-mcp integrations test <id>` | Correct profile and credential reference; never paste token into chat |
| API 401 / 403 | Provider account/scopes/URL | Reauthorize and reduce permissions to necessary minimum |
| Rate limit | Provider headers | Respect retry-after; bounded retry with jitter |
| Stale knowledge | indexed SHA vs current SHA | Re-index or disclose revision mismatch |
| Tool PASS but test FAIL | Inspect separate operation/test statuses | Never equate successful invocation with passed assertion |

---

## 00. Foundation — Existing starter package

**Goal:** a real installable Python package, a Typer CLI and two observable MCP tools.

**Files already in starter:**
- `pyproject.toml`: package metadata, dependencies, build backend, CLI script, lint/type/test settings.
- `.python-version`: requested Python interpreter.
- `src/qa_mcp_hub/__init__.py`: package and version.
- `src/qa_mcp_hub/server.py`: FastMCP instance and `hub_health`, `hub_capabilities`.
- `src/qa_mcp_hub/cli.py`: `serve`, `doctor`, `capabilities` command group.
- `src/qa_mcp_hub/config.py`: typed baseline settings and native OS config paths.
- `src/qa_mcp_hub/capabilities.py`: implemented vs planned contract.
- `tests/unit/test_core.py`: type/config/status/path tests.
- `tests/integration/test_cli.py`: CLI command tests.
- `tests/integration/test_mcp_protocol.py`: FastMCP tool list and call tests.
- `AGENTS.md`, `README.md`, `docs/...`: human instructions, architectural constraints, progress and traceability.

**Manual step 1:** read `pyproject.toml`. `[project.scripts]` means `uv run qa-mcp` calls `qa_mcp_hub.cli:main`. `[build-system]` makes the `src/` package installable.

**Manual step 2:** read `server.py`. Decorator `@mcp.tool` registers a typed Python function for MCP clients; `mcp.run(transport='stdio')` communicates over standard input/output. Do not print to stdout in server mode.

**Manual step 3:** use `uv run qa-mcp capabilities`, then inspect actual MCP invocation test; a unit test calling `hub_health()` alone does **not** prove tool discovery.

**Manual step 4:** register in Codex using an absolute project path:
```bash
codex mcp add qa-hub -- uv run --project /ABSOLUTE/PATH/qa-engineering-mcp-hub qa-mcp serve
codex mcp list
```
On Windows, run the same command from PowerShell with the native absolute path. If necessary use the absolute path to `uv.exe` found with `where.exe uv`. Codex stores MCP settings in `~/.codex/config.toml` (Windows equivalent: `%USERPROFILE%\.codex\config.toml`). Do not include literal provider tokens.

**Exit gate:** all universal commands pass; MCP integration test proves both discovery and invocation; human confirms `hub_health` in Codex. Until then milestone is NOT VERIFIED.

---

## 01. Profiles, credentials, configuration and wizard

**Goal:** same package works on Windows/macOS/Linux; each person can select profiles, providers, and secret backends without editing Python code.

### 01.1 Add dependencies
```bash
uv add pyyaml keyring httpx platformdirs
uv add --dev respx
uv sync
```
Typer, Rich, Pydantic are already in M00. `platformdirs` provides OS-correct user config location.

### 01.2 Create files in this exact order

1. `src/qa_mcp_hub/core/__init__.py` — package marker.
2. `src/qa_mcp_hub/core/models.py` — Pydantic `ProviderKind`, `Connection`, `Profile`, `HubConfig` and schema version.
3. `src/qa_mcp_hub/core/path_service.py` — native OS config root (`platformdirs.user_config_dir('qa-mcp-hub')`) with test override injection.
4. `src/qa_mcp_hub/core/config_repository.py` — safe YAML load, validation, atomic write, file permissions, backup-on-migration.
5. `src/qa_mcp_hub/core/config_resolver.py` — precedence: explicit CLI values > explicitly set env overrides > profile YAML > defaults; secret references are NEVER silently resolved from YAML values.
6. `src/qa_mcp_hub/core/migrations.py` — schema version 1 registry; reject unsupported newer versions; backups and idempotence.
7. `src/qa_mcp_hub/auth/__init__.py` — package marker.
8. `src/qa_mcp_hub/auth/contracts.py` — `CredentialStore` protocol: `get`, `set`, `delete`.
9. `src/qa_mcp_hub/auth/keyring_store.py` — secure OS store using `keyring`, with provider+host+account+profile identifier.
10. `src/qa_mcp_hub/auth/env_store.py` — read-only environment backend; never write to a persistent `.env` automatically.
11. `src/qa_mcp_hub/auth/resolver.py` — selects backend and resolves a credential **inside provider adapter**, never MCP tool arguments.
12. `src/qa_mcp_hub/core/redaction.py` — redacts `Authorization`, `Cookie`, `password`, `api_key`, token-shaped strings in logs and evidence.
13. `src/qa_mcp_hub/cli/setup.py` — Typer + Rich wizard; never echo secrets; `getpass.getpass()` when applicable; provider-specific choices.
14. `src/qa_mcp_hub/cli/profiles.py` — list/add/use/remove profiles with confirmation and collision rules.
15. `src/qa_mcp_hub/cli/integrations.py` — add/auth/test/rotate/remove; `test` must call a real provider-specific diagnostic (or mark unsupported, never fake connected).
16. `src/qa_mcp_hub/cli/config.py` — display sanitized effective config and current profile.
17. `src/qa_mcp_hub/cli/clients.py` — render Codex TOML and client-specific JSON with `command`/`args`; no inline secret. Test exact client schema.
18. Extend existing `src/qa_mcp_hub/cli.py` to register Typer subapps. Avoid ambiguous duplicate `qa-mcp` entrypoints.

### 01.3 Canonical typed models (type manually)

`src/qa_mcp_hub/core/models.py`:
```python
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ProviderKind(StrEnum):
    github = "github"
    gitlab = "gitlab"
    bitbucket = "bitbucket"
    jira = "jira"
    confluence = "confluence"
    google_docs = "google_docs"
    bruno = "bruno"
    postman = "postman"
    postgresql = "postgresql"
    mysql = "mysql"
    kafka = "kafka"
    bitbucket_pipelines = "bitbucket_pipelines"
    github_actions = "github_actions"
    jenkins = "jenkins"
    xray = "xray"
    testrail = "testrail"
    spreadsheet = "spreadsheet"


class Connection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    provider: ProviderKind
    base_url: str | None = None
    credential_ref: str | None = None  # reference only
    enabled: bool = True


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connections: list[Connection] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_connections(self) -> "Profile":
        ids = [item.id for item in self.connections]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate connection id in profile")
        return self


class HubConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    active_profile: str
    profiles: dict[str, Profile]

    @model_validator(mode="after")
    def active_profile_exists(self) -> "HubConfig":
        if self.active_profile not in self.profiles:
            raise ValueError("Active profile does not exist")
        return self
```

**Important:** Two Jira instances are permitted in one profile if they have different `id`s. Two items with same ID are forbidden. Make connection IDs stable and do not use `provider` alone as the credential key.

### 01.4 Credential backend contract

`src/qa_mcp_hub/auth/contracts.py`:
```python
from typing import Protocol


class CredentialStore(Protocol):
    def get(self, credential_id: str) -> str | None: ...
    def set(self, credential_id: str, secret: str) -> None: ...
    def delete(self, credential_id: str) -> None: ...
```

`src/qa_mcp_hub/auth/keyring_store.py`:
```python
import keyring


class KeyringStore:
    SERVICE = "qa-engineering-mcp-hub"

    def get(self, credential_id: str) -> str | None:
        return keyring.get_password(self.SERVICE, credential_id)

    def set(self, credential_id: str, secret: str) -> None:
        if not secret:
            raise ValueError("Empty secret")
        keyring.set_password(self.SERVICE, credential_id, secret)

    def delete(self, credential_id: str) -> None:
        keyring.delete_password(self.SERVICE, credential_id)
```

Implement `EnvStore` as read-only: `get` retrieves `os.environ[credential_id]` if present; `set`/`delete` raise `NotImplementedError`. Unit tests must mock keyring; never save a real token in automated tests.

### 01.5 Create configuration files safely

Canonical YAML location: `platformdirs.user_config_dir('qa-mcp-hub')/config.yaml`, which varies by OS. Allow `QA_MCP_CONFIG_FILE` override for integration tests and automation, validate it before use. Example:
```yaml
schema_version: 1
active_profile: personal-dev
profiles:
  personal-dev:
    connections:
      - id: jira-primary
        provider: jira
        base_url: https://example.atlassian.net
        credential_ref: personal-dev/jira/example.atlassian.net/qa-user
        enabled: true
```
Use `yaml.safe_load`; create a validated model; save with temporary file + `os.replace`; set user-only permissions where supported; create a backup BEFORE migration. Never store `token:` or `password:` in this file.

### 01.6 CLI commands that MUST be operational

```text
qa-mcp setup
qa-mcp profiles list
qa-mcp profiles add NAME
qa-mcp profiles use NAME
qa-mcp integrations add PROVIDER
qa-mcp integrations auth CONNECTION_ID
qa-mcp integrations test CONNECTION_ID
qa-mcp integrations rotate CONNECTION_ID
qa-mcp integrations remove CONNECTION_ID
qa-mcp config show
qa-mcp doctor
qa-mcp clients generate codex
qa-mcp clients generate cursor
```
`integrations test` must distinguish `CONNECTED`, `MISSING_CREDENTIAL`, `UNSUPPORTED`, `UNREACHABLE`, `UNAUTHORIZED`, `FORBIDDEN`; do not print secret or raw authentication headers. Setup wizard never assumes OAuth is available. `doctor` checks installed runners and provider availability without running destructive work.

### 01.7 Client config generation

Codex renders TOML equivalent to:
```toml
[mcp_servers.qa-hub]
command = "uvx"
args = ["--from", "qa-engineering-mcp-hub==1.0.0", "qa-mcp", "serve"]
```
For local development use `uv run --project ABSOLUTE_PROJECT_PATH qa-mcp serve` instead. For clients with JSON `mcpServers`, render their **documented** schema. Never invent a universal JSON spec; some clients differ. Avoid writing the config to user files without preview and confirmation. Do not emit token values.

### 01.8 Tests to write

- `tests/unit/test_profile_models.py`: valid profile; missing active profile; duplicate IDs rejected; duplicate providers with distinct IDs accepted; unsupported provider rejected.
- `tests/unit/test_config_resolver.py`: precedence and no accidental secret merging; missing env var rejected; schema migration idempotence; backup created.
- `tests/unit/test_keyring_store.py`: mocked `keyring` get/set/delete; secrets never logged.
- `tests/unit/test_redaction.py`: hide headers, bearer tokens, cookies and nested JSON values.
- `tests/unit/test_paths.py`: mock platformdirs result for Windows/macOS/Linux; do not assert actual OS path literals on nonmatching OS.
- `tests/integration/test_cli_profiles.py`: Typer `CliRunner`, profile switch, duplicate connection handling.
- `tests/integration/test_cli_clients.py`: TOML parsing through `tomllib`, JSON parsing through `json`, no tokens, valid absolute paths.
- `tests/security/test_profile_isolation.py`: credentials and documents never cross profile boundaries.

**Manual verification:** create two profiles; register two Jira connections with different IDs; rotate only one credential; switch profile; verify wrong-profile access returns DENIED. Run universal gate. Update progress and known limitations.

---

## 02. Provider contracts and capability registry

### Create files
- `src/qa_mcp_hub/providers/contracts.py` — typed `GitProvider`, `TicketProvider`, `DocumentProvider`, `ApiRunner`, `DatabaseVerifier`, `EventProvider`, `CiProvider`, `TestManagementProvider` Python `Protocol`s.
- `src/qa_mcp_hub/providers/models.py` — normalized `SourceRef`, `Issue`, `Document`, `TestCase`, `TestRun`, `AssertionResult`, `EvidenceRef`, `PipelineRun` with Pydantic validators.
- `src/qa_mcp_hub/providers/registry.py` — static allowlist of supported identifiers; per-connection factory and `capabilities` flags.
- `src/qa_mcp_hub/providers/errors.py` — typed `AuthError`, `PermissionError`, `RateLimitError`, `NotFoundError`, `UnavailableError`, `NotSupportedError`.
- `src/qa_mcp_hub/providers/http.py` — shared HTTPX adapter: timeouts, safe redirects policy, retry only idempotent operations, pagination helpers, no secret logging.
- `src/qa_mcp_hub/providers/fakes.py` — deterministic fake provider implementations for tests.
- `src/qa_mcp_hub/modules/tools.py` — thin MCP wrappers that resolve authorized profile/adapter.

### Type a common source contract
```python
from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    provider: str
    repository_or_document: str
    revision: str | None = None
    path: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    url: str | None = None


class ToolResult(BaseModel):
    operation_status: str  # SUCCESS or ERROR
    data: dict[str, object] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

Each integration uses a provider-specific adapter implementing shared interfaces. Tool names remain vendor-neutral (`search_code`, `read_issue`) but response includes provider identity. **No generic arbitrary URL caller.** Configuration and DNS/redirect checks must prevent SSRF, especially for remote hosting.

**Tests:** registry rejects unknown names; factory injects correct connection/profile; fake implementation passes provider contract suite; errors are mapped and sanitized. **Gate:** MCP tools pass in-memory fake provider tests before real adapters.

---

## 03. GitHub, GitLab, Bitbucket and Jira

### Create files, in order
- `src/qa_mcp_hub/adapters/git/github.py` — repositories, branch, file content, commits, PR diff/status.
- `src/qa_mcp_hub/adapters/git/gitlab.py` — project, file, branch, commits, merge request diff.
- `src/qa_mcp_hub/adapters/git/bitbucket.py` — distinguish Bitbucket Cloud vs Data Center; repositories, commits, PR/diffs.
- `src/qa_mcp_hub/adapters/tickets/jira.py` — search issues, get issue, linked issues and comments.
- `src/qa_mcp_hub/services/source_resolver.py` — normalize URL, path, SHA, line ranges; reject claims without a grounded location.
- `src/qa_mcp_hub/modules/knowledge/tools.py` — `search_code`, `get_file_at_revision`, `read_jira_issue`, `related_prs`.

### Integration rules
- GitHub: use provider-supported scoped token/GitHub App, GitHub REST or GraphQL as required; respect API rate limits.
- GitLab: use documented REST routes (`/api/v4/...`); distinguish personal/project/group tokens; URL-encode project path properly.
- Bitbucket: Cloud (`api.bitbucket.org/2.0`) and Data Center use different routes and token models; implement distinct subclasses.
- Jira: Cloud and Data Center have different endpoints/auth; Jira Cloud issue retrieval generally `/rest/api/3/issue/{issueKey}`; do not assume Jira Cloud email/token Basic works for Data Center.

### Manual TDD sequence per adapter
1. Find provider's current official API docs and record endpoint/auth in `docs/providers/<provider>.md`.
2. Define request and normalized response fixture from docs with ALL secrets fictional.
3. Write HTTPX mocked success test, pagination test, 401/403/404 test, 429 test and timeout test.
4. Implement minimal authenticated `httpx.AsyncClient` through credential resolver.
5. Implement one endpoint, run its focused tests, then implement next endpoint.
6. Add `QA_LIVE_TESTS=1` guarded sandbox test (never run in ordinary CI); live test asserts read scope and source revision.
7. Add one MCP tool test using the adapter and a mocked execution context.

**Gate:** all four vendors pass contract tests; sandbox tests pass individually where credentials exist; untested provider endpoints remain explicitly `NOT_LIVE_VERIFIED`.

---

## 04. Confluence and Google Docs

### Create
- `adapters/documentation/confluence.py` — search/read pages, page version and canonical links; Cloud/Data Center route differentiation.
- `adapters/documentation/google_docs.py` — document get, typed section extraction, revision data; Google Docs API.
- `adapters/documentation/google_drive_discovery.py` — narrowly scoped Drive search **only** to discover Google Docs IDs; no general Drive integration.
- `services/document_extraction.py` — strip formatting safely, preserve headings and source IDs.
- `tests/fixtures/docs/` — fictional docs examples with tables/empty sections.

**Google auth:** device/browser OAuth with minimum scopes when supported; token stored in OS keyring or authorized secret store. Do not rely on a service account magically seeing personal Docs. Use delegated permission when appropriate and approved.

**Tests:** pagination, blocked access, document not found, empty doc, large doc, title/version, merged text spans, source URL. Avoid rendering untrusted document instructions as system prompts. **Gate:** both adapters return grounded document text with stable IDs.

---

## 05. Cross-repository knowledge engine

### Create
- `indexing/sync.py`: per-profile allowed repository/document sync, scheduled or on demand.
- `indexing/chunker.py`: deterministic content chunks with revision and line/section metadata.
- `indexing/symbols.py`: language-aware code parser interface; prefer AST/tree-sitter where implemented.
- `indexing/graph.py`: store typed edges (`CALLS`, `IMPORTS`, `PRODUCES_EVENT`, `CONSUMES_EVENT`, `USES_TABLE`) with exact supporting evidence.
- `indexing/storage.py`: local SQLite FTS5 for Community MVP; optional pgvector later.
- `services/knowledge_search.py`: keyword + symbol results; reranking optional; source verification before final answer.
- `modules/knowledge/tools.py`: `search_knowledge`, `find_implementation`, `trace_business_flow`, `analyze_diff`.

**Critical:** a search match is NOT proof of a runtime call. For each edge, preserve source/commit/evidence and mark `VERIFIED`, `INFERRED`, `UNKNOWN` or `CONFLICTING`. Respect access authorization when storing or retrieving each chunk.

**Tests:** different commits don't mix; two profiles cannot retrieve each other's chunks; stale index indicated; exact source links; unknown edge stays unknown; unsupported programming languages return `UNSUPPORTED`, not false graph. **Gate:** at least one curated cross-repo fixture traces real known edges without fabricated dependencies.

---

## 06. Bruno and Postman safe execution

### Create
- `adapters/api/bruno.py`: discover registered suites, run installed Bruno CLI, parse supported reporter output.
- `adapters/api/postman.py`: discover registered collections, use verified Postman CLI or Newman runner for the pinned version, parse output.
- `runners/registry.py`: suite ID maps to fixed filesystem path and approved runner; no user-controlled command strings.
- `runners/process.py`: subprocess with argument list only; restricted cwd, env allowlist, max wall-clock time, sanitized stderr/stdout.
- `runners/models.py`: `ExecutionRecord`, `AssertionRecord`, `TestStatus` (PASSED/FAILED/etc.).
- `runners/executor.py`: enforce policy, enqueue/run, persist results and artifacts.
- `modules/execution/tools.py`: `list_suites`, `submit_test_run`, `get_test_run`.

**Safe subprocess skeleton:**
```python
import asyncio


async def execute_checked(
    argv: list[str], cwd: str, timeout: float
) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise
    return process.returncode or 0, stdout, stderr
```
**Harden it:** reject paths outside registered suite roots, cap output bytes, sanitize environment, protect from runner child processes, bound concurrency, deny production by policy, and separate CLI invocation SUCCESS from assertion PASSED.

**Tests:** registered suite succeeds/fails, missing executable, timeout, malicious suite ID, path escape, secrets not in output, exit code/assertion mismatch. **Gate:** real local Bruno and Postman fixture suites produce normalized results and failure evidence.

---

## 07. PostgreSQL, MySQL and Kafka

### Create
- `adapters/database/postgresql.py`: SQLAlchemy+psycopg connector with read-only DB account and statement_timeout.
- `adapters/database/mysql.py`: SQLAlchemy+PyMySQL connector with read-only DB account and session limits.
- `services/database_assertions.py`: *registered parameterized SELECT-only assertions*, approved connection, bound args, row cap.
- `adapters/streaming/kafka.py`: confluent-kafka, scoped topic metadata, approved diagnostic subscriptions, indexed correlation where available.
- `services/e2e_polling.py`: bounded polling with monotonic deadline and explicit timeout.
- `modules/verification/tools.py`: `verify_assertion`, `find_event`, `verify_workflow`.

**Policy:** SQL string must come from reviewed assertion files; deny multiple statements, arbitrary DDL/DML and external prompt-generated queries. Database read-only server account remains primary safeguard; syntax filtering alone is inadequate. For Kafka, avoid joining live consumer groups or committing offsets for diagnostics. A missing message due to retention/search gaps is INCONCLUSIVE, not FAILED by default.

**Tests:** malicious SQL rejected, missing credential, expired DB session, empty result, polling timeout, eventual success, DLQ unavailable, event correlation mismatch, no offsets committed. **Gate:** approved UAT transaction demonstrates API + DB + Kafka correlation; missing traces are shown as INCONCLUSIVE.

---

## 08. Bitbucket Pipelines, GitHub Actions and Jenkins

### Create
- `adapters/cicd/bitbucket_pipelines.py`
- `adapters/cicd/github_actions.py`
- `adapters/cicd/jenkins.py`
- `services/pipeline_service.py` (normalize run/build/steps/artifacts)
- `modules/cicd/tools.py` (`get_pipeline`, `list_runs`, `get_artifacts`, optional `submit_approved_run`).

**Implementation pattern:** read-only first. Each adapter needs typed identity for project, pipeline/workflow/job, run ID and revision; pagination; log truncation; artifact expiration handling. Jenkins instance auth and CSRF crumb requirements differ by configuration. Add write only with explicit reviewed allowlist, user confirmation and idempotency.

**Tests:** queued/running/passed/failed/cancelled, missing artifact, 403, pagination, triggering denied by default. **Gate:** actual sandbox read operations verified on all three providers.

---

## 09. Xray, TestRail and Spreadsheet

### Create
- `providers/testcase_models.py`: canonical Scenario, Priority, Test Case, Precondition, Steps, Expected Result, Result, Notes, Evidence, external IDs.
- `adapters/test_management/xray.py`: separate Cloud/Data Center API versions, read sets/plans/executions, optional approved import.
- `adapters/test_management/testrail.py`: suite/project/sections/cases/runs/results, paginated results, optional approved publication.
- `adapters/test_management/spreadsheet.py`: `openpyxl` XLSX, `csv` stdlib CSV, explicit user-confirmed mapping, preview/dry run.
- `adapters/test_management/google_sheets.py`: optional spreadsheet provider backed by Google Sheets API and minimum scopes (within Spreadsheet scope).
- `services/testcase_mapping.py`: normalized conversion, field validation, keep original IDs and loss reports.
- `modules/test_management/tools.py`: `search_test_cases`, `import_cases_preview`, `publish_approved_cases`.

**Tests:** Xray Cloud/DC difference, TestRail pagination, column names out of order, empty cells, formulas, dangerous CSV formula input when exporting, duplicate external IDs, roundtrip export/import, no implicit overwrite. **Gate:** one sample suite roundtrips with no silent data loss and real sandbox reads for Xray and TestRail.

---

## 10. Evidence and release readiness

### Create
- `evidence/schema.py`: `EvidenceManifest`, verification category with PASSED/FAILED/NOT_EXECUTED/NOT_APPLICABLE/INCONCLUSIVE.
- `evidence/normalize.py`: runner output to canonical assertions.
- `evidence/redact.py`: sanitize secrets and PII before persistence/publication.
- `evidence/render.py`: JSON/HTML output via Jinja2 with escaping enabled.
- `evidence/storage.py`: local per-profile evidence directory, SHA256 manifests, retention and secure permissions.
- `evidence/publish.py`: optional Jira/Xray/TestRail output with explicit approval, idempotency key and safe retries.
- `release/coverage.py`: requirements → cases → run records mapping.
- `release/risk.py`: compute open blockers, gaps and evidence completeness, never auto-sign-off.
- `modules/evidence/tools.py`, `modules/release/tools.py`.

**Invariant:** API-only evidence never claims DB/Kafka verification. HTTP 200 != test passed; process completed != all checks passed. Unexecuted cases must not become PASSED. Evidence with credentials/PII is a security failure, not a valid artifact.

**Tests:** HTML escapes untrusted text, redaction, checksum tampering, partial evidence, duplicate publishing, wrong-profile artifact, release blockers, manual approval requirement. **Gate:** generate matching JSON/HTML evidence for API-only and E2E fixtures; publish only after explicit approval.

---

## 11. Cross-platform packaging and community release

### Create
- `docs/getting-started/windows.md`, `macos.md`, `linux.md` with exact uv, keyring, Codex setup and troubleshooting.
- `docs/providers/<provider>.md` for each of the 17 provider identifiers (including separate spreadsheet formats as appropriate).
- `examples/config/` sanitized YAML profiles for Bitbucket+Bruno and GitLab+Postman.
- `.github/workflows/ci.yml`: GitHub Actions matrix Windows/macOS/Ubuntu, 3.12+ runtime, `uv sync --frozen`, lint, mypy, pytest, build; no live tokens.
- `.github/workflows/publish.yml`: protected tagged release + trusted publishing (explicit approval).
- `LICENSE`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/PRIVACY.md`.

### Exact release procedure
1. Finish all offline gates and *record* live provider smoke checks independently.
2. Check licensing and ensure no company source code, credentials, customer data, URLs or evidence are included.
3. `uv lock`, commit lockfile; `uv sync --frozen`.
4. `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`.
5. `uv build`, inspect `dist/` and wheel contents.
6. Install built wheel in a fresh isolated environment; run `qa-mcp --help`, `qa-mcp doctor`, tool discovery test.
7. Test Windows Credential Manager, macOS Keychain and Linux Secret Service/explicit env fallback *on their corresponding OS*. Linux headless keyring is not always available.
8. Test clean Codex registration for each OS. Use absolute paths and client-specific configuration.
9. Publish to TestPyPI and perform clean-user installation; never assume PyPI name availability.
10. Obtain release approval, then publish to PyPI with trusted publisher; verify package metadata and `uvx` execution.
11. Mark unsupported/unverified providers prominently. Do not advertise entire provider matrix as live verified without evidence.

---

## Requirement traceability and acceptance matrix

| ID | Requirement | Primary implementation | Automated verification | Live gate |
|---|---|---|---|---|
| R00 | Python+uv+FastMCP package | `pyproject.toml`, `server.py` | MCP integration, build | Codex smoke |
| R01 | Windows/macOS/Linux | `core/path_service.py`, CLI | Platform mocked tests + CI matrix | Native OS install |
| R02 | Wizard/YAML/env config | `cli/`, `core/config_*` | CLI and precedence tests | User onboarding |
| R03 | Multi-profile, multi-instance | `core/models.py` | isolation, duplicate-ID tests | Two profile demo |
| R04 | Keyring/env/OAuth interface | `auth/` | credential mocks, redaction | Local token/OAuth provider test |
| R05 | GitHub/GitLab/Bitbucket | `adapters/git/` | contract tests | 3 sandbox smoke runs |
| R06 | Jira | `adapters/tickets/jira.py` | contract + pagination | Jira sandbox read |
| R07 | Confluence/Google Docs | `adapters/documentation/` | document extraction + auth tests | 2 live reads |
| R08 | Bruno/Postman | `adapters/api/`, `runners/` | runner pass/fail/timeout | 2 runner fixtures |
| R09 | PostgreSQL/MySQL | `adapters/database/` | read-only + injection tests | 2 read-only UAT reads |
| R10 | Kafka | `adapters/streaming/kafka.py` | metadata/event/offset tests | approved topic test |
| R11 | Bitbucket Pipelines/GitHub Actions/Jenkins | `adapters/cicd/` | contract, auth, pagination | 3 sandbox reads |
| R12 | Xray/TestRail/Spreadsheet | `adapters/test_management/` | mapping + import/export | 2 sandbox reads + local spreadsheet |
| R13 | Knowledge source grounding | `indexing/`, `services/` | stale SHA, citations, access | curated cross-repo workflow |
| R14 | Evidence integrity | `evidence/` | hash, redaction, partial status | reviewed report |
| R15 | Manual release readiness | `release/` | blocker + review tests | QA reviewer demo |
| R16 | Public package distribution | packaging + CI docs | build, install, matrix | TestPyPI then approved PyPI |

For each row record **NOT_STARTED → IMPLEMENTED → OFFLINE_VERIFIED → LIVE_VERIFIED**, separately. A requirement is fully complete only when the required live gate passes; providers that require unavailable sandbox credentials must remain NOT_LIVE_VERIFIED.

## Progress log template (copy for every milestone)

```text
Milestone: XX
Start commit: <SHA>
Files created/changed:
- ...
Actual commands run:
- uv sync --frozen : PASS/FAIL/NOT_RUN
- ruff check : PASS/FAIL/NOT_RUN
- ruff format --check : PASS/FAIL/NOT_RUN
- mypy src : PASS/FAIL/NOT_RUN
- pytest : PASS/FAIL/NOT_RUN
- uv build : PASS/FAIL/NOT_RUN
Live provider validation: PASS/FAIL/NOT_AVAILABLE
Defects/failures: ...
Limitations: ...
Final acceptance: VERIFIED / BLOCKED / PARTIAL
```

## Official documentation shortcuts

- MCP protocol: https://modelcontextprotocol.io/
- Standalone FastMCP: https://gofastmcp.com/
- uv: https://docs.astral.sh/uv/
- Codex MCP: https://developers.openai.com/codex/mcp
- Pydantic: https://docs.pydantic.dev/
- GitHub REST: https://docs.github.com/en/rest
- GitLab API: https://docs.gitlab.com/api/
- Atlassian APIs: https://developer.atlassian.com/
- Google Docs: https://developers.google.com/workspace/docs/api
- Bruno: https://docs.usebruno.com/
- Postman CLI: https://learning.postman.com/docs/postman-cli/
- Kafka: https://kafka.apache.org/documentation/

**Never trust hardcoded API assumptions:** before implementing each adapter, verify the exact current vendor API docs and pin tested versions. Public documentation cannot validate private Jira/Bitbucket/Jenkins instances.
