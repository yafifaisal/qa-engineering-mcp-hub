# Workflow engine architecture

Status: **SCAFFOLDED for future milestones.** Milestone 00 cannot discover, plan,
or execute a QA Workspace workflow.

## Intended responsibility

A workflow is approved company data that references registered suites,
deterministic assertions, evidence policies, and dependency ordering. It belongs
in a QA Workspace, not package code. The generic
[workspace template](../../templates/qa-workspace/README.md) illustrates the
boundary but is disabled by default.

The future engine will:

1. discover an explicitly selected, schema-valid workflow;
2. confirm profile, repository, environment, and capability authorization;
3. resolve only registered suites and assertions;
4. validate dependencies and produce an immutable plan;
5. execute bounded jobs through the runner service;
6. normalize results without equating process success with test PASS;
7. collect evidence according to the selected policy.

## Safety invariants

- No caller-provided shell command, working directory, SQL string, or Kafka topic
  may bypass a registry and allowlist.
- Provider writes, CI/CD triggers, and publication require preview and explicit
  approval in their owning milestones.
- Timeouts, cancellation, concurrency, output limits, and sanitized environments
  are mandatory for process execution.
- A dependency failure or missing required check cannot become PASSED.
- Resuming a job must be idempotent and profile-isolated.

The YAML files under [`templates/workflows/`](../../templates/workflows/) are
schemas/examples, not executable M00 functionality.
