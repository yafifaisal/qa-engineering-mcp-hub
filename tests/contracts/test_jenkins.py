"""Offline Jenkins contract."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx
import yaml

from qa_mcp_hub.adapters.cicd.base import parameter_digest
from qa_mcp_hub.adapters.cicd.jenkins import JenkinsAdapter
from qa_mcp_hub.adapters.git.base import ReadOnlyClient
from qa_mcp_hub.config.models import (
    CURRENT_SCHEMA_VERSION,
    ConnectionConfig,
    DeploymentKind,
    ExecutionOverrides,
    HubConfig,
    ProfileConfig,
    QAWorkspaceReference,
)
from qa_mcp_hub.core.approvals import ApprovalGrant, ApprovalLedger
from qa_mcp_hub.core.errors import HubError, ProviderRequestError
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.mcp.tools.cicd import (
    clear_ci_session,
    dispatch_registered_trigger,
    get_pipeline_status_tool,
    install_ci_session,
    list_pipeline_runs_tool,
    prepare_pipeline_trigger_tool,
)

SHA = "e" * 40
OTHER = "f" * 40
CI_VALUE = "qa_mcp_ci_token_value"
APPROVAL = "qa_mcp_approval_token"
NOW = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)
_JOB = "https://jenkins.example.com/job/billing"


def _config(path: Path, *, trigger: bool = False, mutations: bool = False) -> HubConfig:
    path.mkdir(parents=True, exist_ok=True)
    (path / "ci").mkdir(exist_ok=True)
    job: dict[str, object] = {
        "id": "billing",
        "provider": "jenkins",
        "connection_id": "ci",
        "repository": "billing",
        "enabled": True,
        "allow_trigger": trigger,
        "parameters": [{"name": "environment", "allowed_values": ["local"]}],
    }
    if trigger:
        job["ref"] = "main"
    yaml.safe_dump(
        {"schema_version": 1, "implementation_status": "IMPLEMENTED", "jobs": [job]},
        (path / "ci" / "registered-jobs.yaml").open("w", encoding="utf-8"),
        sort_keys=False,
    )
    yaml.safe_dump(
        {
            "schema_version": 1,
            "mappings": [
                {
                    "job_id": "billing",
                    "suite_ids": ["billing-bruno"],
                    "issue_pattern": r"QA-\d+",
                }
            ],
        },
        (path / "ci" / "pipeline-mappings.yaml").open("w", encoding="utf-8"),
        sort_keys=False,
    )
    return HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={
            "alpha": ProfileConfig(
                workspace_id="ws",
                connection_ids=("ci",),
                execution=ExecutionOverrides(allow_mutations=mutations),
            )
        },
        workspaces=(QAWorkspaceReference(id="ws", path=str(path)),),
        connections=(
            ConnectionConfig(
                id="ci",
                provider=ProviderKind.jenkins,
                deployment=DeploymentKind.SELF_MANAGED,
                base_url="https://jenkins.example.com",
                account="qa-bot",
            ),
        ),
    )


def _build(
    number: int, result: str | None, revision: str, message: str
) -> dict[str, object]:
    return {
        "number": number,
        "result": result,
        "building": False,
        "url": f"{_JOB}/{number}/",
        "changeSet": {"items": [{"commitId": revision, "msg": message}]},
    }


def _bind(monkeypatch: pytest.MonkeyPatch, config: HubConfig) -> None:
    monkeypatch.setattr("qa_mcp_hub.mcp.tools.cicd.load_config", lambda: config)
    install_ci_session(lambda: (httpx.Client(), CI_VALUE))


def test_build_states_and_exact_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, _config(tmp_path / "ws"))
    try:
        with respx.mock:
            respx.get(f"{_JOB}/api/json").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "builds": [
                            _build(4, "SUCCESS", SHA, "QA-8 pass"),
                            _build(5, "FAILURE", OTHER, "QA-8 fail"),
                            _build(6, "ABORTED", SHA, "QA-8 stop"),
                            _build(7, "UNSTABLE", SHA, "QA-8 flake"),
                        ]
                    },
                )
            )
            page = list_pipeline_runs_tool("billing", revision=SHA)
    finally:
        clear_ci_session()
    assert [item.pipeline_status.value for item in page.runs] == [
        "SUCCEEDED",
        "CANCELLED",
        "FAILED",
    ]
    assert {item.assertion_status for item in page.runs} == {"NOT_OBSERVED"}
    assert page.runs[0].issue_keys == ("QA-8",)
    assert page.runs[0].suite_ids == ("billing-bruno",)
    assert all(item.revision == SHA for item in page.runs)


def test_invalid_job_name_is_rejected() -> None:
    client = httpx.Client()
    reader = ReadOnlyClient(client, allowed_host="jenkins.example.com")
    with pytest.raises(ProviderRequestError) as invalid:
        JenkinsAdapter(
            reader,
            account="qa-bot",
            token=CI_VALUE,
            base_url="https://jenkins.example.com",
            job_name="../secret",
        )
    client.close()
    assert invalid.value.code == "invalid_repository"


def test_status_permission_and_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, _config(tmp_path / "ws"))
    try:
        with respx.mock:
            respx.get(f"{_JOB}/api/json").mock(
                return_value=httpx.Response(403, text=CI_VALUE)
            )
            with pytest.raises(ProviderRequestError) as denied:
                list_pipeline_runs_tool("billing")
        assert denied.value.code == "permission_denied"
        assert CI_VALUE not in denied.value.message
        with respx.mock:
            respx.get(f"{_JOB}/api/json").mock(
                side_effect=httpx.TimeoutException("timed out")
            )
            with pytest.raises(ProviderRequestError) as timed:
                list_pipeline_runs_tool("billing")
        assert timed.value.code == "provider_unreachable"
    finally:
        clear_ci_session()


def test_expired_artifact_and_redacted_console(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, _config(tmp_path / "ws"))
    try:
        with respx.mock:
            respx.get(f"{_JOB}/9/api/json").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        **_build(9, "SUCCESS", SHA, "QA-8"),
                        "artifacts": [{"fileName": "junit.xml", "expired": True}],
                    },
                )
            )
            respx.get(f"{_JOB}/9/consoleText").mock(
                return_value=httpx.Response(
                    200, text=f"password=hunter2 Bearer {CI_VALUE} " + ("z" * 2100)
                )
            )
            download = respx.get(f"{_JOB}/9/artifact/junit.xml").mock(
                return_value=httpx.Response(200, content=b"hidden")
            )
            status = get_pipeline_status_tool("billing", "9")
        assert download.call_count == 0
    finally:
        clear_ci_session()
    assert status.runs[0].artifacts[0].expired is True
    assert status.runs[0].artifacts[0].available is False
    assert status.runs[0].log_truncated is True
    assert "hunter2" not in status.runs[0].log_excerpt
    assert CI_VALUE not in status.runs[0].log_excerpt


def test_parameters_and_trigger_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, _config(tmp_path / "ws"))
    try:
        with respx.mock:
            route = respx.post(f"{_JOB}/buildWithParameters").mock(
                return_value=httpx.Response(201)
            )
            with pytest.raises(HubError) as invalid:
                prepare_pipeline_trigger_tool("billing", {"environment": "prod"})
            preview = prepare_pipeline_trigger_tool("billing", {"environment": "local"})
            receipt = dispatch_registered_trigger(
                "billing",
                parameters={"environment": "local"},
                ledger=ApprovalLedger(),
                token=APPROVAL,
                confirmed=True,
                now=NOW,
            )
        assert route.call_count == 0
    finally:
        clear_ci_session()
    assert invalid.value.code == "parameter_rejected"
    assert preview.executed is False
    assert receipt.executed is False
    assert receipt.reason == "trigger_disabled"


def test_approved_trigger_posts_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, _config(tmp_path / "ws", trigger=True, mutations=True))
    ledger = ApprovalLedger()
    ledger.issue(
        ApprovalGrant(
            token=APPROVAL,
            job_id="billing",
            parameter_digest=parameter_digest({"environment": "local"}),
            expires_at=datetime(2026, 10, 18, 7, 0, tzinfo=UTC),
        )
    )
    try:
        with respx.mock:
            respx.get("https://jenkins.example.com/crumbIssuer/api/json").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "crumb": "qa_mcp_crumb_value",
                        "crumbRequestField": "Jenkins-Crumb",
                    },
                )
            )
            route = respx.post(f"{_JOB}/buildWithParameters").mock(
                return_value=httpx.Response(201)
            )
            receipt = dispatch_registered_trigger(
                "billing",
                parameters={"environment": "local"},
                ledger=ledger,
                token=APPROVAL,
                confirmed=True,
                now=NOW,
            )
            with pytest.raises(HubError):
                dispatch_registered_trigger(
                    "billing",
                    parameters={"environment": "local"},
                    ledger=ledger,
                    token=APPROVAL,
                    confirmed=True,
                    now=NOW,
                )
        assert route.call_count == 1
        assert route.calls[0].request.headers["Jenkins-Crumb"] == "qa_mcp_crumb_value"
        assert route.calls[0].request.content == b"environment=local"
    finally:
        clear_ci_session()
    assert receipt.executed is True
    assert receipt.reason == "dispatch_accepted"
