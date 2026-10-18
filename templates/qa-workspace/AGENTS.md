# QA Workspace agent rules

- This workspace contains company-specific QA assets; do not copy them into the
  public framework.
- Treat every provider workflow, suite, assertion, and publisher as
  NOT_IMPLEMENTED until the framework reports the required capability.
- Never store tokens, passwords, cookies, private keys, or raw credential values
  in workspace files. Store credential references only.
- Run only registered suites and deterministic assertions. Never convert an AI
  conclusion into PASS/FAIL evidence.
- Preserve source revision, provider identity, profile, and evidence references.
- Keep profiles isolated. Do not read or publish data through a different
  profile without explicit authorization.
- Require explicit user approval for provider writes, CI/CD triggers, and
  evidence publication.
- Classify missing required evidence as INCONCLUSIVE or NOT_EXECUTED according
  to the selected policy; never silently mark it PASSED.
