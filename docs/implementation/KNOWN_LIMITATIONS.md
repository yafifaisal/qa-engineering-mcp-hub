# Known limitations

## Milestone boundary

- GitHub, GitLab, Bitbucket, Jira, Confluence, and Google Docs have read-only
  adapters. Mocked HTTP tests are `OFFLINE_VERIFIED`. No live provider call was
  executed in this session, so those integrations are not `LIVE_VERIFIED`.
- Google Docs can refresh an access token from a stored refresh token. The
  refresh token is not returned by MCP tools. Interactive browser login is not
  implemented.
- The generic `read_case` port stays unavailable even though the Milestone 09
  tools read through reviewed mappings. The Community Edition package is built
  locally and is not published.
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
- Milestone 06 runs only registered Bruno and Newman suites. Secrets are
  injected through a mode-0600 environment file and redacted from stored
  output. They are not accepted as MCP arguments and are not passed with
  `--env-var`. A dry-run profile does not start a runner.
- Milestone 07 runs registered database, Kafka, and business assertions after
  an approved workflow's API steps. SQL text is not an MCP argument. Kafka
  observation does not commit offsets. A topic read is not consumer completion.
  Live database and Kafka drivers are not bundled. `QA_MCP_LIVE_DATABASES` and
  `QA_MCP_LIVE_KAFKA` do not create a successful stand-in connection.
- Test-case import is OFFLINE_VERIFIED for Xray, TestRail, CSV, XLSX, and
  Google Sheets. Unknown priority and result values fail the mapping. Extra
  columns are preserved. Result publication is not an MCP tool. The example
  mapping keeps `allow_publish` false. No live Xray, TestRail, or Google
  Sheets call was made.
- Evidence collection is OFFLINE_VERIFIED from stored executions. API-only
  evidence does not claim database or Kafka validation. Missing mandatory
  evidence cannot be an overall PASS. External publication stays denied unless
  a policy sets `external_publication: approval_required` and a single-use
  approval is consumed. A failed POST is not retried. No live Jira, Xray, or
  TestRail publication was made.
- A release recommendation does not change the QA review state and cannot
  set release approval. Coverage counts only mapped cases that executed and
  passed. A missing defect register or requirement map stays incomplete.
- CI reads are OFFLINE_VERIFIED with mocked HTTP. Remote triggering is not an
  MCP tool. No live CI system was contacted.
- Ticket analysis does not call a language model.
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

- Local execution for Milestone 11 used macOS with the commands recorded in
  the progress document. `qa-mcp doctor` may report a keyring backend name
  without reading a stored secret. That is not a live Keychain write/read
  round trip.
- Windows 10/11 and Linux path behavior is deterministic simulation only. The
  checked-in CI matrix names those runners and has not been observed, so native
  Windows/Linux and Python 3.13 evidence is `BLOCKED`.
- macOS Keychain, Windows Credential Manager, and Linux Secret Service read/write
  round trips are not `LIVE_VERIFIED`. Keyring tests use an injected backend.
  Environment-variable references are the documented fallback when a backend is
  unavailable. The application does not write a plaintext credential file.

## Optional artifacts and external details

- Docker was not installed in the authoring environment, so the Dockerfile and
  Compose file were syntax-reviewed and not built or run.
- Evidence HTML is rendered by the repository template engine. Jinja2 is not a
  dependency.
- Provider editions, scopes, endpoints, and rate limits marked “Requires
  verification” must be checked against current official documentation during the
  owning milestone.
- The QA Workspace root and CI registry YAML files are schema-checked.
  The example CI job is disabled and `allow_trigger` is false. Live CI was
  not contacted.
- No live provider, database, Kafka, Bruno CLI, Newman CLI, or CI system was
  contacted. API execution tests used a local stand-in process.

## Audit limitations

- The secret audit combines Python AST inspection, structured key/value analysis,
  entropy, and known token patterns, but cannot prove that arbitrary text contains no
  sensitive business data. Human review remains required.
- Local-link validation checks repository targets, not the continued availability or
  content of external URLs.
- Schema-valid examples do not prove that their future loaders or services exist.
