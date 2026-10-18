"""Execute one registered database assertion.

Purpose: bind parameters, apply a read-only session, and poll within a deadline.
Milestone: 07
Status: IMPLEMENTED
Ownership: verification.database_assertions
Dependencies: SQL policy, database adapters, and bounded polling.
Expected tests: injection, timeout, connection failure, and eventual consistency.
"""

import json
from collections.abc import Callable

from qa_mcp_hub.adapters.database.base import (
    DatabaseReader,
    redact_rows,
    sensitive_column,
)
from qa_mcp_hub.adapters.database.mysql import mysql_protections
from qa_mcp_hub.adapters.database.postgresql import postgresql_protections
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.runners.polling import poll_for_rows
from qa_mcp_hub.security.sql_policy import prepare_select
from qa_mcp_hub.verification.correlation import matches, require_keys
from qa_mcp_hub.verification.models import AssertionDefinition, CheckResult
from qa_mcp_hub.workflows.models import ExecutionStatus

_RESULT_LIMIT = 8192


def run_database_assertion(
    assertion: AssertionDefinition,
    parameters: dict[str, str],
    *,
    reader: DatabaseReader | None,
    approved_connections: dict[str, str],
    cancel: Callable[[], bool] | None = None,
) -> CheckResult:
    """Run one registered statement. Caller SQL is not accepted here."""
    if assertion.kind not in {"database", "sql"}:
        return _blocked(assertion, "assertion_kind")
    if assertion.definition.get("read_only") is not True:
        return _blocked(assertion, "read_only_required")
    connection_id = assertion.connection_id or ""
    dialect = approved_connections.get(connection_id)
    expected = str(assertion.definition.get("dialect") or "")
    if dialect is None or dialect != expected:
        return _blocked(assertion, "connection_not_approved")
    if reader is None:
        return _blocked(assertion, "infrastructure_unavailable")
    raw_parameters = assertion.definition.get("parameters")
    required = (
        tuple(str(item) for item in raw_parameters)
        if isinstance(raw_parameters, list)
        else ()
    )
    try:
        bound = require_keys(parameters, required)
        prepared = prepare_select(
            str(assertion.definition.get("sql") or ""),
            dialect=dialect,
            parameters=bound,
            allow_tables=_strings(assertion.definition.get("allow_tables")),
            max_rows=_cap(assertion.definition.get("max_rows"), default=20, limit=100),
        )
    except HubError as exc:
        return _blocked(assertion, exc.code)
    column = str(assertion.definition.get("expect_column") or "")
    expected_value = str(assertion.definition.get("expect_equals") or "")
    if not column or not expected_value or sensitive_column(column):
        return _blocked(assertion, "assertion_incomplete")
    timeout_ms = _cap(
        assertion.definition.get("timeout_ms"), default=1000, limit=60_000
    )
    protections = (
        postgresql_protections(timeout_ms)
        if dialect == "postgresql"
        else mysql_protections(timeout_ms)
    )
    try:
        reader.prepare(protections)
    except HubError as exc:
        return _status(assertion, ExecutionStatus.error, True, exc.code)
    attempts = _cap(assertion.definition.get("poll_attempts"), default=1, limit=20)
    correlation_key = required[0] if required else ""

    def probe() -> tuple[dict[str, str], ...] | None:
        if cancel is not None and cancel():
            raise HubError("cancelled", "verification was cancelled")
        rows = reader.query(prepared.statement, prepared.parameters, timeout_ms)
        return rows or None

    try:
        outcome, rows = poll_for_rows(
            probe,
            timeout_seconds=max(timeout_ms / 1000, 0.05),
            interval_seconds=0.01,
            max_attempts=attempts,
        )
    except HubError as exc:
        if exc.code == "database_connection_failed":
            return _status(assertion, ExecutionStatus.error, True, exc.code)
        if exc.code == "database_timeout":
            return _status(assertion, ExecutionStatus.timed_out, True, exc.code)
        if exc.code == "cancelled":
            return _status(assertion, ExecutionStatus.cancelled, False, exc.code)
        return _blocked(assertion, exc.code)
    if not outcome.completed:
        return _status(
            assertion,
            ExecutionStatus.inconclusive,
            True,
            "eventual_consistency_timeout",
        )
    cleaned = redact_rows(rows)
    if len(json.dumps(cleaned)) > _RESULT_LIMIT:
        return _status(
            assertion, ExecutionStatus.inconclusive, True, "result_too_large"
        )
    if not cleaned:
        return _status(assertion, ExecutionStatus.inconclusive, True, "no_rows")
    row = cleaned[0]
    if correlation_key and not matches(
        bound[correlation_key], row.get(correlation_key)
    ):
        return _status(assertion, ExecutionStatus.failed, True, "correlation_mismatch")
    observed = row.get(column)
    if observed != expected_value:
        return CheckResult(
            assertion_id=assertion.id,
            kind=assertion.kind,
            status=ExecutionStatus.failed,
            executed=True,
            verified=False,
            reason="assertion_mismatch",
            observations=((column, observed or ""),),
        )
    return CheckResult(
        assertion_id=assertion.id,
        kind=assertion.kind,
        status=ExecutionStatus.passed,
        executed=True,
        verified=True,
        reason="assertion_matched",
        observations=((column, observed),),
    )


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _cap(value: object, *, default: int, limit: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(1, min(value, limit))


def _blocked(assertion: AssertionDefinition, reason: str) -> CheckResult:
    return _status(assertion, ExecutionStatus.blocked, False, reason)


def _status(
    assertion: AssertionDefinition,
    status: ExecutionStatus,
    executed: bool,
    reason: str,
) -> CheckResult:
    return CheckResult(
        assertion_id=assertion.id,
        kind=assertion.kind,
        status=status,
        executed=executed,
        verified=False,
        reason=reason,
    )
