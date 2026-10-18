"""Evidence publication stays approval-gated and is not retried."""

import shutil
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from qa_mcp_hub.config.models import (
    CURRENT_SCHEMA_VERSION,
    ConnectionConfig,
    DeploymentKind,
    ExecutionOverrides,
    HubConfig,
    ProfileConfig,
    QAWorkspaceReference,
)
from qa_mcp_hub.core.approvals import ApprovalGrant
from qa_mcp_hub.core.errors import ProviderRequestError
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.evidence.manifest import manifest_digest
from qa_mcp_hub.evidence.publisher import (
    clear_publication_session,
    install_publication_session,
)
from qa_mcp_hub.evidence.service import (
    generate_evidence,
    prepare_evidence,
    publication_ledger,
    publish_evidence,
    reset_publication_ledger,
)
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.workflows.models import (
    ApiOnlyEvidence,
    ExecutionRecord,
    ExecutionStatus,
    StepEvidence,
)

NOW = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 18, 7, 0, tzinfo=UTC)
APPROVAL = "qa_mcp_approval_token"
REVISION = "b" * 40


def test_preview_does_not_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(tmp_path, monkeypatch, publish=False)
    generate_evidence("run-1", "api-only")
    preview = prepare_evidence("run-1", "jira")
    assert preview.executed is False
    assert preview.reason == "approval_required"


def test_denied_policy_and_duplicate_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(tmp_path, monkeypatch, publish=False)
    manifest = generate_evidence("run-1", "api-only")
    denied = publish_evidence(
        "run-1",
        "jira",
        token=APPROVAL,
        confirmed=True,
        qa_review="APPROVED",
        now=NOW,
        issue_key="QA-14",
    )
    assert denied.executed is False
    assert denied.reason == "publication_disabled"
    _issue(manifest_digest(manifest))
    first = publish_evidence(
        "run-1",
        "local",
        token=APPROVAL,
        confirmed=True,
        qa_review="APPROVED",
        now=NOW,
    )
    second = publish_evidence(
        "run-1",
        "local",
        token=APPROVAL,
        confirmed=True,
        qa_review="APPROVED",
        now=NOW,
    )
    assert first.executed is True
    assert second.reason == "already_published"
    assert second.executed is False


def test_failed_post_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(tmp_path, monkeypatch, publish=True)
    manifest = generate_evidence("run-1", "api-only")
    _issue(manifest_digest(manifest))
    install_publication_session(lambda: (httpx.Client(), "qa_mcp_ci_token_value"))
    try:
        with respx.mock:
            route = respx.post(
                "https://xray.cloud.getxray.app/api/v2/import/execution"
            ).mock(return_value=httpx.Response(403, text="hidden"))
            with pytest.raises(ProviderRequestError):
                publish_evidence(
                    "run-1",
                    "xray",
                    token=APPROVAL,
                    confirmed=True,
                    qa_review="APPROVED",
                    now=NOW,
                )
            again = publish_evidence(
                "run-1",
                "xray",
                token=APPROVAL,
                confirmed=True,
                qa_review="APPROVED",
                now=NOW,
            )
        assert route.call_count == 1
    finally:
        clear_publication_session()
    assert again.reason == "publication_incomplete"
    assert "hidden" not in again.reason


def _prepare(path: Path, monkeypatch: pytest.MonkeyPatch, *, publish: bool) -> None:
    reset_publication_ledger()
    workspace = path / "ws"
    source = Path("templates/qa-workspace/evidence-policies")
    target = workspace / "evidence-policies"
    target.mkdir(parents=True)
    text = (source / "api-only.yaml").read_text(encoding="utf-8")
    if publish:
        text += "external_publication: approval_required\n"
    (target / "api-only.yaml").write_text(text, encoding="utf-8")
    for name in ("api-database.yaml", "full-e2e.yaml", "security-redaction.yaml"):
        shutil.copy(source / name, target / name)
    monkeypatch.setenv("QA_MCP_EXECUTION_PATH", str(path / "runs.sqlite"))
    config = HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={
            "alpha": ProfileConfig(
                workspace_id="ws",
                connection_ids=("xray",),
                execution=ExecutionOverrides(allow_mutations=True),
            )
        },
        workspaces=(QAWorkspaceReference(id="ws", path=str(workspace)),),
        connections=(
            ConnectionConfig(
                id="xray",
                provider=ProviderKind.xray,
                deployment=DeploymentKind.CLOUD,
                base_url="https://xray.cloud.getxray.app",
            ),
        ),
    )
    monkeypatch.setattr("qa_mcp_hub.evidence.service.load_config", lambda: config)
    ExecutionStore(path / "runs.sqlite").save(_record())


def _issue(digest: str) -> None:
    publication_ledger().issue(
        ApprovalGrant(
            token=APPROVAL,
            action="evidence_publication",
            job_id="run-1",
            parameter_digest=digest,
            expires_at=LATER,
        )
    )


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
        excerpt="QA-14",
        step_results=(
            StepEvidence(
                step_id="api",
                kind="api_suite",
                target="QA-14",
                status=ExecutionStatus.passed,
                executed=True,
                verified=True,
                reason="observed",
                evidence_ref="step-ref",
            ),
        ),
    )
