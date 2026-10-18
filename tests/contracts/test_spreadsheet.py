"""CSV and XLSX import, export, and formula safety."""

from pathlib import Path

import pytest

from qa_mcp_hub.adapters.test_management.base import (
    ColumnMap,
    FieldMapping,
    import_rows,
)
from qa_mcp_hub.adapters.test_management.spreadsheet import (
    export_csv,
    export_xlsx,
    import_csv,
    import_xlsx,
    read_csv,
)
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.planning.coverage_mapper import report_test_coverage


def _mapping(step_format: str = "multiline") -> FieldMapping:
    return FieldMapping(
        id="sheet",
        provider="spreadsheet",
        edition="local",
        format="csv",
        step_format=step_format,
        columns=ColumnMap(
            source_id="ID",
            version="Version",
            scenario="Scenario",
            priority="Priority",
            test_case="Test Case",
            precondition="Precondition",
            steps="Steps",
            expected_result="Expected Result",
            result="Result",
            notes="Notes",
            evidence="Evidence",
            automation_suite_id="Automation Suite",
        ),
        priorities={"High": "High", "Low": "Low"},
        results={"Untested": "Untested", "Passed": "Passed", "Failed": "Failed"},
    )


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "ID": "BILL-1",
        "Version": "1",
        "Scenario": "Checkout",
        "Priority": "High",
        "Test Case": "Pay an order",
        "Precondition": "Card on file",
        "Steps": "Open the page\nEnter 支払",
        "Expected Result": "Payment accepted\nReceipt shown",
        "Result": "Untested",
        "Notes": "café",
        "Evidence": "screenshot",
        "Automation Suite": "billing-bruno",
        "Owner": "qa",
    }
    row.update(overrides)
    return row


def test_unicode_multiline_and_preserved_column(tmp_path: Path) -> None:
    mapping = _mapping()
    cases = import_rows([_row()], mapping, extras=None)
    assert cases[0].steps == ("Open the page\nEnter 支払",)
    assert cases[0].notes == "café"
    assert cases[0].expected_result == "Payment accepted\nReceipt shown"
    path = tmp_path / "cases.csv"
    _write(path, [_row()])
    loaded = import_csv(path, tmp_path, mapping)
    assert loaded[0].steps == cases[0].steps
    assert loaded[0].notes == "café"
    assert loaded[0].preserved_fields[0].name == "Owner"
    assert loaded[0].preserved_fields[0].value == "qa"


def test_step_formats_missing_fields_and_status(tmp_path: Path) -> None:
    blocks = _mapping("blocks")
    case = import_rows(
        [_row(Steps="Open the page\n---\nEnter the amount")],
        blocks,
    )[0]
    assert case.steps == ("Open the page", "Enter the amount")
    delimited = _mapping("delimiter")
    split = import_rows([_row(Steps="Open the page || Enter the amount")], delimited)[0]
    assert split.steps == ("Open the page", "Enter the amount")
    with pytest.raises(HubError) as missing:
        import_rows([_row(**{"Test Case": ""})], _mapping())
    assert missing.value.code == "missing_field"
    with pytest.raises(HubError) as status:
        import_rows([_row(Result="green")], _mapping())
    assert status.value.code == "mapping_rejected"
    with pytest.raises(HubError) as priority:
        import_rows([_row(Priority="Urgent")], _mapping())
    assert priority.value.code == "mapping_rejected"
    with pytest.raises(HubError) as duplicate:
        import_rows([_row(), _row()], _mapping())
    assert duplicate.value.code == "duplicate_case"
    encoded = tmp_path / "utf16.csv"
    encoded.write_bytes("ID,Test Case\n".encode("utf-16"))
    with pytest.raises(HubError) as encoding:
        read_csv(encoded, tmp_path)
    assert encoding.value.code == "encoding_rejected"


def test_formula_neutralization_and_xlsx_roundtrip(tmp_path: Path) -> None:
    mapping = _mapping("blocks")
    cases = import_rows(
        [_row(Steps="Open\n---\nPay", **{"Test Case": "=SUM(1,1)"})],
        mapping,
    )
    csv_path = tmp_path / "safe.csv"
    _text, neutralized, digest, changed = export_csv(cases, csv_path, tmp_path)
    assert changed is True
    assert "=SUM(1,1)" in neutralized
    assert "'=SUM(1,1)" in csv_path.read_text(encoding="utf-8")
    again = export_csv(cases, csv_path, tmp_path)
    assert again[3] is False
    assert again[2] == digest
    xlsx_path = tmp_path / "safe.xlsx"
    export_xlsx(cases, xlsx_path, tmp_path)
    loaded = import_xlsx(xlsx_path, tmp_path, mapping)
    assert loaded[0].steps == ("Open", "Pay")
    assert loaded[0].notes == "café"
    assert loaded[0].test_case == "'=SUM(1,1)"


def test_suite_correlation_rejects_unknown_status() -> None:
    cases = import_rows([_row()], _mapping())
    report = report_test_coverage(
        ((cases[0].source_id, cases[0].automation_suite_id),),
        {"billing-bruno": "Passed"},
    )
    assert report[0].correlated is True
    assert report[0].suite_status == "Passed"
    missing = report_test_coverage((("BILL-2", ""),), {"billing-bruno": "Passed"})
    assert missing[0].correlated is False
    assert missing[0].evidence.value == "UNKNOWN"
    with pytest.raises(HubError) as invalid:
        report_test_coverage((("BILL-1", "billing-bruno"),), {"billing-bruno": "green"})
    assert invalid.value.code == "mapping_rejected"


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    import csv

    headers = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_tools_preview_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    source = workspace / "test-management" / "import-templates" / "cases.csv"
    source.parent.mkdir(parents=True)
    (workspace / "test-management" / "mappings").mkdir()
    _write(source, [_row(), _row(ID="BILL-2", **{"Test Case": "Refund an order"})])
    mapping = _mapping()
    document = mapping.model_copy(
        update={"id": "billing", "source": "test-management/import-templates/cases.csv"}
    )
    import yaml

    yaml.safe_dump(
        document.model_dump(mode="json"),
        (workspace / "test-management" / "mappings" / "billing.yaml").open(
            "w", encoding="utf-8"
        ),
        sort_keys=False,
    )
    from qa_mcp_hub.config.models import (
        CURRENT_SCHEMA_VERSION,
        ExecutionOverrides,
        HubConfig,
        ProfileConfig,
        QAWorkspaceReference,
    )
    from qa_mcp_hub.mcp.tools.test_management import (
        compare_test_cases_tool,
        export_test_cases_tool,
        preview_test_case_import_tool,
        search_test_cases_tool,
    )

    config = HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={
            "alpha": ProfileConfig(
                workspace_id="ws",
                execution=ExecutionOverrides(),
            )
        },
        workspaces=(QAWorkspaceReference(id="ws", path=str(workspace)),),
    )
    monkeypatch.setattr(
        "qa_mcp_hub.mcp.tools.test_management.load_config",
        lambda: config,
    )
    found = search_test_cases_tool("refund", "billing")
    assert found[0].source_id == "BILL-2"
    preview = preview_test_case_import_tool("billing")
    assert preview.dry_run is True
    assert preview.written is False
    assert len(preview.cases) == 2
    compared = compare_test_cases_tool("billing", "BILL-1", "BILL-2")
    assert "test_case" in compared.differences
    exported = export_test_cases_tool("billing", "out.csv", dry_run=True)
    assert exported.written is False
    assert not (workspace / "test-management" / "out.csv").exists()
