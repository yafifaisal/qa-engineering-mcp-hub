"""Release coverage and recommendations do not approve a release."""

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
from qa_mcp_hub.evidence.service import generate_evidence
from qa_mcp_hub.release.service import assess_release, generate_report
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.workflows.models import (
    ApiOnlyEvidence,
    ExecutionRecord,
    ExecutionStatus,
    StepEvidence,
)

NOW = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)
REVISION = "c" * 40


def test_unexecuted_mapping_is_uncovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _prepare(tmp_path, monkeypatch)
    _registers(workspace, defect_state="resolved")
    generate_evidence("run-1", "api-only")
    before = _review(tmp_path)
    report = assess_release("run-1")
    assert report.coverage_percent == 50
    assert report.recommendation == "NOT_READY"
    assert report.release_approved is False
    assert _review(tmp_path) == before


def test_critical_defect_blocks_without_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _prepare(tmp_path, monkeypatch)
    _registers(workspace, defect_state="open", only_passed=True)
    generate_evidence("run-1", "api-only")
    report = generate_report("run-1")
    assert report.recommendation == "BLOCKED"
    assert report.critical_open == 1
    assert report.release_approved is False
    assert report.review_state.value == "UNREVIEWED"
    html = (workspace / "evidence" / "artifacts" / "run-1" / "release.html").read_text(
        encoding="utf-8"
    )
    assert "Release approved: false" in html
    assert "<script>" not in html


def test_ready_recommendation_leaves_review_unreviewed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _prepare(tmp_path, monkeypatch)
    _registers(workspace, defect_state="resolved", only_passed=True)
    generate_evidence("run-1", "api-only")
    report = assess_release("run-1")
    assert report.recommendation == "READY_FOR_REVIEW"
    assert report.release_approved is False
    assert _review(tmp_path) == "UNREVIEWED"


def _prepare(path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    workspace = path / "ws"
    source = Path("templates/qa-workspace/evidence-policies")
    target = workspace / "evidence-policies"
    target.mkdir(parents=True)
    for item in source.glob("*.yaml"):
        shutil.copy(item, target / item.name)
    monkeypatch.setenv("QA_MCP_EXECUTION_PATH", str(path / "runs.sqlite"))
    config = HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={"alpha": ProfileConfig(workspace_id="ws")},
        workspaces=(QAWorkspaceReference(id="ws", path=str(workspace)),),
    )
    monkeypatch.setattr("qa_mcp_hub.evidence.service.load_config", lambda: config)
    monkeypatch.setattr("qa_mcp_hub.release.service.load_config", lambda: config)
    ExecutionStore(path / "runs.sqlite").save(_record())
    return workspace


def _registers(
    workspace: Path, *, defect_state: str, only_passed: bool = False
) -> None:
    root = workspace / "evidence"
    root.mkdir(parents=True)
    links = "links:\n  - requirement_id: REQ-1\n    case_id: example-api-smoke\n"
    if not only_passed:
        links += "  - requirement_id: REQ-2\n    case_id: example-order-state\n"
    (root / "requirement-links.yaml").write_text(links, encoding="utf-8")
    (root / "defects.yaml").write_text(
        f"defects:\n  - id: BUG-1\n    severity: critical\n    state: {defect_state}\n",
        encoding="utf-8",
    )


def _review(path: Path) -> str:
    review, _raw = ExecutionStore(path / "runs.sqlite").manifest_row("alpha", "run-1")
    return review


def _record() -> ExecutionRecord:
    return ExecutionRecord(
        execution_id="run-1",
        profile_id="alpha",
        workflow_id="billing",
        suite_ids=("example-api-smoke",),
        suite_version="1",
        source_revision=REVISION,
        status=ExecutionStatus.passed,
        assertion_status=ExecutionStatus.passed,
        runner_completed=True,
        runner_exit_code=0,
        transitions=("QUEUED", "PASSED"),
        queued_at=NOW,
        started_at=NOW,
        finished_at=NOW,
        evidence=ApiOnlyEvidence(
            execution_id="run-1",
            profile_id="alpha",
            workflow_id="billing",
            suite_ids=("example-api-smoke",),
            suite_version="1",
            source_revision=REVISION,
            checks=("api",),
            assertion_total=1,
            assertion_failed=0,
            status=ExecutionStatus.passed,
            runner_exit_code=0,
            runner_completed=True,
        ),
        step_results=(
            StepEvidence(
                step_id="api",
                kind="api_suite",
                target="example-api-smoke",
                status=ExecutionStatus.passed,
                executed=True,
                verified=True,
                reason="observed",
                evidence_ref="step-ref",
            ),
        ),
    )
