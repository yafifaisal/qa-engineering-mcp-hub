# Canonical architecture

Status: **FROZEN for Milestone 00**  
Authority: this document supersedes earlier path or ownership descriptions  
Change control: structural changes require an entry in
[`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md) before implementation

## Purpose and scope

QA Engineering MCP Hub is an open-source, local-first framework that lets an MCP
client invoke governed QA capabilities. The architecture reserves boundaries for
the supported providers and Milestones 01–11 while Milestone 00 implements only
local introspection. A file in the scaffold is not evidence that its capability
works.

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

| Package | Sole responsibility | Milestone 00 state |
|---|---|---|
| `app.py` | Construct the FastMCP application and register M00 components | IMPLEMENTED |
| `server.py` | Start the approved stdio transport | IMPLEMENTED |
| `mcp/registry.py` | Register only capabilities enabled for the current milestone | IMPLEMENTED |
| `mcp/tools/system.py` | `hub_health` and `hub_capabilities` thin tools | IMPLEMENTED |
| `mcp/resources.py` | Read-only hub status resource | IMPLEMENTED |
| `mcp/prompts.py` | Reusable M00 orientation prompt | IMPLEMENTED |
| `cli/` | Typer commands and Rich presentation | M00 commands implemented; others scaffolded |
| `config/` | Non-secret settings, portable paths, validation, future persistence | minimal M00 subset implemented |
| `auth/` | Credential interfaces and lifecycle, never MCP arguments | SCAFFOLDED |
| `core/` | Stable types, results, capability declarations, policy boundaries | minimal M00 subset implemented |
| `providers/` | Provider-neutral contracts, descriptors, and registry | SCAFFOLDED |
| `adapters/` | One implementation boundary per supported provider | SCAFFOLDED |
| `repositories/` | Local/remote repository registration and discovery | SCAFFOLDED |
| `knowledge/` | Indexing, grounded retrieval, symbols, dependencies, freshness | SCAFFOLDED |
| `planning/` | Ticket analysis, impact, scenarios, and coverage plans | SCAFFOLDED |
| `suites/` | Approved executable-suite registry | SCAFFOLDED |
| `workflows/` | Approved workflow discovery, validation, planning, and state | SCAFFOLDED |
| `runners/` | Bounded approved-process execution and normalized results | SCAFFOLDED |
| `verification/` | Registered deterministic assertions and correlation | SCAFFOLDED |
| `evidence/` | Redacted evidence collection, manifests, rendering, publishing | SCAFFOLDED |
| `release/` | Deterministic coverage and risk facts; never automatic sign-off | SCAFFOLDED |
| `storage/` | Local persistence abstractions and migrations | SCAFFOLDED |
| `security/` | Path/URL/process/SQL policy and secret detection | SCAFFOLDED |

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

No module under `adapters/` or future domain services is imported during server
construction. The registry owns the allowlist so merely creating a future file
cannot expose a tool.

## Configuration and profile model

M00 settings use Pydantic Settings with the `QA_MCP_` environment prefix, reject
invalid log levels, and contain no secret fields. Native application directories
come from `platformdirs`; explicit platform/home inputs exist only for deterministic
simulation tests.

Future configuration separates:

- connection identity and provider edition;
- profile membership and active selection;
- local repositories and workspace path;
- credential references such as `keyring:profile/provider/account`;
- authorization policy and explicit write approval.

Multiple connection IDs may target the same provider. Cloud and self-managed
editions are properties of a connection, not separate global singletons.

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

## Milestone boundary

Milestone 00 ends with the framework, contracts, documentation, templates, and
auditing foundation. Milestones 01–11 remain scaffolded. A future milestone may
move a file from `SCAFFOLDED` to `IMPLEMENTED` only when its requirements, tests,
security policy, and progress records change together.

