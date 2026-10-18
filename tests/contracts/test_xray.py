"""Offline Xray Cloud and Data Center contract."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx
import yaml

from qa_mcp_hub.adapters.git.base import ReadOnlyClient
from qa_mcp_hub.adapters.test_management.base import (
    ColumnMap,
    FieldMapping,
    content_digest,
)
from qa_mcp_hub.adapters.test_management.xray import (
    cases_from_cloud,
    cases_from_data_center,
    edition_endpoint,
    fetch_cloud,
)
from qa_mcp_hub.config.models import (
    CURRENT_SCHEMA_VERSION,
    ExecutionOverrides,
    HubConfig,
    ProfileConfig,
    QAWorkspaceReference,
)
from qa_mcp_hub.core.approvals import ApprovalGrant, ApprovalLedger
from qa_mcp_hub.core.errors import HubError, ProviderRequestError
from qa_mcp_hub.mcp.tools.test_management import (
    clear_test_session,
    dispatch_result_publication,
    install_test_session,
    prepare_result_publication_tool,
    reset_publications,
)

NOW = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)
APPROVAL = "qa_mcp_approval_token"


def _mapping(*, publish: bool = False) -> FieldMapping:
    return FieldMapping(
        id="billing",
        provider="xray",
        edition="cloud",
        format="api",
        allow_publish=publish,
        step_format="blocks",
        columns=ColumnMap(
            source_id="key",
            test_case="summary",
            steps="steps",
            expected_result="expected",
            priority="priority",
            scenario="scenario",
            version="version",
        ),
        priorities={"High": "High", "Low": "Low"},
        results={"Untested": "Untested", "Passed": "Passed"},
    )


def _cloud(priority: str = "High", key: str = "QA-1") -> dict[str, object]:
    return {
        "data": {
            "getTests": {
                "results": [
                    {
                        "issueId": "100",
                        "jira": {"key": key, "summary": "Pay an order"},
                        "priority": {"name": priority},
                        "folder": "Billing",
                        "steps": [
                            {"action": "Open the page", "result": "Form shown"},
                            {
                                "action": "Enter the amount",
                                "result": "Payment accepted",
                            },
                        ],
                    }
                ]
            }
        }
    }


def test_cloud_and_data_center_share_canonical_fields() -> None:
    mapping = _mapping()
    cloud = cases_from_cloud(_cloud(), mapping)[0]
    center = cases_from_data_center(
        {
            "tests": [
                {
                    "key": "QA-1",
                    "summary": "Pay an order",
                    "priority": "High",
                    "definition": "Checkout",
                    "version": "3",
                    "folder": "Billing",
                    "steps": [
                        {"step": "Open the page", "result": "Form shown"},
                        {"step": "Enter the amount", "result": "Payment accepted"},
                    ],
                }
            ]
        },
        _mapping().model_copy(update={"edition": "data_center"}),
    )[0]
    assert cloud.steps == ("Open the page", "Enter the amount")
    assert cloud.expected_result == "Form shown\n---\nPayment accepted"
    assert center.steps == cloud.steps
    assert cloud.provider == "xray"
    assert cloud.edition == "cloud"
    assert center.edition == "data_center"
    assert {item.name for item in cloud.preserved_fields} == {"folder"}
    assert edition_endpoint("cloud", "https://jira.example.com") != edition_endpoint(
        "data_center", "https://jira.example.com"
    )


def test_unknown_priority_missing_field_and_duplicates() -> None:
    mapping = _mapping()
    with pytest.raises(HubError) as priority:
        cases_from_cloud(_cloud(priority="Urgent"), mapping)
    assert priority.value.code == "mapping_rejected"
    payload = _cloud()
    results = payload["data"]["getTests"]["results"]  # type: ignore[index]
    results[0]["jira"]["summary"] = ""  # type: ignore[index]
    with pytest.raises(HubError) as missing:
        cases_from_cloud(payload, mapping)
    assert missing.value.code == "missing_field"
    duplicated = _cloud()
    page = duplicated["data"]["getTests"]["results"]  # type: ignore[index]
    page.append(page[0])
    with pytest.raises(HubError) as duplicate:
        cases_from_cloud(duplicated, mapping)
    assert duplicate.value.code == "duplicate_case"


def test_permission_failure_is_not_a_case() -> None:
    client = httpx.Client()
    reader = ReadOnlyClient(client, allowed_host="xray.cloud.getxray.app")
    try:
        with respx.mock:
            route = respx.post("https://xray.cloud.getxray.app/api/v2/graphql").mock(
                return_value=httpx.Response(403, text="qa_mcp_hidden")
            )
            with pytest.raises(ProviderRequestError) as denied:
                fetch_cloud(reader, "qa_mcp_ci_token_value")
        assert denied.value.code == "permission_denied"
        assert "qa_mcp_hidden" not in denied.value.message
        assert route.call_count == 1
    finally:
        client.close()


def _config(path: Path, *, mutations: bool) -> HubConfig:
    path.mkdir(parents=True, exist_ok=True)
    (path / "test-management" / "mappings").mkdir(parents=True, exist_ok=True)
    return HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={
            "alpha": ProfileConfig(
                workspace_id="ws",
                execution=ExecutionOverrides(allow_mutations=mutations),
            )
        },
        workspaces=(QAWorkspaceReference(id="ws", path=str(path)),),
    )


def _write_mapping(path: Path, *, publish: bool) -> None:
    target = path / "test-management" / "mappings"
    target.mkdir(parents=True, exist_ok=True)
    yaml.safe_dump(
        _mapping(publish=publish).model_dump(mode="json"),
        (target / "billing.yaml").open("w", encoding="utf-8"),
        sort_keys=False,
    )


def test_publication_stays_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _write_mapping(workspace, publish=False)
    monkeypatch.setattr(
        "qa_mcp_hub.mcp.tools.test_management.load_config",
        lambda: _config(workspace, mutations=True),
    )
    reset_publications()
    install_test_session(lambda: (httpx.Client(), "qa_mcp_ci_token_value", ()))
    try:
        with respx.mock:
            route = respx.post(
                "https://xray.cloud.getxray.app/api/v2/import/execution"
            ).mock(return_value=httpx.Response(200))
            preview = prepare_result_publication_tool("billing", "run-1", ["QA-1"])
            receipt = dispatch_result_publication(
                "billing",
                execution_id="run-1",
                source_ids=("QA-1",),
                ledger=ApprovalLedger(),
                token=APPROVAL,
                confirmed=True,
                now=NOW,
            )
        assert route.call_count == 0
    finally:
        clear_test_session()
        reset_publications()
    assert preview.executed is False
    assert preview.reason == "publication_disabled"
    assert receipt.executed is False


def test_publication_is_single_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _write_mapping(workspace, publish=True)
    monkeypatch.setattr(
        "qa_mcp_hub.mcp.tools.test_management.load_config",
        lambda: _config(workspace, mutations=True),
    )
    reset_publications()
    digest = content_digest("run-1|QA-1")
    ledger = ApprovalLedger()
    ledger.issue(
        ApprovalGrant(
            token=APPROVAL,
            action="result_publication",
            job_id="billing",
            parameter_digest=digest,
            expires_at=datetime(2026, 10, 18, 7, 0, tzinfo=UTC),
        )
    )
    install_test_session(lambda: (httpx.Client(), "qa_mcp_ci_token_value", ()))
    try:
        with respx.mock:
            route = respx.post(
                "https://xray.cloud.getxray.app/api/v2/import/execution"
            ).mock(return_value=httpx.Response(200))
            first = dispatch_result_publication(
                "billing",
                execution_id="run-1",
                source_ids=("QA-1",),
                ledger=ledger,
                token=APPROVAL,
                confirmed=True,
                now=NOW,
            )
            second = dispatch_result_publication(
                "billing",
                execution_id="run-1",
                source_ids=("QA-1",),
                ledger=ledger,
                token=APPROVAL,
                confirmed=True,
                now=NOW,
            )
        assert route.call_count == 1
    finally:
        clear_test_session()
        reset_publications()
    assert first.executed is True
    assert first.reason == "published"
    assert second.reason == "already_published"
    assert second.executed is False
