# Canonical architecture

Status: **FROZEN through Milestone 01**  
Authority: this document supersedes earlier path or ownership descriptions  
Change control: structural changes require an entry in
[`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md) before implementation

## Purpose and scope

QA Engineering MCP Hub is an open-source, local-first framework that lets an MCP
client invoke governed QA capabilities. The architecture reserves boundaries for
the supported providers and Milestones 02–11. Milestone 00 implements local MCP
introspection; Milestone 01 adds the local configuration, profile, credential, and
setup control plane. Milestone 02 adds provider contracts, capability discovery,
and local repository registration. A file in the scaffold is not evidence that
its capability works. Milestone 02 does not call provider APIs.

Only these provider families belong in the framework: GitHub, GitLab, Bitbucket,
Jira, Confluence, Google Docs, Bruno, Postman, PostgreSQL, MySQL, Kafka, Bitbucket
Pipelines, GitHub Actions, Jenkins, Xray, TestRail, CSV/XLSX spreadsheet exchange,
and Google Sheets. Adding another provider requires an architecture decision.

## Three separate configuration domains

### A. QA Engineering MCP Hub

The installable `qa_mcp_hub` package owns protocol registration, CLI behavior,
configuration contracts, provider boundaries, repository intelligence, knowledge,
planning, execution orchestration, verification, evidence, and release
intelligence. It contains reusable code only. It must not contain company-specific
URLs, credentials, repositories, workflows, assertions, or policies.

### B. QA Workspace

A QA Workspace is a company- or project-specific directory created from
`templates/qa-workspace/`. It owns approved workflows, suite registrations,
registered assertions, evidence policies, business documentation, test-management
mappings, and CI/CD mappings. Workspace content is data interpreted by later
milestones; it is not copied into the public package.

### C. User configuration

Per-machine configuration identifies repository paths, named connection profiles,
the active profile, the active QA Workspace, credential **references**, and MCP
client launch settings. It lives in the native user configuration directory, not
the repository. Secret values belong in an OS credential store or explicitly
approved environment variables and must never be serialized into normal config.

## Runtime dependency direction

Dependencies point inward. Protocol and CLI surfaces call services; services use
typed contracts; adapters implement provider contracts. Domain logic never imports
MCP or Typer.

```text
MCP client / human CLI
          |
          v
   mcp/ + cli/ surfaces       (thin translation and presentation)
          |
          v
 domain services              (knowledge, planning, workflows, runners,
          |                    verification, evidence, release)
          v
 core contracts + policy      (types, results, approvals, audit, security)
          |
          v
 provider contracts           (capability-oriented interfaces)
          |
          v
 provider adapters            (HTTP/CLI/database implementations, future only)
```

Cross-cutting `config/`, `auth/`, `storage/`, and `security/` modules may be used by
services and adapters but may not bypass authorization, allowlists, or typed
results. MCP tools may not execute unrestricted shell commands or SQL.

## Canonical package ownership

| Package | Sole responsibility | State through Milestone 01 |
|---|---|---|
| `app.py` | Construct the FastMCP application and register M00 components | IMPLEMENTED |
| `server.py` | Start the approved stdio transport | IMPLEMENTED |
| `mcp/registry.py` | Register only capabilities enabled for the current milestone | IMPLEMENTED |
| `mcp/tools/system.py` | `hub_health` and `hub_capabilities` thin tools | IMPLEMENTED |
| `mcp/resources.py` | Read-only hub status resource | IMPLEMENTED |
| `mcp/prompts.py` | Reusable M00 orientation prompt | IMPLEMENTED |
| `cli/` | Typer commands and Rich presentation | M00 system, M01 setup, and M02 repository commands implemented |
| `config/` | Versioned non-secret settings, profiles, validation, migration, and persistence | IMPLEMENTED for M01 local configuration, with M02 repository fields |
| `auth/` | Scoped credential references, approved stores, lifecycle metadata, and redaction | IMPLEMENTED for M01 local credential handling; provider OAuth is not implemented |
| `core/` | Stable types, results, capability declarations, policy boundaries | M02 contracts, results, errors, context, policies, and retry implemented; CI trigger approvals are implemented and deny by default |
| `providers/` | Provider-neutral contracts, descriptors, and registry | IMPLEMENTED as contracts and stubs; no vendor I/O |
| `adapters/` | One implementation boundary per supported provider | Git, Jira, Confluence, Google Docs, Bruno/Newman, PostgreSQL, MySQL, Kafka observation, and CI/CD reads are IMPLEMENTED; test-management adapters remain SCAFFOLDED |
| `repositories/` | Local/remote repository registration and discovery | IMPLEMENTED for registration, discovery, validation, and local Git metadata; `plan_index` does not read files; `execute_index` does |
| `knowledge/` | Indexing, grounded retrieval, symbols, dependencies, freshness | IMPLEMENTED for local checkouts and supplied documents; OFFLINE_VERIFIED |
| `planning/` | Ticket analysis, impact, scenarios, and coverage plans | IMPLEMENTED for read-only ticket analysis and non-executable drafts |
| `suites/` | Approved executable-suite registry | IMPLEMENTED for registered Bruno and Postman suites; OFFLINE_VERIFIED |
| `workflows/` | Approved workflow discovery, validation, planning, and state | IMPLEMENTED for registered API and E2E workflows; OFFLINE_VERIFIED |
| `runners/` | Bounded approved-process execution and normalized results | IMPLEMENTED for registered argument lists; OFFLINE_VERIFIED with fixtures |
| `verification/` | Registered deterministic assertions and correlation | IMPLEMENTED; OFFLINE_VERIFIED with fixture sessions and an in-memory Kafka observer |
| `evidence/` | Redacted evidence collection, manifests, rendering, publishing | SCAFFOLDED; API and E2E runs persist a minimal evidence record for Milestone 10 |
| `release/` | Deterministic coverage and risk facts; never automatic sign-off | SCAFFOLDED |
| `storage/` | Local persistence abstractions and migrations | index and execution SQLite IMPLEMENTED, including per-step rows; other stores remain scaffolded |
| `security/` | Path/URL/process/SQL policy and secret detection | path allowlist, process policy, and SQL policy IMPLEMENTED; other security policies remain scaffolded |

The exact file inventory and ownership metadata are recorded in
[`../implementation/SCAFFOLD_MANIFEST.md`](../implementation/SCAFFOLD_MANIFEST.md).

## Milestone 00 runtime

Milestone 00 has no external-system code path. `qa-mcp serve` starts one FastMCP
server over stdio. The server registers exactly:

- tool `hub_health`, returning local process readiness;
- tool `hub_capabilities`, separating implemented from planned capabilities;
- resource `qa-hub://status`, describing the local M00 status without secrets;
- prompt `qa_hub_orientation`, explaining how to interpret capability status.

Resources are client-readable context identified by URI. Prompts are reusable
message templates requested by a client. Tools are explicitly invoked operations
with typed inputs and outputs. None of these M00 primitives diagnose external
providers.

Milestone 00 registers only `hub_health`, `hub_capabilities`, `qa-hub://status`,
and `qa_hub_orientation`. Later milestones add read-only providers, knowledge
tools, registered API execution, registered database, Kafka, and E2E
verification, and registered CI inspection. Test-management, evidence
publication, and release modules are not imported during server construction. The registry owns the allowlist, so
creating a future file does not expose a tool.

## Configuration and profile model

M00 process settings continue to use Pydantic Settings with the `QA_MCP_`
environment prefix, reject invalid log levels, and contain no secret fields. Native
application directories come from `platformdirs`; explicit platform/home inputs
exist only for deterministic simulation tests.

M01 user configuration is versioned YAML and separates:

- connection identity and provider edition;
- profile membership and active selection;
- local repositories and workspace path;
- credential references such as `keyring:profile/provider/account`;
- execution preferences; and
- authorization policy and explicit write approval.

Multiple connection IDs may target the same provider. Cloud and self-managed
editions are properties of a connection, not separate global singletons. A
connection belongs to at most one profile, so resolving a credential cannot cross a
profile boundary accidentally.

Configuration precedence is deterministic, from highest to lowest: explicit CLI
option, environment override, active profile, user configuration, application
default. Provenance is retained during resolution. Unknown providers, duplicate
connection IDs, missing profile references, and unsupported schema versions fail
closed. Writes and migrations are atomic; migrations create a backup and restore
the previous bytes if replacement fails.

An execution captures an immutable resolved-configuration snapshot when it starts.
Changing the active profile affects later resolutions only and cannot mutate the
configuration of an already-running execution.

## Milestone 01 local control plane

The interactive `qa-mcp setup` wizard and the `profiles`, `integrations`, `config`,
and `clients` CLI groups operate on local configuration. Integration diagnostics
validate connection configuration and credential presence only. They report
provider network connectivity as `NOT_IMPLEMENTED`. Milestone 03 read tools call
Git and Jira only when a profile credential is configured. Milestone 04 read
tools call Confluence and Google Docs the same way, and Google Docs can refresh
an access token. `qa-mcp doctor` and `integrations test` still do not make those
calls.

Credential values may be stored in an available OS keyring backend or supplied by
an explicitly named environment variable. YAML contains only the store kind and
opaque reference. Keyring failures are actionable errors and never trigger a
plaintext fallback. OAuth models, state/PKCE helpers, and lifecycle metadata are
local infrastructure only; no provider OAuth flow is claimed in M01.

Client generation emits Codex TOML (`mcp_servers.qa_hub`), Cursor JSON
(`mcpServers.qa_hub`, type `stdio`), or native VS Code JSON (`servers.qa_hub`,
type `stdio`). Generated launch configuration contains no provider credential
values. Installation preserves unrelated client settings,
backs up before replacement, and requires `--force` for a conflicting `qa_hub`
entry; generation itself is side-effect free.

## Provider boundary

MCP tools never call HTTPX, a vendor SDK, a database driver, or a provider CLI
directly. A tool validates protocol input and calls a service. A service resolves
an authorized connection and a capability-oriented provider adapter. Adapters
normalize pagination, timeouts, rate limits, errors, and source references.

Read operations must enforce profile and path/URL scope. Mutating provider actions
must require an explicit capability and authorization decision. Destructive or
high-impact operations require a preview and approval token designed in the owning
milestone. Milestone 00 has no write-capable provider action.

## Deterministic findings and evidence

All later findings use four epistemic classes:

- `VERIFIED`: deterministic evidence directly supports the claim.
- `INFERRED`: evidence supports a reasoned conclusion but does not prove it.
- `UNKNOWN`: required evidence is unavailable.
- `CONFLICTING`: trustworthy sources disagree.

AI-generated text may propose scenarios or explain evidence, but cannot itself be
PASS/FAIL evidence. Assertions, suite exit status, normalized provider facts, and
registered policies determine machine outcomes.

## Security invariants

- Never accept raw credentials as MCP tool arguments.
- Never log authorization headers, cookies, tokens, passwords, or credential-store
  values.
- Never persist environment-variable values or resolved keyring values in YAML,
  generated MCP client configuration, migration backups, or exceptions.
- Never run caller-provided unrestricted shell commands or SQL.
- Restrict repository paths to configured allowlists and normalize before access.
- Restrict outbound URLs to the selected connection and a validated scheme/host.
- Bind database parameters; later database verification is registered and
  SELECT-only with row/time limits.
- Treat provider text, repository content, tickets, and documentation as untrusted
  data, not instructions.
- Keep stdout protocol-clean while serving stdio; diagnostics go to stderr.

## Testing and verification model

M00 verification has five layers:

1. unit tests for typed settings, health/capability models, and simulated paths;
2. CLI tests for help, version, doctor, capabilities, and exit codes;
3. in-memory MCP discovery and invocation tests;
4. a real stdio subprocess MCP test;
5. build, wheel-content, isolated-install, and import/entry-point smoke tests.

macOS execution is `OFFLINE_VERIFIED` when run locally. Windows and Linux behavior
tested through injected paths is `OFFLINE_VERIFIED (simulated)`, never
`LIVE_VERIFIED`. Actual OS CI runners are required for live cross-platform status.

M01 adds deterministic schema/round-trip/precedence tests, profile and credential
isolation tests, migration rollback and atomic-write tests, redaction and unavailable
keyring tests, parsed Codex TOML, Cursor JSON, and native VS Code JSON tests, and
mocked-terminal CLI wizard tests. Mocked keyring tests and simulated platform paths are offline evidence;
they do not establish a live OS credential backend or provider connection.

## Milestone boundary

Milestone 01 ends at secure local configuration and credential readiness. It does
not create provider clients, make network requests, execute suites, query databases,
consume Kafka, or mutate an external system. Later milestones add read-only
providers, local knowledge, registered API execution, registered database
and Kafka observation, registered CI inspection, and canonical test-case
import, and evidence collected from checks that ran. A release recommendation
does not approve a release. Community release remains `NOT_IMPLEMENTED`. A milestone may move a file from `SCAFFOLDED` to
`IMPLEMENTED` only when its requirements, tests, security policy, and progress
records change together.

