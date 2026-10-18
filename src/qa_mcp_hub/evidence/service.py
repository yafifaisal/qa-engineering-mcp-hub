"""Collect, validate, and preview evidence for one stored execution.

Purpose: orchestrate policy, collection, rendering, and artifact storage.
Milestone: 10
Status: IMPLEMENTED
Ownership: evidence.service
Dependencies: Evidence modules, the execution store, and the artifact store.
Expected tests: missing runs, completeness, and unchanged review state.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from qa_mcp_hub.config.loader import load_config
from qa_mcp_hub.config.models import HubConfig
from qa_mcp_hub.core.approvals import ApprovalLedger
from qa_mcp_hub.evidence.collector import collect_checks
from qa_mcp_hub.evidence.manifest import artifact_for, verify_artifact
from qa_mcp_hub.evidence.models import EvidenceManifest, PublicationPreview, ReviewState
from qa_mcp_hub.evidence.policy_registry import load_policies, require_policy
from qa_mcp_hub.evidence.policy_validator import validate_policy
from qa_mcp_hub.evidence.publisher import prepare_publication, publish_manifest
from qa_mcp_hub.evidence.renderer import render_report, render_summary, template_dir
from qa_mcp_hub.storage.artifact_store import ArtifactStore
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.verification.service import workspace_for
from qa_mcp_hub.workflows.models import ExecutionRecord
from qa_mcp_hub.workflows.service import resolve_execution_path

_ledger = ApprovalLedger()


def publication_ledger() -> ApprovalLedger:
    """Return the process ledger used by the publication tool."""
    return _ledger


def reset_publication_ledger() -> None:
    """Replace the process ledger. Tests use this between cases."""
    global _ledger
    _ledger = ApprovalLedger()


def generate_evidence(
    execution_id: str,
    policy_id: str,
    *,
    profile: str | None = None,
    config: HubConfig | None = None,
    ci_job_id: str = "",
) -> EvidenceManifest:
    """Build a manifest from one stored run. Review state stays unreviewed."""
    selected, workspace, store, record = _loaded(execution_id, profile, config)
    policy = validate_policy(require_policy(load_policies(workspace), policy_id))
    observations = store.ci_observations(selected, ci_job_id) if ci_job_id else ()
    checks, excerpt, limitations, overall = collect_checks(
        record,
        policy,
        ci_references=observations,
        recovered=store.recovery_warning is not None,
    )
    generated_at = record.finished_at or record.queued_at
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    manifest = EvidenceManifest(
        execution_id=record.execution_id,
        profile_id=record.profile_id,
        policy_id=policy.id,
        suite_version=record.suite_version,
        source_revision=record.source_revision or "UNKNOWN",
        generated_at=generated_at,
        overall=overall,
        checks=checks,
        limitations=limitations,
        http_excerpt=excerpt,
        review_state=ReviewState.unreviewed,
    )
    _store_reports(workspace, store, manifest)
    review, raw = store.manifest_row(selected, execution_id)
    stored = EvidenceManifest.model_validate_json(raw)
    return stored.model_copy(update={"review_state": ReviewState(review)})


def validate_evidence(
    execution_id: str, *, profile: str | None = None
) -> EvidenceManifest:
    """Re-read artifacts and reject a digest mismatch. Review state is unchanged."""
    selected, workspace, store, _record = _loaded(execution_id, profile, None)
    review, raw = store.manifest_row(selected, execution_id)
    manifest = EvidenceManifest.model_validate_json(raw)
    artifacts = ArtifactStore(workspace)
    by_name = {item.name: item for item in manifest.artifacts}
    for name, expected in by_name.items():
        verify_artifact(artifacts.read(execution_id, name), expected)
    return manifest.model_copy(update={"review_state": ReviewState(review)})


def prepare_evidence(
    execution_id: str, destination: str, *, profile: str | None = None
) -> PublicationPreview:
    """Preview publication without a provider call or a review change."""
    manifest = validate_evidence(execution_id, profile=profile)
    return prepare_publication(manifest, destination)


def publish_evidence(
    execution_id: str,
    destination: str,
    *,
    token: str,
    confirmed: bool,
    qa_review: str,
    now: datetime,
    issue_key: str = "",
    profile: str | None = None,
) -> PublicationPreview:
    """Publish after an explicit review value and a matching approval."""
    selected, workspace, store, record = _loaded(execution_id, profile, None)
    manifest = validate_evidence(execution_id, profile=profile)
    policy = validate_policy(
        require_policy(load_policies(workspace), manifest.policy_id)
    )
    return publish_manifest(
        manifest=manifest,
        policy=policy,
        record=record,
        config=load_config(),
        profile_id=selected,
        store=store,
        ledger=publication_ledger(),
        destination=destination,
        token=token,
        confirmed=confirmed,
        qa_review=qa_review,
        now=now,
        issue_key=issue_key,
    )


def _store_reports(
    workspace: Path, store: ExecutionStore, manifest: EvidenceManifest
) -> None:
    styles = (template_dir() / "styles.css").read_bytes()
    files = {
        "report.html": render_report(manifest).encode("utf-8"),
        "summary.html": render_summary(manifest).encode("utf-8"),
        "styles.css": styles,
    }
    artifacts = tuple(artifact_for(name, content) for name, content in files.items())
    complete = manifest.model_copy(update={"artifacts": artifacts})
    document = json.dumps(
        complete.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    files["report.json"] = document
    complete = complete.model_copy(
        update={"artifacts": artifacts + (artifact_for("report.json", document),)}
    )
    stored = ArtifactStore(workspace)
    for name, content in files.items():
        stored.write(manifest.execution_id, name, content)
    store.save_manifest(
        complete.profile_id, complete.execution_id, complete.model_dump_json()
    )


def _loaded(
    execution_id: str, profile: str | None, config: HubConfig | None
) -> tuple[str, Path, ExecutionStore, ExecutionRecord]:
    selected_config = config or load_config()
    selected, workspace = workspace_for(selected_config, profile)
    store = ExecutionStore(resolve_execution_path())
    record = store.get(selected, execution_id)
    return selected, workspace, store, record
