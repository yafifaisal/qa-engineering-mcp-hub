# Known limitations

## Milestone boundary

- Every external provider integration is `NOT_IMPLEMENTED`. Provider modules and
  documentation are scaffolds, not callable adapters.
- Profiles, config persistence/migration, credential resolution, OAuth/token
  lifecycle, repository access, knowledge indexing, planning, workflows, suite
  execution, assertions, CI/CD, test management, evidence, and release intelligence
  remain Milestones 01–10.
- The pre-existing profile types, credential protocol, and keyring wrapper are
  preserved but are not imported or registered by the M00 runtime. This project
  declares Keyring only in the optional `credentials` extra; FastMCP 4.1.0 also
  installs Keyring transitively, so it can still be present in a base environment.

## Runtime and client boundary

- `qa-mcp doctor` checks only local package/settings readiness. It does not validate
  a credential, connection, executable, provider permission, or external service.
- Only local stdio is enabled. Remote HTTP, server authentication, and OAuth hosting
  are absent.
- MCP resources and prompts pass protocol tests, but their presentation in the Codex
  IDE UI was not observed in this session.

## Platform evidence

- Local execution used macOS with Python 3.12.15 and uv 0.13.1.
- Windows 10/11 and Linux path behavior is deterministic simulation only. The
  checked-in CI matrix has not run in this session, so native Windows/Linux and
  Python 3.13 evidence is `BLOCKED` on hosted-runner access.
- Keychain, Windows Credential Manager, and Linux Secret Service behavior is not
  tested.

## Optional artifacts and external details

- Docker was not installed in the authoring environment, so the Dockerfile and
  Compose file were syntax-reviewed scaffolding but not built or run.
- Jinja2 is a future optional dependency; evidence templates were not rendered.
- Provider editions, scopes, endpoints, and rate limits marked “Requires
  verification” must be checked against current official documentation during the
  owning milestone.
- The QA Workspace root and CI registry YAML files are syntax-checked and
  manifest-audited, but do not yet have dedicated semantic schemas; those belong
  with the Milestone 01 workspace/configuration loader.
- No live provider, database, Kafka, CLI runner, or CI system was contacted.

## Audit limitations

- The secret audit combines Python AST inspection, structured key/value analysis,
  entropy, and known token patterns, but cannot prove that arbitrary text contains no
  sensitive business data. Human review remains required.
- Local-link validation checks repository targets, not the continued availability or
  content of external URLs.
- Schema-valid examples do not prove that their future loaders or services exist.
