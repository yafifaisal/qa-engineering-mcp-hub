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
Local registration is Milestone 02. Exit: read-only contract fixtures plus
separately gated sandbox reads for every edition claimed live.

## 04 — documentation providers

Owns Confluence and Google Docs adapters and document extraction/version provenance.
Exit: deterministic content/version/pagination/permission tests plus gated live
reads. General unrestricted Drive browsing is outside scope.

## 05 — knowledge and planning

Owns indexing coordination, chunking, parsers, symbols, dependency graph, retrieval,
freshness/source verification, ticket/change analysis, scenarios, and coverage maps.
Exit: repeatable indexes, stale/access tests, grounded citations, and curated
cross-repository traces.

## 06 — API automation execution

Owns suite registry, Bruno/Postman adapters, approved process runner, jobs,
normalization, and execution MCP tools. Exit: registered-only execution with timeout,
cancellation, output limits, sanitized environment, parser fixtures, and gated local
runner smoke tests. No arbitrary shell.

## 07 — deterministic end-to-end verification

Owns PostgreSQL/MySQL/Kafka adapters, assertion registry, correlation, invariants,
polling, and verification tools. Exit: registered parameterized SELECT-only policy,
row/time limits, authorized bounded Kafka reads without production offset commits,
and gated non-production live checks.

## 08 — CI/CD

Owns Bitbucket Pipelines, GitHub Actions, Jenkins, run/artifact normalization, and
CI/CD tools. Exit: deterministic state/pagination/artifact/permission tests and
preview-plus-approval for any trigger or cancellation.

## 09 — test management

Owns Xray, TestRail, CSV/XLSX, Google Sheets, canonical case mapping, previews,
loss reports, and approved publication. Exit: mapping/round-trip/formula-safety/
idempotency tests and gated sandbox reads/writes for each live claim.

## 10 — evidence and release intelligence

Owns policies, redacted collection, completeness, manifests, rendering, publishing,
coverage, risk, and release reports. Exit: deterministic evidence hashes, no secret
leaks, explicit missing-check behavior, authorized publication, and no automatic
release sign-off.

## 11 — community release

Owns supported-version policy, complete OS/Python CI, release/security workflows,
artifact provenance, migration notes, support documentation, and public release.
Exit: all claimed matrices are genuinely executed; mocks and simulations remain
clearly labeled offline evidence.
