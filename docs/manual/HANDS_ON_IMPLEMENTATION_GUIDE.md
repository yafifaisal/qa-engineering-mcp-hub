# Hands-on implementation guide: foundation to release

This guide explains how to extend QA Engineering MCP Hub without creating a second
architecture. The [canonical architecture](../architecture/CANONICAL_ARCHITECTURE.md)
and [architecture decisions](../architecture/ARCHITECTURE_DECISIONS.md) are the
authority when any older example or milestone note disagrees.

## Start every milestone safely

1. Read `AGENTS.md`, the canonical architecture, roadmap, scaffold manifest,
   traceability table, progress report, and known limitations.
2. Run the completed quality gates before editing. Record a genuine pre-existing
   failure rather than weakening a check.
3. Confirm the owning module and milestone. Change architecture decisions before
   moving ownership.
4. Verify version-sensitive APIs against current official documentation.
5. Implement one thin vertical slice: contract, service/adapter, surface, security
   policy, deterministic tests, documentation, and traceability.
6. Keep future tool modules out of `mcp/registry.py` until their implementation and
   authorization behavior are verified.
7. Re-run all gates and distinguish offline, simulated, and live evidence.

## Milestone 00 — framework foundation

Milestone 00 is the only implemented milestone in this architecture freeze. Its
runtime path is:

```text
qa-mcp / MCP client
        |
        +--> cli/main.py
        |
        +--> server.py --> app.py --> mcp/registry.py
                                      |-- mcp/tools/system.py
                                      |-- mcp/resources.py
                                      `-- mcp/prompts.py
```

The exact exposed protocol surface is two tools (`hub_health`,
`hub_capabilities`), one resource (`qa-hub://status`), and one prompt
(`qa_hub_orientation`). The in-memory protocol tests and real stdio subprocess test
must agree with this exact allowlist.

To validate M00:

```sh
uv sync --locked
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
uv run qa-mcp --help
uv run qa-mcp doctor
uv run qa-mcp capabilities
uv run python scripts/structure_audit.py
uv build --no-sources
```

Build evidence must come from a fresh artifact. Install the resolved wheel in an
isolated environment, import `qa_mcp_hub`, execute `qa-mcp --help`, and run the smoke
test. A stale file already under `dist/` proves nothing.

## Milestone 01 — profiles and credentials

Owns `config/`, `auth/`, and the scaffolded CLI configuration commands. Implement
atomic configuration writes, schema migration, multiple named profiles and
connections, credential references, environment read-only fallback, and OS keyring
storage. Never put secret values in YAML or MCP arguments. Client-file changes need
a preview and explicit approval.

Exit evidence: permission and migration tests on each supported OS, redaction tests,
profile isolation tests, and an observed credential-store flow. A mocked keyring is
offline evidence only.

## Milestone 02 — provider contracts and registry

Owns `providers/`. Define capability-oriented protocols, normalized records and
source references, typed provider errors, and a strict provider/connection registry.
One provider may have multiple connection IDs and cloud/self-managed editions.
Do not put vendor HTTP endpoints into MCP tools.

Exit evidence: contract suites, unknown-provider rejection, capability checks,
profile isolation, timeout/error normalization, and no registered provider tools.

## Milestone 03 — Git and tickets

Owns GitHub, GitLab, Bitbucket, and Jira adapters plus repository registration and
source resolution. Start read-only. Preserve revision, path, line/issue, provider,
connection, and URL provenance. Treat provider content as untrusted data.

Exit evidence: deterministic contract fixtures for pagination, permission, missing
objects, cloud/self-managed routing, and grounded source references; separately
gated sandbox reads are needed for live verification.

## Milestone 04 — documentation providers

Owns Confluence and Google Docs adapters. Retrieve documents with stable IDs,
versions, headings, and source links. Do not broaden Google Docs into unrestricted
Drive access unless a later decision explicitly changes scope.

Exit evidence: extraction fixtures, version/freshness behavior, pagination,
authorization boundaries, and separately gated live reads.

## Milestone 05 — knowledge and planning

Owns `knowledge/`, `planning/`, and repository indexing coordination. Chunking,
symbol extraction, dependency edges, retrieval, freshness, and source verification
must be deterministic where possible. Generated scenarios are `INFERRED` until
grounded; missing sources are `UNKNOWN`.

Exit evidence: repeatable indexes, stale-revision tests, access-filtered retrieval,
exact source links, and curated cross-repository trace fixtures.

## Milestone 06 — registered API suite execution

Owns Bruno/Postman adapters, `suites/`, and the bounded process runner. Execute only
registered commands assembled by code. Set working directory, environment allowlist,
timeout, output limit, cancellation, and normalized exit/result behavior. Never
offer an arbitrary-command MCP tool.

Exit evidence: pass/fail/timeout/cancel/parser fixtures, executable discovery, secret
redaction, and separately gated local Bruno/Postman smoke tests.

## Milestone 07 — deterministic end-to-end verification

Owns PostgreSQL, MySQL, Kafka, and `verification/`. Database assertions are
registered, parameterized, SELECT-only, row-limited, and time-limited. Kafka reads
use authorized topics and bounded correlation windows and never commit production
consumer offsets. Model prose never decides PASS/FAIL.

Exit evidence: SQL-policy and injection tests, database timeout/row-limit tests,
Kafka authorization/correlation/retention fixtures, and gated non-production live
verification.

## Milestone 08 — CI/CD visibility and approved actions

Owns Bitbucket Pipelines, GitHub Actions, and Jenkins adapters. Normalize pipeline,
step, log, and artifact state. Reads remain scoped. Triggers and cancellations need
an explicit capability, preview, approval, and audit record.

Exit evidence: pagination/state/artifact fixtures, permission and rate-limit errors,
write-denial tests, and separately approved sandbox actions.

## Milestone 09 — test management

Owns Xray, TestRail, CSV/XLSX, and Google Sheets adapters. Map through one canonical
test-case model, preserve original IDs, and emit loss reports. Imports and
publication require preview and approval. Spreadsheet exports defend against formula
injection and accidental overwrite.

Exit evidence: round-trip fixtures, edition routing, pagination, malformed data,
formula safety, idempotency, write-denial, and gated sandbox reads/writes.

## Milestone 10 — evidence and release intelligence

Owns `evidence/` and `release/`. Evidence policy specifies required facts;
redaction happens before persistence. Manifests contain hashes and provenance.
Release reports compute coverage gaps, blockers, and evidence completeness but never
auto-approve a release. Missing required evidence is explicit and cannot be silently
treated as PASS.

Exit evidence: redaction leak tests, deterministic manifests/hashes, completeness
rules, coverage/risk fixtures, publication approval, and reproducible reports.

## Milestone 11 — community release

Owns final packaging, compatibility matrices, migration notes, security/release
workflows, and public support policy. No milestone may be marked live-verified from
mocks or file existence.

Exit evidence: all supported OS/Python CI, isolated installation, signed/reviewed
artifacts where configured, complete documentation and traceability, and an explicit
list of provider environments actually tested.

## Finding and verification language

Use only these finding classes in analysis:

- `VERIFIED`: deterministic evidence directly supports the statement.
- `INFERRED`: evidence supports but does not prove the statement.
- `UNKNOWN`: required evidence is unavailable.
- `CONFLICTING`: trustworthy sources disagree.

Use only the requirement statuses defined by the project: `NOT_IMPLEMENTED`,
`SCAFFOLDED`, `IMPLEMENTED`, `OFFLINE_VERIFIED`, `LIVE_VERIFIED`, and `BLOCKED`.
Existence is not implementation; a mock is not a live provider test; simulated
Windows paths are not live Windows execution.

## Official references

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP](https://gofastmcp.com/)
- [uv](https://docs.astral.sh/uv/)
- [Pydantic](https://docs.pydantic.dev/)
- [Typer](https://typer.tiangolo.com/)
- [pytest](https://docs.pytest.org/)
- [Codex MCP](https://developers.openai.com/codex/mcp)
