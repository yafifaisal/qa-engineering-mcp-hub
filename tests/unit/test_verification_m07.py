"""Milestone 07 database, Kafka, and E2E verification."""

import importlib.util
import inspect
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from fastmcp import Client
from pydantic import ValidationError

from qa_mcp_hub.adapters.database.base import redact_rows
from qa_mcp_hub.adapters.database.mysql import mysql_protections, open_mysql
from qa_mcp_hub.adapters.database.postgresql import (
    open_postgresql,
    postgresql_protections,
)
from qa_mcp_hub.adapters.streaming.kafka import (
    BoundedObserver,
    TopicRead,
    observer_settings,
    open_observer,
)
from qa_mcp_hub.config.models import ConnectionConfig, DeploymentKind
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.mcp.tools.verification import (
    find_kafka_event_tool,
    run_database_assertion_tool,
)
from qa_mcp_hub.security.sql_policy import prepare_select
from qa_mcp_hub.server import mcp
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.verification.assertion_registry import load_assertions
from qa_mcp_hub.verification.database_assertions import run_database_assertion
from qa_mcp_hub.verification.invariant_engine import evaluate_invariant
from qa_mcp_hub.verification.kafka_assertions import run_kafka_assertion
from qa_mcp_hub.verification.models import AssertionDefinition
from qa_mcp_hub.verification.runtime import clear_readers, install_readers
from qa_mcp_hub.workflows.models import ApiOnlyEvidence, ExecutionStatus
from qa_mcp_hub.workflows.service import ExecutionService

_HELPERS = Path(__file__).with_name("test_execution_m06.py")
_SPEC = importlib.util.spec_from_file_location("m06_helpers", _HELPERS)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("milestone 06 helpers are unavailable")
_M06 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_M06)
_NOW = _M06._NOW
_collection = _M06._collection
_config = _M06._config
_fake = _M06._fake

_ROW = {"order_id": "100", "status": "paid"}
_QUERY = "SELECT order_id, status FROM billing.orders WHERE order_id = :order_id"
_READ_CTE = (
    "WITH recent AS (SELECT order_id, status FROM billing.orders "
    "WHERE order_id = :order_id) SELECT order_id, status FROM recent "
    "WHERE order_id = :order_id"
)
_DELETE_CTE = (
    "WITH recent AS (SELECT order_id FROM billing.orders "
    "WHERE order_id = :order_id) DELETE FROM billing.orders"
)
_INJECTED = (
    "SELECT order_id FROM billing.orders "
    "WHERE order_id = :order_id; DROP TABLE billing.orders"
)


class ScriptedDatabase:
    """Fixture session. It records protections and bound parameters."""

    def __init__(
        self,
        pages: list[tuple[dict[str, str], ...]],
        fail: str | None = None,
    ) -> None:
        self.pages = list(pages)
        self.fail = fail
        self.protections: list[str] = []
        self.statements: list[tuple[str, tuple[str, ...]]] = []

    def prepare(self, protections: tuple[str, ...]) -> None:
        self.protections.extend(protections)

    def query(
        self,
        statement: str,
        parameters: tuple[str, ...],
        timeout_ms: int,
    ) -> tuple[dict[str, str], ...]:
        self.statements.append((statement, parameters))
        if self.fail == "connect":
            raise HubError("database_connection_failed", "database connection failed")
        if self.fail == "timeout":
            raise HubError("database_timeout", "database statement timed out")
        if not self.pages:
            return ()
        return self.pages.pop(0)


class CommittedReader:
    """A reader that reports an offset commit. The assertion must reject it."""

    offsets_committed = 1

    def read_topic(
        self,
        topic: str,
        *,
        max_messages: int,
        timeout_seconds: float,
    ) -> TopicRead:
        return TopicRead(
            messages=(_ROW,),
            offsets_committed=1,
            scanned=1,
        )

    def commit(self) -> None:
        raise AssertionError("assertion must not commit")


def _write_assertion(workspace, relative: str, document: dict[str, object]) -> None:
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def _assertions(workspace, **overrides: object) -> None:
    poll = int(overrides.get("poll_attempts", 1))
    max_messages = int(overrides.get("max_messages", 50))
    kafka_definition: dict[str, object] = {
        "topic": "orders",
        "correlation_key": "order_id",
        "parameters": ["order_id"],
        "required_fields": ["order_id", "status"],
        "max_messages": max_messages,
        "timeout_seconds": 2,
        "group_id": "qa-mcp-observer-billing",
        "protocol": "SASL_SSL",
        "mechanism": "SCRAM-SHA-512",
    }
    if overrides.get("dlq", True):
        kafka_definition["dlq_topic"] = "orders.dlq"
    if overrides.get("consumer"):
        kafka_definition["require_consumer_completion"] = True
    _write_assertion(
        workspace,
        "assertions/database/order-row.yaml",
        {
            "schema_version": 1,
            "id": "order-row",
            "kind": "database",
            "implementation_status": "IMPLEMENTED",
            "enabled": True,
            "connection_id": "billing-db",
            "definition": {
                "dialect": "postgresql",
                "read_only": True,
                "sql": _QUERY,
                "parameters": ["order_id"],
                "allow_tables": ["billing.orders"],
                "expect_column": "status",
                "expect_equals": "paid",
                "max_rows": 20,
                "timeout_ms": 1000,
                "poll_attempts": poll,
            },
        },
    )
    _write_assertion(
        workspace,
        "assertions/sql/order-mysql.yaml",
        {
            "schema_version": 1,
            "id": "order-mysql",
            "kind": "sql",
            "implementation_status": "IMPLEMENTED",
            "enabled": True,
            "connection_id": "billing-mysql",
            "definition": {
                "dialect": "mysql",
                "read_only": True,
                "sql": _QUERY,
                "parameters": ["order_id"],
                "allow_tables": ["billing.orders"],
                "expect_column": "status",
                "expect_equals": "paid",
                "max_rows": 20,
                "timeout_ms": 1000,
                "poll_attempts": 1,
            },
        },
    )
    _write_assertion(
        workspace,
        "assertions/kafka/order-event.yaml",
        {
            "schema_version": 1,
            "id": "order-event",
            "kind": "kafka",
            "implementation_status": "IMPLEMENTED",
            "enabled": True,
            "connection_id": "billing-kafka",
            "definition": kafka_definition,
        },
    )
    _write_assertion(
        workspace,
        "assertions/business/order-paid.yaml",
        {
            "schema_version": 1,
            "id": "order-paid",
            "kind": "business",
            "implementation_status": "IMPLEMENTED",
            "enabled": True,
            "definition": {
                "left": "database.order-row.status",
                "right": "kafka.order-event.status",
            },
        },
    )


def _workflow(workspace) -> None:
    (workspace / "workflows" / "e2e" / "full.yaml").write_text(
        "schema_version: 1\n"
        "id: billing-e2e\n"
        "name: Billing end to end\n"
        "implementation_status: IMPLEMENTED\n"
        "enabled: true\n"
        "approved: true\n"
        "evidence_policy: full-e2e\n"
        "steps:\n"
        "  - id: run-bruno\n"
        "    kind: api_suite\n"
        "    target: billing-bruno\n"
        "    depends_on: []\n"
        "    assertion_ids: [status-ok]\n"
        "  - id: check-db\n"
        "    kind: database_assertion\n"
        "    target: order-row\n"
        "    depends_on: [run-bruno]\n"
        "  - id: check-event\n"
        "    kind: kafka_assertion\n"
        "    target: order-event\n"
        "    depends_on: [run-bruno]\n"
        "  - id: check-invariant\n"
        "    kind: business_assertion\n"
        "    target: order-paid\n"
        "    depends_on: [check-db, check-event]\n",
        encoding="utf-8",
    )


def _connected(workspace):
    base = _config(workspace, dry_run=False)
    alpha = base.profiles["alpha"].model_copy(
        update={"connection_ids": ("billing-db", "billing-mysql", "billing-kafka")}
    )
    return base.model_copy(
        update={
            "profiles": {"alpha": alpha, "beta": base.profiles["beta"]},
            "connections": (
                ConnectionConfig(
                    id="billing-db",
                    provider=ProviderKind.postgresql,
                    deployment=DeploymentKind.SELF_MANAGED,
                ),
                ConnectionConfig(
                    id="billing-mysql",
                    provider=ProviderKind.mysql,
                    deployment=DeploymentKind.SELF_MANAGED,
                ),
                ConnectionConfig(
                    id="billing-kafka",
                    provider=ProviderKind.kafka,
                    deployment=DeploymentKind.SELF_MANAGED,
                ),
            ),
        }
    )


def _service(tmp_path, workspace, monkeypatch, database, kafka):
    script = _fake(tmp_path / "bin", "pass")
    monkeypatch.setenv("QA_MCP_BRUNO_BIN", str(script))
    monkeypatch.setenv("QA_MCP_NEWMAN_BIN", str(script))
    monkeypatch.setenv("QA_MCP_EXECUTION_PATH", str(tmp_path / "runs.sqlite"))
    config = _connected(workspace)
    return ExecutionService(
        ExecutionStore(tmp_path / "runs.sqlite"),
        clock=lambda: _NOW,
        config_loader=lambda: config,
        id_factory=lambda: "run-e2e",
        database_reader=database,
        kafka_reader=kafka,
    )


def _database(workspace, name: str) -> AssertionDefinition:
    return load_assertions(workspace)[name]


def _approved() -> dict[str, str]:
    return {
        "billing-db": "postgresql",
        "billing-mysql": "mysql",
        "billing-kafka": "kafka",
    }


def test_postgres_and_mysql_bind_parameters_and_reject_injection(tmp_path) -> None:
    workspace = tmp_path / "ws"
    _assertions(workspace)
    postgres = ScriptedDatabase([(_ROW,)])
    mysql = ScriptedDatabase([(_ROW,)])
    parameters = {"order_id": "100 OR 1=1"}
    postgres_result = run_database_assertion(
        _database(workspace, "order-row"),
        parameters,
        reader=postgres,
        approved_connections=_approved(),
    )
    mysql_result = run_database_assertion(
        _database(workspace, "order-mysql"),
        parameters,
        reader=mysql,
        approved_connections=_approved(),
    )
    assert postgres_result.status is ExecutionStatus.failed
    assert mysql_result.status is ExecutionStatus.failed
    assert postgres.protections == list(postgresql_protections(1000))
    assert mysql.protections == list(mysql_protections(1000))
    assert all(
        item.startswith("SELECT")
        or item.startswith("SET")
        or item.startswith("BEGIN")
        or item.startswith("START")
        for item in postgres.protections
    )
    statement, bound = postgres.statements[0]
    assert "$1" in statement
    assert "100 OR 1=1" not in statement
    assert bound == ("100 OR 1=1",)
    assert "%s" in mysql.statements[0][0]
    injected = run_database_assertion(
        _database(workspace, "order-row").model_copy(
            update={
                "definition": {
                    **_database(workspace, "order-row").definition,
                    "sql": _INJECTED,
                }
            }
        ),
        {"order_id": "100"},
        reader=ScriptedDatabase([]),
        approved_connections=_approved(),
    )
    assert injected.status is ExecutionStatus.blocked
    assert injected.reason == "sql_rejected"
    with pytest.raises(HubError) as rejected:
        prepare_select(
            _DELETE_CTE,
            dialect="postgresql",
            parameters={"order_id": "100"},
            allow_tables=("billing.orders",),
            max_rows=20,
        )
    assert rejected.value.code == "sql_rejected"
    prepared = prepare_select(
        _READ_CTE,
        dialect="postgresql",
        parameters={"order_id": "100"},
        allow_tables=("billing.orders",),
        max_rows=20,
    )
    assert prepared.parameters == ("100", "100")
    assert "LIMIT 20" in prepared.statement


def test_connection_timeout_and_read_only_stay_distinct(tmp_path) -> None:
    workspace = tmp_path / "ws"
    _assertions(workspace)
    assertion = _database(workspace, "order-row")
    connected = run_database_assertion(
        assertion,
        {"order_id": "100"},
        reader=ScriptedDatabase([], fail="connect"),
        approved_connections=_approved(),
    )
    timed = run_database_assertion(
        assertion,
        {"order_id": "100"},
        reader=ScriptedDatabase([], fail="timeout"),
        approved_connections=_approved(),
    )
    blocked = run_database_assertion(
        assertion,
        {"order_id": "100"},
        reader=None,
        approved_connections=_approved(),
    )
    assert connected.status is ExecutionStatus.error
    assert connected.reason == "database_connection_failed"
    assert timed.status is ExecutionStatus.timed_out
    assert timed.status is not ExecutionStatus.failed
    assert blocked.status is ExecutionStatus.blocked
    assert blocked.reason == "infrastructure_unavailable"
    write = assertion.model_copy(
        update={
            "definition": {
                **assertion.definition,
                "sql": "INSERT INTO billing.orders (order_id) VALUES (:order_id)",
            }
        }
    )
    rejected = run_database_assertion(
        write,
        {"order_id": "100"},
        reader=ScriptedDatabase([(_ROW,)]),
        approved_connections=_approved(),
    )
    assert rejected.status is ExecutionStatus.blocked
    assert rejected.reason == "sql_rejected"


def test_eventual_consistency_and_correlation_mismatch(tmp_path) -> None:
    workspace = tmp_path / "ws"
    _assertions(workspace, poll_attempts=3)
    found = run_database_assertion(
        _database(workspace, "order-row"),
        {"order_id": "100"},
        reader=ScriptedDatabase([(), (_ROW,)]),
        approved_connections=_approved(),
    )
    missing = run_database_assertion(
        _database(workspace, "order-row"),
        {"order_id": "100"},
        reader=ScriptedDatabase([(), ()]),
        approved_connections=_approved(),
    )
    mismatched = run_database_assertion(
        _database(workspace, "order-row"),
        {"order_id": "100"},
        reader=ScriptedDatabase([({"order_id": "200", "status": "paid"},)]),
        approved_connections=_approved(),
    )
    assert found.status is ExecutionStatus.passed
    assert found.verified is True
    assert missing.status is ExecutionStatus.inconclusive
    assert missing.reason == "eventual_consistency_timeout"
    assert mismatched.status is ExecutionStatus.failed
    assert mismatched.reason == "correlation_mismatch"
    redacted = redact_rows(({"email": "person@example.com", "status": "paid"},))
    assert redacted[0]["email"] == "[REDACTED]"
    assert "person@example.com" not in str(redacted)


def test_kafka_schema_dlq_retention_and_offsets(tmp_path) -> None:
    workspace = tmp_path / "ws"
    _assertions(workspace)
    settings = observer_settings(
        protocol="SASL_SSL",
        mechanism="SCRAM-SHA-512",
        group_id="qa-mcp-observer-billing",
    )
    assert settings["enable.auto.commit"] is False
    assert settings["auto.offset.reset"] == "latest"
    with pytest.raises(HubError):
        observer_settings(protocol="PLAINTEXT", mechanism=None, group_id="billing")
    observer = BoundedObserver(settings, {"orders": (_ROW,)})
    observed = run_kafka_assertion(
        _database(workspace, "order-event"),
        {"order_id": "100"},
        reader=observer,
        approved_connections=_approved(),
    )
    assert observed.status is ExecutionStatus.passed
    assert observed.published is True
    assert observed.consumer_completed is False
    assert observed.schema_validated is True
    assert observer.offsets_committed == 0
    with pytest.raises(HubError) as refused:
        observer.commit()
    assert refused.value.code == "kafka_rejected"
    invalid = BoundedObserver(settings, {"orders": ({"order_id": "100"},)})
    schema = run_kafka_assertion(
        _database(workspace, "order-event"),
        {"order_id": "100"},
        reader=invalid,
        approved_connections=_approved(),
    )
    assert schema.status is ExecutionStatus.failed
    assert schema.reason == "schema_mismatch"
    gap = BoundedObserver(settings, {}, retention_gaps=frozenset({"orders"}))
    retained = run_kafka_assertion(
        _database(workspace, "order-event"),
        {"order_id": "100"},
        reader=gap,
        approved_connections=_approved(),
    )
    assert retained.status is ExecutionStatus.inconclusive
    assert retained.reason == "retention_gap"
    empty = BoundedObserver(settings, {})
    absent = run_kafka_assertion(
        _database(workspace, "order-event"),
        {"order_id": "100"},
        reader=empty,
        approved_connections=_approved(),
    )
    assert absent.reason == "event_not_observed"
    dead = BoundedObserver(
        settings,
        {"orders": (_ROW,), "orders.dlq": (_ROW,)},
    )
    dlq = run_kafka_assertion(
        _database(workspace, "order-event"),
        {"order_id": "100"},
        reader=dead,
        approved_connections=_approved(),
    )
    assert dlq.status is ExecutionStatus.failed
    assert dlq.reason == "dlq_event"
    assert dead.topics == ["orders", "orders.dlq"]
    committed = run_kafka_assertion(
        _database(workspace, "order-event"),
        {"order_id": "100"},
        reader=CommittedReader(),
        approved_connections=_approved(),
    )
    assert committed.status is ExecutionStatus.error
    assert committed.reason == "offset_commit_detected"
    _assertions(workspace, max_messages=500)
    bounded = BoundedObserver(settings, {"orders": (_ROW,)})
    wide = run_kafka_assertion(
        _database(workspace, "order-event"),
        {"order_id": "100"},
        reader=bounded,
        approved_connections=_approved(),
    )
    assert wide.status is ExecutionStatus.blocked
    assert bounded.topics == []


def test_e2e_pass_fail_inconclusive_and_missing_checks(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _collection(workspace)
    _assertions(workspace, poll_attempts=1)
    _workflow(workspace)
    database = ScriptedDatabase([(_ROW,)])
    kafka = BoundedObserver(
        observer_settings(
            protocol="SASL_SSL",
            mechanism="SCRAM-SHA-512",
            group_id="qa-mcp-observer-billing",
        ),
        {"orders": (_ROW,)},
    )
    service = _service(tmp_path, workspace, monkeypatch, database, kafka)
    passed = service.submit(
        workflow_id="billing-e2e",
        execute=True,
        correlation={"order_id": "100"},
    )
    assert passed.run is not None
    assert passed.run.status is ExecutionStatus.passed
    assert passed.run.evidence.database_verified is True
    assert passed.run.evidence.kafka_verified is True
    assert "database" in passed.run.evidence.checks
    assert "kafka" in passed.run.evidence.checks
    assert "consumer_completion_not_observed" in passed.run.warnings
    stored = service._store.steps("alpha", passed.run.execution_id)
    assert {item.step_id for item in stored} == {
        "run-bruno",
        "check-db",
        "check-event",
        "check-invariant",
    }
    assert service._store.steps("beta", passed.run.execution_id) == ()
    failed = _service(
        tmp_path / "fail",
        workspace,
        monkeypatch,
        ScriptedDatabase([({"order_id": "100", "status": "unpaid"},)]),
        kafka,
    ).submit(workflow_id="billing-e2e", execute=True, correlation={"order_id": "100"})
    assert failed.run is not None
    assert failed.run.status is ExecutionStatus.failed
    assert failed.run.evidence.database_verified is False
    inconclusive = _service(
        tmp_path / "wait",
        workspace,
        monkeypatch,
        ScriptedDatabase([()]),
        kafka,
    ).submit(workflow_id="billing-e2e", execute=True, correlation={"order_id": "100"})
    assert inconclusive.run is not None
    assert inconclusive.run.status is ExecutionStatus.inconclusive
    assert inconclusive.run.status is not ExecutionStatus.passed
    blocked = _service(tmp_path / "blocked", workspace, monkeypatch, None, None).submit(
        workflow_id="billing-e2e",
        execute=True,
        correlation={"order_id": "100"},
    )
    assert blocked.run is not None
    assert blocked.run.status is ExecutionStatus.blocked
    assert blocked.run.evidence.database_verified is False
    assert blocked.run.evidence.kafka_verified is False
    with pytest.raises(ValidationError):
        ApiOnlyEvidence(
            execution_id="run",
            profile_id="alpha",
            workflow_id="billing-e2e",
            suite_ids=("billing-bruno",),
            suite_version="1",
            source_revision=None,
            checks=("api", "database"),
            database_verified=False,
            status=ExecutionStatus.passed,
            runner_exit_code=0,
            runner_completed=True,
            assertion_total=1,
            assertion_failed=0,
        )
    invariant = evaluate_invariant(
        _database(workspace, "order-paid"),
        {
            "database.order-row.status": "paid",
            "kafka.order-event.status": "unpaid",
        },
    )
    assert invariant.status is ExecutionStatus.failed
    assert invariant.reason == "invariant_mismatch"


def test_live_drivers_are_not_faked(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HubError) as postgres:
        open_postgresql("billing-db")
    assert postgres.value.code == "infrastructure_unavailable"
    monkeypatch.setenv("QA_MCP_LIVE_DATABASES", "1")
    with pytest.raises(HubError) as bundled:
        open_mysql("billing-mysql")
    assert "not bundled" in bundled.value.message
    monkeypatch.delenv("QA_MCP_LIVE_DATABASES")
    with pytest.raises(HubError) as kafka:
        open_observer({"enable.auto.commit": False})
    assert kafka.value.code == "infrastructure_unavailable"


def test_pass_cannot_claim_an_unverified_database() -> None:
    evidence = ApiOnlyEvidence(
        execution_id="run",
        profile_id="alpha",
        workflow_id="api",
        suite_ids=("suite",),
        suite_version="1",
        source_revision=None,
        checks=("api",),
        database_verified=False,
        kafka_verified=False,
        status=ExecutionStatus.passed,
        runner_exit_code=0,
        runner_completed=True,
        assertion_total=1,
        assertion_failed=0,
    )
    assert evidence.database_verified is False
    assert evidence.kafka_verified is False


@pytest.mark.asyncio
async def test_mcp_verification_tools_reject_sql_and_run_registered_checks(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert "sql" not in inspect.signature(run_database_assertion_tool).parameters
    assert "commit" not in inspect.signature(find_kafka_event_tool).parameters
    workspace = tmp_path / "ws"
    _collection(workspace)
    _assertions(workspace)
    _workflow(workspace)
    script = _fake(tmp_path / "bin", "pass")
    monkeypatch.setenv("QA_MCP_BRUNO_BIN", str(script))
    monkeypatch.setenv("QA_MCP_NEWMAN_BIN", str(script))
    monkeypatch.setenv("QA_MCP_EXECUTION_PATH", str(tmp_path / "runs.sqlite"))
    config = _connected(workspace)
    monkeypatch.setattr(
        "qa_mcp_hub.workflows.service.load_config", lambda path=None: config
    )
    monkeypatch.setattr(
        "qa_mcp_hub.verification.service.load_config", lambda path=None: config
    )
    database = ScriptedDatabase([(_ROW,), (_ROW,)])
    kafka = BoundedObserver(
        observer_settings(
            protocol="SASL_SSL",
            mechanism="SCRAM-SHA-512",
            group_id="qa-mcp-observer-billing",
        ),
        {"orders": (_ROW,)},
    )
    install_readers(database=database, kafka=kafka)
    try:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {tool.name for tool in tools}
            assert {
                "list_registered_assertions",
                "run_database_assertion",
                "find_kafka_event",
                "verify_e2e_workflow",
            } <= names
            database_tool = next(
                tool for tool in tools if tool.name == "run_database_assertion"
            )
            assert "sql" not in database_tool.input_schema["properties"]
            listed = await client.call_tool("list_registered_assertions", {})
            assert listed.structured_content is not None
            payload = listed.structured_content
            rendered = str(payload)
            assert "SELECT" not in rendered
            checked = await client.call_tool(
                "run_database_assertion",
                {"assertion_id": "order-row", "parameters": {"order_id": "100"}},
            )
            assert checked.structured_content is not None
            assert checked.structured_content["status"] == "PASSED"
            found = await client.call_tool(
                "find_kafka_event",
                {"assertion_id": "order-event", "correlation": {"order_id": "100"}},
            )
            assert found.structured_content is not None
            assert found.structured_content["consumer_completed"] is False
            verified = await client.call_tool(
                "verify_e2e_workflow",
                {
                    "workflow_id": "billing-e2e",
                    "execute": True,
                    "correlation": {"order_id": "100"},
                },
            )
            assert verified.structured_content is not None
            assert verified.structured_content["run"]["status"] == "PASSED"
            assert (
                verified.structured_content["run"]["evidence"]["kafka_verified"] is True
            )
    finally:
        clear_readers()
