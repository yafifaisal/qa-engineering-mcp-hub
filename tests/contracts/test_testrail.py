"""Offline TestRail contract."""

import httpx
import pytest
import respx

from qa_mcp_hub.adapters.git.base import ReadOnlyClient
from qa_mcp_hub.adapters.test_management.base import (
    ColumnMap,
    FieldMapping,
    PreservedField,
    compare_cases,
    related_records,
    result_record,
)
from qa_mcp_hub.adapters.test_management.testrail import (
    cases_from_payload,
    fetch_cases,
    fetch_runs,
)
from qa_mcp_hub.adapters.test_management.xray import cases_from_cloud
from qa_mcp_hub.core.errors import HubError, ProviderRequestError


def _cloud_case():
    return cases_from_cloud(
        {
            "data": {
                "getTests": {
                    "results": [
                        {
                            "issueId": "100",
                            "jira": {"key": "QA-1", "summary": "Pay an order"},
                            "priority": {"name": "High"},
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
        },
        FieldMapping(
            id="billing",
            provider="xray",
            edition="cloud",
            format="api",
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
            priorities={"High": "High"},
            results={"Untested": "Untested"},
        ),
    )[0]


CI_VALUE = "qa_mcp_ci_token_value"


def _testrail_mapping() -> FieldMapping:
    return FieldMapping(
        id="billing",
        provider="testrail",
        edition="cloud",
        format="api",
        step_format="blocks",
        project_id="7",
        base_url="https://testrail.example.com",
        columns=ColumnMap(
            source_id="id",
            test_case="title",
            steps="steps",
            expected_result="expected",
            priority="priority",
            precondition="precondition",
            scenario="refs",
            version="version",
        ),
        priorities={"2": "High", "1": "Low"},
        results={"Untested": "Untested"},
    )


def test_separated_steps_suite_and_section_are_preserved() -> None:
    cases = cases_from_payload(
        {
            "cases": [
                {
                    "id": 15,
                    "title": "Pay an order",
                    "priority_id": 2,
                    "suite_id": 4,
                    "section_id": 9,
                    "custom_preconds": "Card on file",
                    "refs": "QA-1",
                    "custom_steps_separated": [
                        {"content": "Open the page\nWait", "expected": "Form shown"},
                        {"content": "Enter 支払", "expected": "Payment accepted"},
                    ],
                }
            ]
        },
        _testrail_mapping(),
    )
    case = cases[0]
    assert case.steps == ("Open the page\nWait", "Enter 支払")
    assert case.expected_result == "Form shown\n---\nPayment accepted"
    assert case.precondition == "Card on file"
    assert {item.name for item in case.preserved_fields} == {"suite_id", "section_id"}
    assert case.version == ""


def test_invalid_priority_and_permission() -> None:
    with pytest.raises(HubError) as invalid:
        cases_from_payload(
            {
                "cases": [
                    {
                        "id": 1,
                        "title": "Pay",
                        "priority_id": 9,
                        "custom_steps": "Open",
                        "custom_expected": "Form",
                    }
                ]
            },
            _testrail_mapping(),
        )
    assert invalid.value.code == "mapping_rejected"
    client = httpx.Client()
    reader = ReadOnlyClient(client, allowed_host="testrail.example.com")
    try:
        with respx.mock:
            respx.get(
                "https://testrail.example.com/index.php?/api/v2/get_cases/7&limit=20&offset=0"
            ).mock(return_value=httpx.Response(403, text="hidden"))
            with pytest.raises(ProviderRequestError) as denied:
                fetch_cases(
                    reader,
                    base_url="https://testrail.example.com",
                    project_id="7",
                    token=CI_VALUE,
                )
        assert denied.value.code == "permission_denied"
    finally:
        client.close()


def test_runs_are_identifiers_and_models_compare() -> None:
    client = httpx.Client()
    reader = ReadOnlyClient(client, allowed_host="testrail.example.com")
    try:
        with respx.mock:
            respx.get(
                "https://testrail.example.com/index.php?/api/v2/get_runs/7&limit=20&offset=0"
            ).mock(
                return_value=httpx.Response(
                    200, json={"runs": [{"id": 3, "name": "Nightly"}]}
                )
            )
            runs = fetch_runs(
                reader,
                base_url="https://testrail.example.com",
                project_id="7",
                token=CI_VALUE,
            )
    finally:
        client.close()
    assert runs == ("3",)
    rail = cases_from_payload(
        {
            "cases": [
                {
                    "id": 15,
                    "title": "Pay an order",
                    "priority_id": 2,
                    "suite_id": 4,
                    "custom_steps_separated": [
                        {"content": "Open the page", "expected": "Form shown"},
                        {"content": "Enter the amount", "expected": "Payment accepted"},
                    ],
                }
            ]
        },
        _testrail_mapping(),
    )[0]
    cloud = _cloud_case()
    compared = compare_cases(cloud, rail)
    assert compared.compatible is True
    assert "steps" not in compared.differences
    assert "provider" in compared.differences
    assert "source_id" in compared.differences
    suites, plans = related_records((rail,))
    assert suites[0].source_id == "4"
    assert suites[0].provider == "testrail"
    assert plans == ()
    planned = rail.model_copy(
        update={
            "preserved_fields": rail.preserved_fields
            + (PreservedField(name="plan_id", value="8"),)
        }
    )
    _suites, plans = related_records((planned,))
    assert plans[0].source_id == "8"
    assert plans[0].case_ids == ("15",)
    recorded = result_record(
        execution_id="3",
        source_id="15",
        provider="testrail",
        result="Passed",
    )
    assert recorded.result == "Passed"
    with pytest.raises(HubError) as invalid_result:
        result_record(
            execution_id="3",
            source_id="15",
            provider="testrail",
            result="green",
        )
    assert invalid_result.value.code == "mapping_rejected"
