# Verify an end-to-end invariant

Status: **NOT_IMPLEMENTED — Future Milestone 07**

Use only registered deterministic assertions and approved connections. Arbitrary
SQL, production writes, unrestricted Kafka consumption, and offset commits are
forbidden. If a required API, database, or event check cannot run, report
NOT_EXECUTED or INCONCLUSIVE according to policy; never silently return PASSED.

Return each check independently with its source, correlation key, bounded time
window, normalized result, and redacted evidence reference.
