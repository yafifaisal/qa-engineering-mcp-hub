# Test strategy

Tests must demonstrate behavior, not inflate counts. A future scaffold needs
ownership documentation; it does not need a meaningless test that imports an empty
module.

## Evidence layers

1. **Unit:** deterministic models, settings, paths, policies, parsers, and domain
   services without a protocol or external system.
2. **CLI integration:** Typer `CliRunner` verifies commands, output intent, and exit
   codes. It does not prove installed console-script metadata.
3. **In-memory MCP protocol:** `fastmcp.Client(mcp)` proves component registration,
   schemas, reads, prompts, and calls through the SDK protocol layer. It does not
   prove subprocess stdio.
4. **Stdio MCP protocol:** `StdioTransport` launches `python -m qa_mcp_hub.server`
   and proves discovery/invocation over the real M00 transport.
5. **Packaging:** build wheel/sdist, inspect metadata, install the exact wheel in an
   isolated environment, import the package, run CLI help, and run the smoke test.
6. **Security/structure:** AST, schema, link, secret, ownership, and accidental MCP
   exposure checks; targeted security regressions.
7. **External contract/live:** later provider fixtures verify normalization offline;
   separately gated sandbox calls establish live behavior.

## Verification language

- A mock, fake, or recorded fixture is `OFFLINE_VERIFIED` evidence only.
- Simulating `win32` or Linux paths on macOS is not native OS execution.
- An installed SDK or provider module is not a successful integration.
- A process exit code is not an application assertion unless a registered runner
  contract defines and verifies that meaning.
- AI prose is never PASS/FAIL evidence.
- Unexecuted checks are not passed; inaccessible environments are `BLOCKED` with a
  recorded reason.

## Milestone 00 matrix

| Area | Required evidence |
|---|---|
| Health/capabilities | direct unit plus in-memory and stdio calls |
| Resource/prompt | list/read and list/get through both relevant protocol layers |
| CLI | help, version, doctor, capabilities, serve entry point metadata |
| Settings | defaults, environment overrides, invalid values, no secret fields |
| Paths | native macOS observation; deterministic Windows/macOS/Linux simulations |
| Packaging | locked sync, source build, isolated exact-wheel install and smoke |
| Structure | zero mandatory findings and exact MCP allowlist |

## Milestone 01 matrix

| Area | Required evidence |
|---|---|
| Schema | valid and invalid profiles, connections, enums, duplicates, and references |
| Precedence | explicit, environment, profile, user, and default provenance |
| Persistence | YAML round trip, owner-only permissions, atomic replacement |
| Migration | backup, idempotent rerun, and rollback after a failed replacement |
| Credentials | profile isolation, environment read-only mode, missing/expired metadata |
| Keyring | injected backend success and sanitized unavailable-backend failure |
| Redaction | nested values, generated client files, and CLI output |
| CLI | mocked wizard input, cancellation, safe rerun, and command exit codes |
| Clients | parsed Codex TOML, Cursor JSON, and native VS Code JSON, merge, and no embedded secrets |
| Doctor | local configuration validity and keyring availability without secret reads |

## Milestone 02 matrix

| Area | Required evidence |
|---|---|
| Provider catalog | exact match to the architecture document and `ProviderKind` |
| Capabilities | unimplemented operations raise typed errors and are not MCP tools |
| Isolation | two connections of one provider stay distinct; profiles do not share them |
| Repositories | local registration, duplicate rejection, discovery, and CLI commands |
| Git metadata | branch, HEAD, dirty state, and redacted remote URL on this machine |
| Paths | Windows, macOS, and Linux logical containment, plus symlink escape |
| Indexing | a plan is recorded and file contents are not read |

## Milestone 03 matrix

| Area | Required evidence |
|---|---|
| GitHub/GitLab/Bitbucket/Jira | respx authentication, pagination, 401/403/404, and edition routing |
| Source integrity | every code hit has a commit SHA and URL; local HEAD stays separate |
| Secrets | provider error messages omit response bodies and credentials |
| MCP tools | in-memory invocation of the four read tools against mocked HTTP |
| Live providers | skipped unless `QA_MCP_LIVE_PROVIDERS=1` |

## Milestone 04 matrix

| Area | Required evidence |
|---|---|
| Confluence | Cloud and Data Center paths, space-limited search, denied and removed pages |
| Google Docs | headings, paragraphs, tables, unsupported nodes, refresh, and scope failure |
| Citations | provider, document id, URL, revision, and retrieval time |
| Secrets | refresh tokens and client secrets stay out of tool results |
| MCP tools | in-memory `search_documents` and `read_document` against mocked HTTP |

## Milestone 05 matrix

| Area | Required evidence |
|---|---|
| Indexing | repeatable chunks, incremental updates, and skipped secret paths |
| Languages | Python AST is VERIFIED; pattern parsers are INFERRED; other files are UNKNOWN |
| Freshness | stale HEAD warnings, missing files, and conflicting line hashes |
| Isolation | one profile cannot read another profile's chunks |
| Traces | cross-repository edges stay partial and `complete_graph` is false |
| Drafts | scenario text is not executable and no workflow file is written |
| MCP tools | in-memory knowledge and planning tools against a local Git fixture |

## Milestone 06 matrix

| Area | Required evidence |
|---|---|
| Bruno | passing and failing reporter fixtures, missing binary, invalid output |
| Postman | Newman 6.2.2 JSON reporter fixtures for pass and fail |
| Process | timeout, cancellation, nonzero exit, and no shell execution |
| Registry | duplicate suite and workflow ids, unsupported environment |
| Workflow | dependency cycle, missing assertion, unapproved candidate |
| Evidence | API-only PASS does not claim database or Kafka verification |
| Secrets | credential values stay out of argv and the execution database |
| MCP tools | list, explain, preview, submit, and get against a local fixture |

## Milestone 07 matrix

| Area | Required evidence |
|---|---|
| PostgreSQL | bound parameters, injection rejection, read-only session, timeout |
| MySQL | read-only session statements and bound parameters |
| Kafka | schema mismatch, retention gap, missing event, DLQ, no offset commit |
| Correlation | mismatched keys fail; undeclared keys are rejected |
| E2E | PASS, FAIL, INCONCLUSIVE, and BLOCKED; missing mandatory checks are not PASS |
| MCP tools | assertion list omits SQL text; database and Kafka tools have no SQL argument |

## Milestone 08 matrix

| Area | Required evidence |
|---|---|
| Bitbucket Pipelines | success, failure, cancellation, pagination, permission, expiry |
| GitHub Actions | exact revision, redacted log, rate limit, single-use dispatch guard |
| Jenkins | unstable versus assertion status, invalid parameters, crumb, one POST |
| Trigger | prepare does not call a provider; remote trigger is not an MCP tool |
| Correlation | suite ids and issue keys come from the run revision and mapping |

## Milestone 09 matrix

| Area | Required evidence |
|---|---|
| Xray | Cloud `action` steps and Data Center `step` fields, unknown priority, one POST |
| TestRail | separated steps, suite and section ids, run ids, permission failure |
| CSV/XLSX | UTF-8, rejected UTF-16, formula prefix, multiline roundtrip, dry-run |
| Google Sheets | read-only scope and mocked values range |
| Publication | prepare does not call a provider; publishing is not an MCP tool |

## Milestone 10 matrix

| Area | Required evidence |
|---|---|
| API-only | database and Kafka sections are absent |
| E2E | a missing mandatory check is not PASS |
| Artifacts | SHA-256 mismatch and path escape are rejected |
| Redaction | tokens, email, and HTML are sanitized |
| Publication | denied by default, one POST, no automatic retry |
| Release | coverage uses executed mappings; a recommendation does not approve |

## Milestone 11 matrix

| Area | Required evidence |
|---|---|
| Package | wheel and source distribution install, then uninstall, in a clean environment |
| uvx | `qa-mcp --version` runs from the built wheel |
| Onboarding | setup, doctor, profiles, integrations, repositories, workflows, and client install |
| Companies | Company A and Company C profiles do not share connections, repositories, or artifacts |
| Scanning | known token shapes and unsafe archive paths fail the distribution scan |
| Publish | the release workflow builds artifacts and does not publish unless explicitly approved |

Mocked keyring tests and simulated Windows/Linux paths are `OFFLINE_VERIFIED`.
They do not establish a live Credential Manager, Keychain, or Secret Service round
trip. `integrations test` must keep provider connectivity at `NOT_IMPLEMENTED`.

CI is configured for Windows, macOS, and Linux with Python 3.12/3.13, but a workflow
file is not live evidence. Record actual runner results in the progress document.
Hosted runner execution for this milestone remains `BLOCKED` until that workflow
has been observed.
