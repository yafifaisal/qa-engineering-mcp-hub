"""Evidence collection, completeness, rendering, and tamper checks."""

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from qa_mcp_hub.config.models import (
    CURRENT_SCHEMA_VERSION,
    HubConfig,
    ProfileConfig,
    QAWorkspaceReference,
)
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.evidence.models import EvidenceCheckStatus
from qa_mcp_hub.evidence.service import generate_evidence, validate_evidence
from qa_mcp_hub.storage.artifact_store import ArtifactStore
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.workflows.models import (
    ApiOnlyEvidence,
    ExecutionRecord,
    ExecutionStatus,
    StepEvidence,
)

NOW = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)
REVISION = "a" * 40


def test_api_only_omits_database_and_kafka(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    _save(tmp_path, _record(excerpt="token=qa_mcp_secret_value user=ada@example.com"))
    _bind(tmp_path, workspace, monkeypatch)
    manifest = generate_evidence("run-1", "api-only")
    names = {item.name for item in manifest.checks}
    assert "database" not in names
    assert "kafka" not in names
    assert manifest.overall is EvidenceCheckStatus.passed
    assert "qa_mcp_secret_value" not in manifest.http_excerpt
    assert "ada@example.com" not in manifest.http_excerpt
    assert manifest.review_state.value == "UNREVIEWED"
    html = (workspace / "evidence" / "artifacts" / "run-1" / "report.html").read_text(
        encoding="utf-8"
    )
    assert "<script>" not in html
    assert "PASSED" in html
    assert manifest.suite_version == "1"
    assert manifest.source_revision == REVISION


def test_e2e_missing_check_cannot_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    record = _record()
    record = record.model_copy(
        update={
            "step_results": (
                _step("api_suite", "example-api-smoke", evidence_ref="<script>"),
            )
        }
    )
    _save(tmp_path, record)
    _bind(tmp_path, workspace, monkeypatch)
    manifest = generate_evidence("run-1", "full-e2e")
    assert manifest.overall is not EvidenceCheckStatus.passed
    assert all(item.name != "database" or not item.executed for item in manifest.checks)
    html = (workspace / "evidence" / "artifacts" / "run-1" / "report.html").read_text(
        encoding="utf-8"
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_tamper_and_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    _save(tmp_path, _record())
    _bind(tmp_path, workspace, monkeypatch)
    first = generate_evidence("run-1", "api-only")
    second = generate_evidence("run-1", "api-only")
    assert second.artifacts == first.artifacts
    report = workspace / "evidence" / "artifacts" / "run-1" / "report.html"
    report.write_bytes(report.read_bytes() + b"x")
    with pytest.raises(HubError) as tampered:
        validate_evidence("run-1")
    assert tampered.value.code == "artifact_rejected"
    store = ArtifactStore(workspace)
    with pytest.raises(HubError) as traversal:
        store.write("run-1", "../escape.html", b"nope")
    assert traversal.value.code == "path_rejected"


def test_partial_and_crashed_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    partial = _record(status=ExecutionStatus.inconclusive).model_copy(
        update={
            "evidence": _evidence(status=ExecutionStatus.inconclusive),
            "runner_completed": True,
        }
    )
    _save(tmp_path, partial)
    _bind(tmp_path, workspace, monkeypatch)
    incomplete = generate_evidence("run-1", "api-database")
    assert incomplete.overall is not EvidenceCheckStatus.passed
    crashed = _record(execution_id="run-2", status=ExecutionStatus.error).model_copy(
        update={
            "evidence": _evidence(execution_id="run-2", status=ExecutionStatus.error),
            "runner_completed": False,
            "runner_exit_code": None,
        }
    )
    _save(tmp_path, crashed)
    recovered = generate_evidence("run-2", "api-only")
    assert recovered.overall is EvidenceCheckStatus.blocked


def _workspace(path: Path) -> Path:
    workspace = path / "ws"
    source = Path("templates/qa-workspace/evidence-policies")
    target = workspace / "evidence-policies"
    target.mkdir(parents=True)
    for item in source.glob("*.yaml"):
        shutil.copy(item, target / item.name)
    return workspace


def _bind(path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_MCP_EXECUTION_PATH", str(path / "runs.sqlite"))
    config = HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={"alpha": ProfileConfig(workspace_id="ws")},
        workspaces=(QAWorkspaceReference(id="ws", path=str(workspace)),),
    )
    monkeypatch.setattr("qa_mcp_hub.evidence.service.load_config", lambda: config)


def _save(path: Path, record: ExecutionRecord) -> None:
    ExecutionStore(path / "runs.sqlite").save(record)


def _record(
    *,
    execution_id: str = "run-1",
    status: ExecutionStatus = ExecutionStatus.passed,
    excerpt: str = "status=ok",
) -> ExecutionRecord:
    return ExecutionRecord(
        execution_id=execution_id,
        profile_id="alpha",
        workflow_id="billing",
        suite_ids=("example-api-smoke",),
        suite_version="1",
        source_revision=REVISION,
        status=status,
        assertion_status=status,
        runner_completed=status is ExecutionStatus.passed,
        runner_exit_code=0 if status is ExecutionStatus.passed else 1,
        transitions=("QUEUED", status.value),
        queued_at=NOW,
        started_at=NOW,
        finished_at=NOW,
        evidence=_evidence(execution_id=execution_id, status=status),
        excerpt=excerpt,
        step_results=(
            _step("api_suite", "example-api-smoke"),
            _step("database_assertion", "example-order-state", executed=False),
        ),
    )


def _evidence(
    *,
    execution_id: str = "run-1",
    status: ExecutionStatus = ExecutionStatus.passed,
) -> ApiOnlyEvidence:
    passed = status is ExecutionStatus.passed
    return ApiOnlyEvidence(
        execution_id=execution_id,
        profile_id="alpha",
        workflow_id="billing",
        suite_ids=("example-api-smoke",),
        suite_version="1",
        source_revision=REVISION,
        checks=("api",),
        assertion_total=1 if passed else 0,
        assertion_failed=0 if passed else 1,
        status=status,
        runner_exit_code=0 if passed else 1,
        runner_completed=passed,
    )


def _step(
    kind: str,
    target: str,
    *,
    executed: bool = True,
    evidence_ref: str = "step-ref",
) -> StepEvidence:
    return StepEvidence(
        step_id=kind,
        kind=kind,
        target=target,
        status=ExecutionStatus.passed if executed else ExecutionStatus.blocked,
        executed=executed,
        verified=executed,
        reason="observed" if executed else "not_run",
        evidence_ref=evidence_ref,
    )
