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

Mocked keyring tests and simulated Windows/Linux paths are `OFFLINE_VERIFIED`.
They do not establish a live Credential Manager, Keychain, or Secret Service round
trip. `integrations test` must keep provider connectivity at `NOT_IMPLEMENTED`.

CI is configured for Windows, macOS, and Linux with Python 3.12/3.13, but a workflow
file is not live evidence. Record actual runner results in the progress document.
