# Known limitations

## Milestone boundary

- GitHub, GitLab, Bitbucket, Jira, Confluence, and Google Docs have read-only
  adapters. Mocked HTTP tests are `OFFLINE_VERIFIED`. No live provider call was
  executed in this session, so those integrations are not `LIVE_VERIFIED`.
- Google Docs can refresh an access token from a stored refresh token. The
  refresh token is not returned by MCP tools. Interactive browser login is not
  implemented.
- Other provider integrations remain `NOT_IMPLEMENTED`. Their registry entries
  still return contract stubs.
- Milestone 01 implements local configuration, profiles, credential references,
  redaction, offline OAuth/PKCE state, and the setup/config CLI. It does not
  perform a provider OAuth exchange, token refresh, or network connectivity test.
- Milestone 02 registers local and remote repository definitions, discovers Git
  checkouts inside an approved workspace, and reads local branch, HEAD, remote
  URL, and dirty state. `plan_index` still does not read file contents.
- Milestone 05 indexes git-tracked files in an explicitly permitted local
  checkout. Pattern parsers for Go, Java, JavaScript, and TypeScript are
  INFERRED. Unsupported languages stay UNKNOWN. A source reference is not a
  runtime observation, and no trace claims a complete call graph. Community
  Edition does not call a hosted embedding service. Confluence and Google Docs
  enter the index only after an authorized read is passed to the engine.
- Workflows, suite execution, assertions, CI/CD, test management, evidence, and
  release intelligence remain Milestones 06–10. Ticket analysis does not call a
  language model.
- Python keyring is a direct development dependency and an optional `credentials`
  extra. A missing or unusable backend fails closed. The application does not fall
  back to a plaintext file.

## Runtime and client boundary

- `qa-mcp doctor` checks process settings, local configuration validity, and
  keyring-backend availability. It does not read a stored secret, validate a
  provider permission, or contact an external service.
- `qa-mcp integrations test` checks the selected connection and credential
  presence only. Its provider network result remains `NOT_IMPLEMENTED`.
- Only local stdio is enabled. Remote HTTP, server authentication, and provider
  OAuth hosting are absent.
- MCP resources and prompts pass protocol tests, but their presentation in the Codex
  IDE UI was not observed in this session.

## Platform evidence

- Local execution for this milestone used macOS with Python 3.12.12 and uv 0.8.22.
  `qa-mcp doctor` reported a usable keyring backend named `Keyring` without
  reading a stored secret. That is not a live Keychain write/read round trip.
- Windows 10/11 and Linux path behavior is deterministic simulation only. The
  checked-in CI matrix has not run in this session, so native Windows/Linux and
  Python 3.13 evidence is `BLOCKED` on hosted-runner access.
- macOS Keychain, Windows Credential Manager, and Linux Secret Service read/write
  round trips are not `LIVE_VERIFIED`. Keyring tests use an injected backend.
  `qa-mcp doctor` may report the active backend name without reading a secret.

## Optional artifacts and external details

- Docker was not installed in the authoring environment, so the Dockerfile and
  Compose file were syntax-reviewed scaffolding but not built or run.
- Jinja2 is a future optional dependency; evidence templates were not rendered.
- Provider editions, scopes, endpoints, and rate limits marked “Requires
  verification” must be checked against current official documentation during the
  owning milestone.
- The QA Workspace root and CI registry YAML files are syntax-checked and
  manifest-audited. Milestone 01 stores a workspace path reference only; dedicated
  workspace and CI semantic schemas remain future work.
- No live provider, database, Kafka, CLI runner, or CI system was contacted.

## Audit limitations

- The secret audit combines Python AST inspection, structured key/value analysis,
  entropy, and known token patterns, but cannot prove that arbitrary text contains no
  sensitive business data. Human review remains required.
- Local-link validation checks repository targets, not the continued availability or
  content of external URLs.
- Schema-valid examples do not prove that their future loaders or services exist.
