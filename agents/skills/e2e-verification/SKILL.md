---
name: e2e-verification
description: Verify registered API, database, Kafka, and business invariants with deterministic evidence after the verification services are implemented.
metadata:
  owning-milestone: "07"
  implementation-status: NOT_IMPLEMENTED
---

# End-to-end verification

This repository skill is scaffolded for Future Milestone 07. Return
`NOT_IMPLEMENTED` unless every required verifier and evidence policy is active.

Use registered assertions only. Deny arbitrary SQL, database writes, unrestricted
topics, production offset commits, and unbounded polling. Correlate checks with a
stable key and deadline. Missing required observations are INCONCLUSIVE or
NOT_EXECUTED according to policy, not PASSED.
