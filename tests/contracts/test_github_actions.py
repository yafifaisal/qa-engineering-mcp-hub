"""Offline GitHub Actions contract."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx
import yaml
from fastmcp import Client

from qa_mcp_hub.adapters.cicd.base import parameter_digest
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
from qa_mcp_hub.core.enums import OperationStatus, ProviderCategory
from qa_mcp_hub.core.errors import (
    HubError,
    ProviderRequestError,
    UnsupportedCapabilityError,
)
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.mcp.tools.cicd import (
    clear_ci_session,
    dispatch_registered_trigger,
    get_pipeline_artifacts_tool,
    get_pipeline_status_tool,
    install_ci_session,
    list_pipeline_runs_tool,
    prepare_pipeline_trigger_tool,
)
from qa_mcp_hub.providers.registry import CicdContractStub, discover_capabilities
from qa_mcp_hub.server import mcp

SHA = "a" * 40
OTHER = "b" * 40
CI_VALUE = "qa_mcp_ci_token_value"
APPROVAL = "qa_mcp_approval_token"
NOW = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)
_RUNS = "https://api.github.com/repos/acme/billing/actions/workflows/ci.yml/runs"


def _workspace(
    path: Path, *, trigger: bool = False, mutations: bool = False
) -> HubConfig:
    path.mkdir(parents=True, exist_ok=True)
    (path / "ci").mkdir(exist_ok=True)
    job: dict[str, object] = {
        "id": "billing",
        "provider": "github_actions",
        "connection_id": "ci",
        "repository": "acme/billing",
        "workflow": "ci.yml",
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
            ),
            "beta": ProfileConfig(workspace_id="ws"),
        },
        workspaces=(QAWorkspaceReference(id="ws", path=str(path)),),
        connections=(
            ConnectionConfig(
                id="ci",
                provider=ProviderKind.github_actions,
                deployment=DeploymentKind.CLOUD,
            ),
        ),
    )


def _bind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, config: HubConfig) -> None:
    monkeypatch.setattr("qa_mcp_hub.mcp.tools.cicd.load_config", lambda: config)
    monkeypatch.setenv("QA_MCP_EXECUTION_PATH", str(tmp_path / "runs.sqlite"))
    install_ci_session(lambda: (httpx.Client(), CI_VALUE))


def _run(number: int, conclusion: str, revision: str, title: str) -> dict[str, object]:
    return {
        "id": number,
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": revision,
        "html_url": f"https://github.com/acme/billing/actions/runs/{number}",
        "display_title": title,
    }


def test_states_revision_correlation_and_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path / "ws")
    _bind(monkeypatch, tmp_path, config)
    try:
        with respx.mock:
            respx.get(_RUNS).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "workflow_runs": [
                            _run(10, "success", SHA, "QA-12 ship OTHER-9"),
                            _run(11, "failure", OTHER, "failed"),
                            _run(12, "cancelled", SHA, "QA-12 stop"),
                        ]
                    },
                )
            )
            page = list_pipeline_runs_tool("billing", revision=SHA)
    finally:
        clear_ci_session()
    assert [item.run_id for item in page.runs] == ["10", "12"]
    assert [item.pipeline_status.value for item in page.runs] == [
        "SUCCEEDED",
        "CANCELLED",
    ]
    assert {item.assertion_status for item in page.runs} == {"NOT_OBSERVED"}
    assert page.runs[0].suite_ids == ("billing-bruno",)
    assert page.runs[0].issue_keys == ("QA-12",)
    assert page.runs[0].revision == SHA
    database = sqlite3.connect(tmp_path / "runs.sqlite")
    assert database.execute("SELECT COUNT(*) FROM runs").fetchone() == (0,)
    rows = database.execute(
        "SELECT pipeline_status FROM ci_observations WHERE profile_id = ?",
        ("alpha",),
    ).fetchall()
    assert {row[0] for row in rows} == {"SUCCEEDED", "CANCELLED"}
    hidden = database.execute(
        "SELECT COUNT(*) FROM ci_observations WHERE profile_id = ?",
        ("beta",),
    ).fetchone()
    database.close()
    assert hidden == (0,)


def test_permission_timeout_and_rate_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path / "ws")
    _bind(monkeypatch, tmp_path, config)
    try:
        with respx.mock:
            respx.get(_RUNS).mock(return_value=httpx.Response(403, text=CI_VALUE))
            with pytest.raises(ProviderRequestError) as denied:
                list_pipeline_runs_tool("billing")
        assert denied.value.code == "permission_denied"
        assert CI_VALUE not in denied.value.message
        with respx.mock:
            respx.get(_RUNS).mock(side_effect=httpx.TimeoutException("timed out"))
            with pytest.raises(ProviderRequestError) as timed:
                list_pipeline_runs_tool("billing")
        assert timed.value.code == "provider_unreachable"
        with respx.mock:
            route = respx.get(_RUNS).mock(return_value=httpx.Response(429))
            with pytest.raises(ProviderRequestError) as limited:
                list_pipeline_runs_tool("billing")
        assert limited.value.code == "rate_limited"
        assert route.call_count == 3
    finally:
        clear_ci_session()


def test_expired_artifact_and_redacted_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path / "ws")
    _bind(monkeypatch, tmp_path, config)
    log = ("x" * 2500) + f" password=hunter2 Bearer {CI_VALUE}"
    try:
        with respx.mock:
            respx.get("https://api.github.com/repos/acme/billing/actions/runs/10").mock(
                return_value=httpx.Response(200, json=_run(10, "success", SHA, "QA-12"))
            )
            respx.get(
                "https://api.github.com/repos/acme/billing/actions/runs/10/jobs"
            ).mock(
                return_value=httpx.Response(
                    200, json={"jobs": [{"id": 7, "name": "test"}]}
                )
            )
            respx.get(
                "https://api.github.com/repos/acme/billing/actions/jobs/7/logs"
            ).mock(return_value=httpx.Response(200, text=log))
            download = respx.get(
                "https://api.github.com/repos/acme/billing/actions/artifacts/1/zip"
            ).mock(return_value=httpx.Response(200, content=b"secret-bytes"))
            respx.get(
                "https://api.github.com/repos/acme/billing/actions/runs/10/artifacts"
            ).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "artifacts": [
                            {
                                "name": "junit",
                                "expired": True,
                                "size_in_bytes": 4,
                                "archive_download_url": (
                                    "https://api.github.com/repos/acme/billing/"
                                    "actions/artifacts/1/zip"
                                ),
                                "expires_at": "2020-01-01T00:00:00Z",
                            }
                        ]
                    },
                )
            )
            status = get_pipeline_status_tool("billing", "10")
            artifacts = get_pipeline_artifacts_tool("billing", "10")
        assert download.call_count == 0
    finally:
        clear_ci_session()
    assert status.runs[0].log_truncated is True
    assert status.runs[0].log_incomplete is True
    assert "hunter2" not in status.runs[0].log_excerpt
    assert CI_VALUE not in status.runs[0].log_excerpt
    assert artifacts.runs[0].artifacts[0].expired is True
    assert artifacts.runs[0].artifacts[0].available is False
    assert artifacts.runs[0].assertion_status == "NOT_OBSERVED"


def test_trigger_stays_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path / "ws")
    _bind(monkeypatch, tmp_path, config)
    try:
        with respx.mock:
            route = respx.post(
                "https://api.github.com/repos/acme/billing/actions/workflows/ci.yml/dispatches"
            ).mock(return_value=httpx.Response(204))
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
    assert preview.executed is False
    assert preview.trigger_enabled is False
    assert preview.reason == "trigger_disabled"
    assert receipt.executed is False
    with pytest.raises(HubError) as invalid:
        prepare_pipeline_trigger_tool("billing", {"environment": "prod"})
    assert invalid.value.code == "parameter_rejected"


def test_approved_trigger_is_single_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path / "ws", trigger=True, mutations=True)
    _bind(monkeypatch, tmp_path, config)
    ledger = ApprovalLedger()
    digest = parameter_digest({"environment": "local"})
    ledger.issue(
        ApprovalGrant(
            token=APPROVAL,
            job_id="billing",
            parameter_digest=digest,
            expires_at=datetime(2026, 10, 18, 7, 0, tzinfo=UTC),
        )
    )
    try:
        with respx.mock:
            route = respx.post(
                "https://api.github.com/repos/acme/billing/actions/workflows/ci.yml/dispatches"
            ).mock(return_value=httpx.Response(204))
            preview = prepare_pipeline_trigger_tool("billing", {"environment": "local"})
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
        assert preview.executed is False
        assert route.call_count == 1
        body = json.loads(route.calls[0].request.content.decode("utf-8"))
        assert body == {"ref": "main", "inputs": {"environment": "local"}}
    finally:
        clear_ci_session()
    assert receipt.executed is True
    assert receipt.reason == "dispatch_accepted"
    assert receipt.provider_status == 204


def test_trigger_failure_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path / "ws", trigger=True, mutations=True)
    _bind(monkeypatch, tmp_path, config)
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
            route = respx.post(
                "https://api.github.com/repos/acme/billing/actions/workflows/ci.yml/dispatches"
            ).mock(return_value=httpx.Response(503))
            with pytest.raises(ProviderRequestError) as caught:
                dispatch_registered_trigger(
                    "billing",
                    parameters={"environment": "local"},
                    ledger=ledger,
                    token=APPROVAL,
                    confirmed=True,
                    now=NOW,
                )
        assert caught.value.code == "rate_limited"
        assert route.call_count == 1
    finally:
        clear_ci_session()


def test_generic_port_does_not_advertise_a_trigger() -> None:
    capabilities = discover_capabilities("github_actions")
    assert [item.name for item in capabilities] == ["read_pipeline"]
    assert capabilities[0].status is OperationStatus.not_implemented
    stub = CicdContractStub(ProviderKind.github_actions, ProviderCategory.cicd)
    with pytest.raises(UnsupportedCapabilityError):
        stub.list_pipeline_runs(object(), object())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_mcp_lists_inspection_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _workspace(tmp_path / "ws")
    _bind(monkeypatch, tmp_path, config)
    try:
        with respx.mock:
            respx.get(_RUNS).mock(
                return_value=httpx.Response(
                    200, json={"workflow_runs": [_run(10, "success", SHA, "QA-12")]}
                )
            )
            async with Client(mcp) as client:
                names = {tool.name for tool in await client.list_tools()}
                assert {
                    "list_pipeline_runs",
                    "get_pipeline_status",
                    "get_pipeline_artifacts",
                    "prepare_pipeline_trigger",
                } <= names
                assert "dispatch_registered_trigger" not in names
                result = await client.call_tool(
                    "list_pipeline_runs", {"job_id": "billing", "revision": SHA}
                )
    finally:
        clear_ci_session()
    payload = result.structured_content
    assert payload is not None
    assert payload["runs"][0]["pipeline_status"] == "SUCCEEDED"
    assert payload["runs"][0]["assertion_status"] == "NOT_OBSERVED"
