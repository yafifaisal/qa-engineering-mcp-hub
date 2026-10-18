"""Locate one registered Kafka event without committing offsets.

Purpose: bound the scan, validate a registered schema, and report DLQ hits.
Milestone: 07
Status: IMPLEMENTED
Ownership: verification.kafka_assertions
Dependencies: Kafka observer and correlation keys.
Expected tests: schema, retention, DLQ, and unchanged offsets.
"""

from qa_mcp_hub.adapters.database.base import redact_rows, sensitive_column
from qa_mcp_hub.adapters.streaming.kafka import TopicReader, observer_settings
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.verification.correlation import matches, require_keys
from qa_mcp_hub.verification.models import AssertionDefinition, CheckResult
from qa_mcp_hub.workflows.models import ExecutionStatus


def run_kafka_assertion(
    assertion: AssertionDefinition,
    parameters: dict[str, str],
    *,
    reader: TopicReader | None,
    approved_connections: dict[str, str],
) -> CheckResult:
    """Observe one topic. Publication is not consumer completion."""
    if assertion.kind != "kafka":
        return _result(assertion, ExecutionStatus.blocked, False, "assertion_kind")
    connection_id = assertion.connection_id or ""
    if approved_connections.get(connection_id) != "kafka":
        return _result(
            assertion, ExecutionStatus.blocked, False, "connection_not_approved"
        )
    if reader is None:
        return _result(
            assertion, ExecutionStatus.blocked, False, "infrastructure_unavailable"
        )
    definition = assertion.definition
    topic = definition.get("topic")
    key_name = definition.get("correlation_key")
    if not isinstance(topic, str) or not isinstance(key_name, str):
        return _result(
            assertion, ExecutionStatus.blocked, False, "assertion_incomplete"
        )
    if sensitive_column(key_name):
        return _result(assertion, ExecutionStatus.blocked, False, "sensitive_field")
    try:
        bound = require_keys(parameters, (key_name,))
        settings = observer_settings(
            protocol=str(definition.get("protocol") or ""),
            mechanism=_optional_str(definition.get("mechanism")),
            group_id=str(definition.get("group_id") or ""),
        )
        max_messages = _cap(definition.get("max_messages"), default=50, limit=200)
        timeout_seconds = _seconds(definition.get("timeout_seconds"))
    except HubError as exc:
        return _result(assertion, ExecutionStatus.blocked, False, exc.code)
    if settings.get("enable.auto.commit") is not False:
        return _result(
            assertion, ExecutionStatus.error, False, "offset_commit_detected"
        )
    try:
        batch = reader.read_topic(
            topic, max_messages=max_messages, timeout_seconds=timeout_seconds
        )
    except HubError as exc:
        return _result(assertion, ExecutionStatus.blocked, False, exc.code)
    if batch.offsets_committed != 0 or reader.offsets_committed != 0:
        return _result(assertion, ExecutionStatus.error, True, "offset_commit_detected")
    dlq = definition.get("dlq_topic")
    if isinstance(dlq, str) and dlq:
        try:
            dead = reader.read_topic(
                dlq, max_messages=max_messages, timeout_seconds=timeout_seconds
            )
        except HubError as exc:
            return _result(assertion, ExecutionStatus.blocked, True, exc.code)
        if dead.offsets_committed != 0:
            return _result(
                assertion, ExecutionStatus.error, True, "offset_commit_detected"
            )
        if _matching(dead.messages, key_name, bound[key_name]):
            return _result(assertion, ExecutionStatus.failed, True, "dlq_event")
    matched = _matching(batch.messages, key_name, bound[key_name])
    if matched is None:
        reason = "retention_gap" if batch.retention_gap else "event_not_observed"
        status = ExecutionStatus.inconclusive
        return _result(assertion, status, True, reason)
    required = definition.get("required_fields")
    fields = tuple(str(item) for item in required) if isinstance(required, list) else ()
    cleaned = redact_rows((matched,))[0]
    if fields:
        missing = [item for item in fields if item not in matched or not matched[item]]
        if missing:
            return _result(assertion, ExecutionStatus.failed, True, "schema_mismatch")
        schema_validated = True
        warning = ""
    else:
        schema_validated = False
        warning = "schema_not_registered"
    if definition.get("require_consumer_completion") is True:
        return CheckResult(
            assertion_id=assertion.id,
            kind=assertion.kind,
            status=ExecutionStatus.inconclusive,
            executed=True,
            verified=False,
            reason="consumer_completion_not_observed",
            published=True,
            consumer_completed=False,
            schema_validated=schema_validated,
            observations=tuple(cleaned.items()),
            warning=warning,
        )
    return CheckResult(
        assertion_id=assertion.id,
        kind=assertion.kind,
        status=ExecutionStatus.passed,
        executed=True,
        verified=True,
        reason="event_observed",
        published=True,
        consumer_completed=False,
        schema_validated=schema_validated,
        observations=tuple(cleaned.items()),
        warning=warning or "consumer_completion_not_observed",
    )


def _matching(
    messages: tuple[dict[str, str], ...],
    key_name: str,
    expected: str,
) -> dict[str, str] | None:
    for message in messages:
        if matches(expected, message.get(key_name)):
            return message
    return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _cap(value: object, *, default: int, limit: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    if value < 1 or value > limit:
        raise HubError("kafka_rejected", "message cap is outside the allowed range")
    return value


def _seconds(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 2.0
    if value <= 0 or value > 60:
        raise HubError("kafka_rejected", "kafka timeout is outside the allowed range")
    return float(value)


def _result(
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
