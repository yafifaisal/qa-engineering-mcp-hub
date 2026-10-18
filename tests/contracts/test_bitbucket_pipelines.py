"""Offline Bitbucket Pipelines contract."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx
import yaml

from qa_mcp_hub.adapters.cicd.base import PipelineState
from qa_mcp_hub.config.models import (
    CURRENT_SCHEMA_VERSION,
    ConnectionConfig,
    DeploymentKind,
    HubConfig,
    ProfileConfig,
    QAWorkspaceReference,
)
from qa_mcp_hub.core.approvals import ApprovalLedger
from qa_mcp_hub.core.errors import ProviderRequestError
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.mcp.tools.cicd import (
    clear_ci_session,
    dispatch_registered_trigger,
    get_pipeline_status_tool,
    install_ci_session,
    list_pipeline_runs_tool,
    prepare_pipeline_trigger_tool,
)

SHA = "c" * 40
OTHER = "d" * 40
CI_VALUE = "qa_mcp_ci_token_value"
APPROVAL = "qa_mcp_approval_token"
_PIPELINES = "https://api.bitbucket.org/2.0/repositories/acme/billing/pipelines"
NOW = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)


def _config(path: Path) -> HubConfig:
    path.mkdir(parents=True, exist_ok=True)
    (path / "ci").mkdir(exist_ok=True)
    yaml.safe_dump(
        {
            "schema_version": 1,
            "implementation_status": "IMPLEMENTED",
            "jobs": [
                {
                    "id": "billing",
                    "provider": "bitbucket_pipelines",
                    "connection_id": "ci",
                    "repository": "acme/billing",
                    "enabled": True,
                    "allow_trigger": False,
                }
            ],
        },
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
            "alpha": ProfileConfig(workspace_id="ws", connection_ids=("ci",)),
        },
        workspaces=(QAWorkspaceReference(id="ws", path=str(path)),),
        connections=(
            ConnectionConfig(
                id="ci",
                provider=ProviderKind.bitbucket_pipelines,
                deployment=DeploymentKind.CLOUD,
            ),
        ),
    )


def _pipeline(result: str, revision: str, message: str) -> dict[str, object]:
    return {
        "uuid": "{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}",
        "state": {"name": "COMPLETED", "result": {"name": result}},
        "target": {"commit": {"hash": revision, "message": message}},
        "links": {
            "self": {"href": f"{_PIPELINES}/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}
        },
    }


def _bind(monkeypatch: pytest.MonkeyPatch, config: HubConfig) -> None:
    monkeypatch.setattr("qa_mcp_hub.mcp.tools.cicd.load_config", lambda: config)
    install_ci_session(lambda: (httpx.Client(), CI_VALUE))


def test_states_and_exact_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, _config(tmp_path / "ws"))
    try:
        with respx.mock:
            respx.get(_PIPELINES).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "values": [
                            _pipeline("SUCCESSFUL", SHA, "QA-4 done"),
                            _pipeline("FAILED", OTHER, "QA-4 fail"),
                            {
                                "uuid": "{bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb}",
                                "state": {
                                    "name": "COMPLETED",
                                    "result": {"name": "STOPPED"},
                                },
                                "target": {
                                    "commit": {"hash": SHA, "message": "QA-4 stop"}
                                },
                            },
                        ]
                    },
                )
            )
            page = list_pipeline_runs_tool("billing", revision=SHA)
    finally:
        clear_ci_session()
    assert [item.pipeline_status for item in page.runs] == [
        PipelineState.SUCCEEDED,
        PipelineState.CANCELLED,
    ]
    assert {item.assertion_status for item in page.runs} == {"NOT_OBSERVED"}
    assert page.runs[0].revision == SHA
    assert page.runs[0].issue_keys == ("QA-4",)
    assert page.runs[0].suite_ids == ("billing-bruno",)
    assert all(item.revision == SHA for item in page.runs)


def test_pagination_permission_and_rate_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, _config(tmp_path / "ws"))
    try:
        with respx.mock:
            respx.get(_PIPELINES).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "values": [_pipeline("SUCCESSFUL", SHA, "QA-4")],
                        "next": f"{_PIPELINES}?page=2",
                    },
                )
            )
            respx.get(f"{_PIPELINES}?page=2").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "values": [_pipeline("FAILED", SHA, "QA-4")],
                        "next": f"{_PIPELINES}?page=3",
                    },
                )
            )
            page = list_pipeline_runs_tool("billing", revision=SHA)
        assert page.truncated is True
        assert len(page.runs) == 2
        with respx.mock:
            respx.get(_PIPELINES).mock(return_value=httpx.Response(403, text=CI_VALUE))
            with pytest.raises(ProviderRequestError) as denied:
                list_pipeline_runs_tool("billing")
        assert denied.value.code == "permission_denied"
        assert CI_VALUE not in denied.value.message
        with respx.mock:
            route = respx.get(_PIPELINES).mock(return_value=httpx.Response(429))
            with pytest.raises(ProviderRequestError) as limited:
                list_pipeline_runs_tool("billing")
        assert limited.value.code == "rate_limited"
        assert route.call_count == 3
    finally:
        clear_ci_session()


def test_expired_artifact_and_redacted_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, _config(tmp_path / "ws"))
    run_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    try:
        with respx.mock:
            respx.get(f"{_PIPELINES}/{run_id}").mock(
                return_value=httpx.Response(
                    200, json=_pipeline("SUCCESSFUL", SHA, "QA-4")
                )
            )
            respx.get(f"{_PIPELINES}/{run_id}/steps/").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "values": [
                            {
                                "uuid": "step-1",
                                "artifacts": [
                                    {"name": "report", "expired": True},
                                ],
                            }
                        ]
                    },
                )
            )
            respx.get(f"{_PIPELINES}/{run_id}/steps/step-1/log").mock(
                return_value=httpx.Response(
                    200, text=f"password=hunter2 Bearer {CI_VALUE} " + ("y" * 2100)
                )
            )
            download = respx.get(f"{_PIPELINES}/{run_id}/artifacts/report").mock(
                return_value=httpx.Response(200, content=b"hidden")
            )
            status = get_pipeline_status_tool("billing", run_id)
        assert download.call_count == 0
    finally:
        clear_ci_session()
    assert status.runs[0].artifacts[0].expired is True
    assert status.runs[0].artifacts[0].available is False
    assert status.runs[0].log_truncated is True
    assert "hunter2" not in status.runs[0].log_excerpt
    assert CI_VALUE not in status.runs[0].log_excerpt
    assert status.runs[0].assertion_status == "NOT_OBSERVED"


def test_trigger_is_not_called(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bind(monkeypatch, _config(tmp_path / "ws"))
    try:
        with respx.mock:
            route = respx.post(_PIPELINES + "/").mock(return_value=httpx.Response(201))
            preview = prepare_pipeline_trigger_tool("billing")
            receipt = dispatch_registered_trigger(
                "billing",
                parameters=None,
                ledger=ApprovalLedger(),
                token=APPROVAL,
                confirmed=True,
                now=NOW,
            )
        assert route.call_count == 0
    finally:
        clear_ci_session()
    assert preview.executed is False
    assert preview.reason == "trigger_disabled"
    assert receipt.executed is False
