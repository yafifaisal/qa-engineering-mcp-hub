# Workflow engine architecture

Status: **IMPLEMENTED for API-only workflows. OFFLINE_VERIFIED with local fixtures.**
Database and Kafka steps are extension points and stay unavailable until Milestone 07.

## Responsibility

A workflow is approved QA Workspace data. It references registered suites and
assertion ids. The engine:

1. loads schema version 1 YAML from `workflows/api` and `workflows/e2e`;
2. rejects duplicate ids, missing dependencies, missing assertion ids, and cycles;
3. previews an immutable plan before any process starts;
4. runs only `api_suite` steps through the registered Bruno or Newman argument list;
5. marks `database_assertion`, `kafka_assertion`, and `business_assertion` steps
   unavailable and does not execute them;
6. normalizes runner exit and assertion results separately;
7. stores an API-only evidence record. `database_verified` and `kafka_verified`
   stay false.

Suggestions built from a Jira key or changed paths are not approved and cannot
be submitted.

## Safety invariants

- No caller-provided shell command, working directory, or extra CLI flag is accepted.
- `shell=True` is not available. Arguments are a list.
- Timeouts, cancellation, concurrency, output limits, and a sanitized environment
  are mandatory.
- A dependency failure or a run with no itemized assertions cannot become PASSED.
- A dry-run execution preference returns the preview and does not start a process.

The examples under `templates/qa-workspace/workflows/` are disabled. They are not
an approved company registry. The files under `templates/workflows/` are schema
examples.
