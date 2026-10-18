"""Assess release readiness from a stored manifest and mapped records.

Purpose: read requirement and defect registers without approving a release.
Milestone: 10
Status: IMPLEMENTED
Ownership: release.service
Dependencies: Evidence manifests, coverage, and risk.
Expected tests: missing registers, critical defects, and unchanged review.
"""

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import TypeAdapter, ValidationError

from qa_mcp_hub.config.loader import load_config
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.evidence.models import EvidenceCheckStatus
from qa_mcp_hub.evidence.service import validate_evidence
from qa_mcp_hub.release.coverage_engine import calculate_coverage
from qa_mcp_hub.release.models import DefectRecord, MappedRequirement, ReleaseReport
from qa_mcp_hub.release.report_builder import report_html, report_json
from qa_mcp_hub.release.risk_engine import assess
from qa_mcp_hub.storage.artifact_store import ArtifactStore
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.verification.service import workspace_for
from qa_mcp_hub.workflows.models import ExecutionRecord, ExecutionStatus
from qa_mcp_hub.workflows.service import resolve_execution_path

_LINKS = TypeAdapter(tuple[MappedRequirement, ...])
_DEFECTS = TypeAdapter(tuple[DefectRecord, ...])
_STATUS = {
    ExecutionStatus.passed: EvidenceCheckStatus.passed,
    ExecutionStatus.failed: EvidenceCheckStatus.failed,
    ExecutionStatus.blocked: EvidenceCheckStatus.blocked,
    ExecutionStatus.inconclusive: EvidenceCheckStatus.inconclusive,
}


def assess_release(execution_id: str, *, profile: str | None = None) -> ReleaseReport:
    """Return a recommendation and leave the stored review state unchanged."""
    before = _review(execution_id, profile)
    manifest = validate_evidence(execution_id, profile=profile)
    workspace = _workspace(profile)
    links, coverage_recorded = _links(workspace)
    defects, _recorded = _defects(workspace)
    executed = _executed_cases(execution_id, profile)
    coverage = calculate_coverage(links, executed)
    report = assess(
        manifest,
        coverage,
        defects,
        coverage_recorded=coverage_recorded,
    )
    if _review(execution_id, profile) != before:
        raise HubError("approval_rejected", "release assessment changed the review")
    return report.model_copy(update={"review_state": manifest.review_state})


def generate_report(execution_id: str, *, profile: str | None = None) -> ReleaseReport:
    """Write the release report beside the evidence artifacts."""
    report = assess_release(execution_id, profile=profile)
    workspace = _workspace(profile)
    store = ArtifactStore(workspace)
    store.write(execution_id, "release.json", report_json(report))
    store.write(execution_id, "release.html", report_html(report))
    return report


def _executed_cases(
    execution_id: str, profile: str | None
) -> dict[str, EvidenceCheckStatus]:
    _selected, record = _record(execution_id, profile)
    found: dict[str, EvidenceCheckStatus] = {}
    for step in record.step_results:
        if not step.executed:
            continue
        found[step.target] = _STATUS.get(step.status, EvidenceCheckStatus.blocked)
    return found


def _links(workspace: Path) -> tuple[tuple[MappedRequirement, ...], bool]:
    loaded = _read_yaml(workspace / "evidence" / "requirement-links.yaml")
    if loaded is None:
        return (), False
    raw = loaded.get("links")
    if not isinstance(raw, list):
        raise HubError("mapping_invalid", "requirement map is invalid")
    try:
        return _LINKS.validate_python(raw), True
    except ValidationError as exc:
        raise HubError("mapping_invalid", "requirement map is invalid") from exc


def _defects(workspace: Path) -> tuple[tuple[DefectRecord, ...] | None, bool]:
    loaded = _read_yaml(workspace / "evidence" / "defects.yaml")
    if loaded is None:
        return None, False
    raw = loaded.get("defects")
    if not isinstance(raw, list):
        raise HubError("mapping_invalid", "defect register is invalid")
    try:
        return _DEFECTS.validate_python(raw), True
    except ValidationError as exc:
        raise HubError("mapping_invalid", "defect register is invalid") from exc


def _read_yaml(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise HubError("mapping_invalid", "release register is invalid")
    return loaded


def _review(execution_id: str, profile: str | None) -> str:
    selected, _workspace_path = workspace_for(load_config(), profile)
    store = ExecutionStore(resolve_execution_path())
    review, _raw = store.manifest_row(selected, execution_id)
    return review


def _workspace(profile: str | None) -> Path:
    _selected, workspace = workspace_for(load_config(), profile)
    return workspace


def _record(execution_id: str, profile: str | None) -> tuple[str, ExecutionRecord]:
    selected, _workspace_path = workspace_for(load_config(), profile)
    store = ExecutionStore(resolve_execution_path())
    return selected, store.get(selected, execution_id)
