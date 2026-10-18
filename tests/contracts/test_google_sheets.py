"""Mocked Google Sheets contract."""

import httpx
import pytest
import respx

from qa_mcp_hub.adapters.git.base import ReadOnlyClient
from qa_mcp_hub.adapters.test_management.base import ColumnMap, FieldMapping
from qa_mcp_hub.adapters.test_management.google_sheets import (
    SHEETS_READONLY_SCOPE,
    cases_from_values,
    fetch_values,
    require_readonly_scope,
)
from qa_mcp_hub.core.errors import ProviderRequestError

CI_VALUE = "qa_mcp_ci_token_value"


def _mapping() -> FieldMapping:
    return FieldMapping(
        id="sheet",
        provider="google_sheets",
        edition="sheets",
        format="api",
        spreadsheet_id="sheet-1",
        step_format="multiline",
        columns=ColumnMap(
            source_id="ID",
            test_case="Test Case",
            steps="Steps",
            expected_result="Expected Result",
            priority="Priority",
            scenario="Scenario",
            notes="Notes",
        ),
        priorities={"High": "High"},
        results={"Untested": "Untested"},
    )


def test_values_keep_unicode_and_custom_columns() -> None:
    payload = {
        "values": [
            [
                "ID",
                "Scenario",
                "Priority",
                "Test Case",
                "Steps",
                "Expected Result",
                "Notes",
            ],
            [
                "BILL-1",
                "Checkout",
                "High",
                "Pay an order",
                "Open\nEnter 支払",
                "Receipt",
                "café",
            ],
        ]
    }
    case = cases_from_values(payload, _mapping())[0]
    assert case.steps == ("Open\nEnter 支払",)
    assert case.notes == "café"
    assert case.provider == "google_sheets"
    assert case.edition == "sheets"


def test_readonly_scope_and_permission() -> None:
    with pytest.raises(ProviderRequestError) as scope:
        require_readonly_scope(("https://www.googleapis.com/auth/spreadsheets",))
    assert scope.value.code == "insufficient_scope"
    client = httpx.Client()
    reader = ReadOnlyClient(client, allowed_host="sheets.googleapis.com")
    try:
        with respx.mock:
            route = respx.get(
                "https://sheets.googleapis.com/v4/spreadsheets/sheet-1/values/Cases!A1:L50"
            ).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "values": [
                            [
                                "ID",
                                "Scenario",
                                "Priority",
                                "Test Case",
                                "Steps",
                                "Expected Result",
                                "Notes",
                            ],
                            [
                                "BILL-1",
                                "Checkout",
                                "High",
                                "Pay",
                                "Open",
                                "Receipt",
                                "",
                            ],
                        ]
                    },
                )
            )
            payload = fetch_values(
                reader,
                spreadsheet_id="sheet-1",
                token=CI_VALUE,
                scopes=(SHEETS_READONLY_SCOPE,),
            )
            with pytest.raises(ProviderRequestError):
                fetch_values(
                    reader,
                    spreadsheet_id="sheet-1",
                    token=CI_VALUE,
                    scopes=("https://www.googleapis.com/auth/drive.readonly",),
                )
        assert route.call_count == 1
    finally:
        client.close()
    assert cases_from_values(payload, _mapping())[0].source_id == "BILL-1"
