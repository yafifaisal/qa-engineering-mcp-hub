# Implementation roadmap

The [canonical architecture](../architecture/CANONICAL_ARCHITECTURE.md) freezes
ownership. A milestone advances only when its code, deterministic tests, security
controls, documentation, traceability, and honest verification evidence advance
together.

## 00 — foundation

Owns packaging, standalone FastMCP stdio, the two system tools, status resource,
orientation prompt, Typer/Rich CLI, non-secret Pydantic settings, portable paths,
complete future scaffold, documentation, and structure auditing.

Exit: lint, format, mypy, pytest, lock, structure audit, source build, stdio protocol,
and isolated wheel smoke tests pass. External providers remain unimplemented.

## 01 — profiles and credentials

Owns configuration load/write/migration/resolution, named profiles, multiple
connections, active QA Workspace, OS credential store, environment fallback,
redaction, OAuth/token lifecycle, setup/config/profile/client CLI commands.

Exit: atomic-write/migration/permissions/redaction/profile-isolation tests and live
credential-store validation on each claimed OS. No provider operation yet.

## 02 — provider contracts and registry

Owns provider-neutral contracts/models/registry, normalized errors/capabilities,
connection-to-adapter construction, and local/remote repository registration.
Exit: deterministic contract suites, unknown provider/capability rejection,
connection/profile isolation, and local Git metadata without a remote API call.
Indexing execution remains Milestone 05.

## 03 — Git and ticket intelligence

Owns GitHub, GitLab, Bitbucket, and Jira adapters plus grounded source resolution.
Local registration is Milestone 02. Exit: read-only contract fixtures are
OFFLINE_VERIFIED. Live sandbox reads stay gated and are not LIVE_VERIFIED until
they are actually executed.

## 04 — documentation providers

Owns Confluence and Google Docs adapters and document extraction/version provenance.
Exit: mocked content, version, pagination, and permission tests are
OFFLINE_VERIFIED. Live reads stay gated and are not LIVE_VERIFIED until they
are executed. General unrestricted Drive browsing is outside scope.

## 05 — knowledge and planning

Owns indexing coordination, chunking, parsers, symbols, dependency graph, retrieval,
freshness/source verification, ticket/change analysis, scenarios, and coverage maps.
Exit: repeatable local indexes, stale and permission tests, grounded citations,
and partial cross-repository traces are OFFLINE_VERIFIED. A trace is not a
complete runtime call graph. Live provider calls are not part of this exit.

## 06 — API automation execution

Owns suite registry, Bruno/Postman adapters, approved process runner, jobs,
normalization, and execution MCP tools. Exit: registered-only execution with timeout,
cancellation, output limits, sanitized environment, parser fixtures, and gated local
runner smoke tests are OFFLINE_VERIFIED. No arbitrary shell. Installed Bruno and
Newman binaries were not executed, so this exit is not LIVE_VERIFIED. Registered
database and Kafka checks are Milestone 07.

## 07 — deterministic end-to-end verification

Owns PostgreSQL/MySQL/Kafka adapters, assertion registry, correlation, invariants,
polling, and verification tools. Exit: registered parameterized SELECT-only policy,
row/time limits, authorized bounded Kafka reads without production offset commits,
and gated non-production live checks. Exit status: OFFLINE_VERIFIED with fixture
sessions and an in-memory observer. Live PostgreSQL, MySQL, and Kafka clients are
not bundled, so this exit is not LIVE_VERIFIED.

## 08 — CI/CD

Owns Bitbucket Pipelines, GitHub Actions, Jenkins, run/artifact normalization, and
CI/CD tools. Exit status: OFFLINE_VERIFIED with mocked HTTP for Bitbucket
Pipelines, GitHub Actions, and Jenkins. Remote triggering is not an MCP tool.
Live CI systems were not contacted, so this exit is not LIVE_VERIFIED.

## 09 — test management

Owns Xray Cloud, Xray Data Center, TestRail, CSV/XLSX, Google Sheets, canonical
case mapping, and publication preview. Exit status: OFFLINE_VERIFIED with local
files and mocked HTTP. `prepare_result_publication` does not call a provider.
Result publication is not an MCP tool. Live Xray, TestRail, and Google Sheets
were not contacted, so this exit is not LIVE_VERIFIED.

## 10 — evidence and release intelligence

Owns policies, redacted collection, completeness, manifests, rendering, publishing,
coverage, risk, and release reports. Exit status: OFFLINE_VERIFIED with stored
executions and mocked publication HTTP. A missing mandatory check cannot become
PASS. Publication requires an explicit review and a single-use approval.
A release recommendation does not approve the release. No live Jira, Xray, or
TestRail publication was made, so this exit is not LIVE_VERIFIED.

## 11 — community release

Owns supported-version policy, complete OS/Python CI, release/security workflows,
artifact provenance, migration notes, support documentation, and public release.
Exit: all claimed matrices are genuinely executed; mocks and simulations remain
clearly labeled offline evidence.
