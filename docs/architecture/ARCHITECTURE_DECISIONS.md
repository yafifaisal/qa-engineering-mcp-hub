# Architecture decisions

This log records decisions that freeze the Milestone 00 architecture. New
structural changes must be added here before code is moved or ownership changes.

## ADR-001 — Separate framework, QA Workspace, and machine configuration

- **Status:** Accepted
- **Decision:** Keep reusable package code, company-specific QA assets, and
  machine-specific configuration in three different roots.
- **Reason:** It prevents credentials and company data from entering the public
  framework and lets one installation work with multiple companies and profiles.
- **Consequence:** Workspace/config paths are references; the package ships only
  sanitized examples and a generic workspace template.

## ADR-002 — Standalone FastMCP over stdio for Milestone 00

- **Status:** Accepted
- **Decision:** Use `fastmcp` directly and expose only stdio in M00.
- **Reason:** Codex and other local MCP clients can manage the subprocess without a
  listening socket or remote authentication surface.
- **Consequence:** stdout is reserved for protocol messages; remote HTTP and OAuth
  remain future work.

## ADR-003 — Explicit MCP registration allowlist

- **Status:** Accepted
- **Decision:** `mcp/registry.py` registers the M00 tool, resource, and prompt
  modules explicitly. Future tool modules are never discovered by filesystem scan.
- **Reason:** A scaffold file must not accidentally expose an unimplemented or
  write-capable operation.
- **Consequence:** Adding a tool requires a registry change and a protocol test.

## ADR-004 — Thin surfaces, typed services, isolated adapters

- **Status:** Accepted
- **Decision:** MCP and Typer functions translate inputs/outputs only. Domain
  services own orchestration and provider adapters own external APIs/CLIs.
- **Reason:** Protocol presentation, deterministic QA logic, and vendor behavior
  change at different rates and need independent tests.
- **Consequence:** Direct vendor SDK/HTTP/process imports in MCP tool modules are an
  architecture violation.

## ADR-005 — Atomic `cli` and `config` package migration

- **Status:** Accepted
- **Decision:** Replace the colliding `cli.py`/`cli/` and `config.py`/`config/`
  layouts in one change. Package `__init__.py` files re-export the established
  public names.
- **Reason:** Adding an initializer before moving code changes Python import
  resolution and breaks the console entry point.
- **Consequence:** The entry point becomes `qa_mcp_hub.cli.main:main`; existing
  imports from `qa_mcp_hub.cli` and `qa_mcp_hub.config` remain valid.

## ADR-006 — One canonical domain tree; no duplicate service layer

- **Status:** Accepted
- **Decision:** Replace `modules/`, `indexing/`, and generic `services/` ownership
  with `mcp/tools/`, `knowledge/`, and the relevant domain packages.
- **Reason:** Two names for the same responsibility cause competing implementations
  and unclear test ownership.
- **Consequence:** Old empty placeholders are removed. Historical path mappings are
  retained in implementation documentation, not compatibility modules with no
  users.

## ADR-007 — Exact supported-provider allowlist

- **Status:** Accepted
- **Decision:** Support only the providers named in the canonical architecture.
- **Reason:** A bounded scope allows complete documentation, security review, and
  predictable configuration.
- **Consequence:** Other providers require a later ADR and roadmap change. All
  allowed provider integrations remain `NOT_IMPLEMENTED` in M00.

## ADR-008 — Credential references, never plaintext configuration

- **Status:** Accepted
- **Decision:** Normal configuration may store only opaque credential references.
  Secret values live in an approved credential store or explicit process
  environment.
- **Reason:** Repository and workspace files are routinely copied, reviewed, and
  logged.
- **Consequence:** Examples contain placeholder reference names, never token-shaped
  values; MCP tools do not accept credentials.

## ADR-009 — Deterministic evidence controls PASS/FAIL

- **Status:** Accepted
- **Decision:** Only registered deterministic assertions, normalized runner results,
  and evidence policies can produce PASS/FAIL facts.
- **Reason:** Model conclusions are probabilistic and cannot establish execution
  evidence.
- **Consequence:** Narrative output must label `VERIFIED`, `INFERRED`, `UNKNOWN`,
  and `CONFLICTING` findings.

## ADR-010 — Manifest-driven structure audit

- **Status:** Accepted
- **Decision:** A versioned machine manifest, referenced by the human scaffold
  manifest, enumerates intended files, directories, status, and allowed emptiness.
- **Reason:** The large future scaffold requires automated detection of omissions,
  unexplained placeholders, duplicate ownership, accidental tool exposure, invalid
  configs, broken links, and suspicious secrets.
- **Consequence:** New files must be added to the manifest in the same change.

## ADR-011 — Status vocabulary and verification levels

- **Status:** Accepted
- **Decision:** Requirements use only `NOT_IMPLEMENTED`, `SCAFFOLDED`,
  `IMPLEMENTED`, `OFFLINE_VERIFIED`, `LIVE_VERIFIED`, and `BLOCKED`.
- **Reason:** Implementation existence and verification evidence are different
  facts.
- **Consequence:** Simulated platform tests cannot yield live platform status, and
  mocked tests cannot verify an external integration.

## ADR-012 — Pin direct dependencies and retain `uv.lock`

- **Status:** Accepted
- **Decision:** Pin direct M00 runtime and development dependencies to the versions
  verified during the architecture freeze; update them intentionally with tests and
  an ADR amendment when compatibility changes.
- **Reason:** MCP APIs and tool behavior are version-sensitive.
- **Consequence:** `uv lock --check`, a source build, and an isolated wheel smoke test
  are release gates.

