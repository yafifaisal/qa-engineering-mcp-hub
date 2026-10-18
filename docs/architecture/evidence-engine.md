# Evidence engine architecture

Status: **SCAFFOLDED for Future Milestone 10.** M00 does not collect, persist,
render, sign, or publish QA evidence.

## Intended responsibility

Evidence records deterministic observations from approved suites and assertions.
The engine will normalize results, enforce evidence policies, redact sensitive
data, compute completeness, create tamper-evident manifests, render reports, and
publish only after authorization.

Required states include `PASSED`, `FAILED`, `NOT_EXECUTED`, `NOT_APPLICABLE`, and
`INCONCLUSIVE`. Invocation success, HTTP 2xx, a process exit code of zero, or AI
prose cannot replace assertion results.

## Integrity and privacy

- Preserve execution ID, profile, source revisions, timestamps, assertion IDs,
  and artifact hashes.
- Redact secrets and sensitive values before persistence or rendering.
- Treat renderer input as untrusted and escape HTML.
- Detect manifest or artifact checksum mismatch and block publication.
- Keep retention and storage location policy-specific and profile-isolated.
- Make publication explicit, previewable, retry-safe, and idempotent.

API-only evidence must not imply that database, Kafka, business, or UI checks ran.
Missing required evidence follows the selected policy and is never silently
PASSED.

The files under [`templates/evidence/`](../../templates/evidence/) and
[`templates/qa-workspace/evidence-policies/`](../../templates/qa-workspace/evidence-policies/)
are non-executable templates. See [data handling](../security/data-handling.md).
