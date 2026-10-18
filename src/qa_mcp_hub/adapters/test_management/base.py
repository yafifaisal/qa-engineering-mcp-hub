"""Canonical test-management records and field mapping.

Purpose: map provider rows into one case shape and report every extra field.
Milestone: 09
Status: IMPLEMENTED
Ownership: adapters.test_management.base
Dependencies: Path allowlist and Pydantic v2.
Expected tests: mapping errors, duplicates, multiline steps, and formula safety.
"""

import hashlib
import re
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.security.path_allowlist import resolve_within

_STEP_BREAK = "\n---\n"
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_FILE_LIMIT = 65536
_PRIORITIES = frozenset({"Critical", "High", "Medium", "Low"})
_RESULTS = frozenset({"Passed", "Failed", "Blocked", "Untested", "Retest"})
_REQUIRED = ("source_id", "test_case", "steps", "expected_result", "priority")


class PreservedField(BaseModel):
    """A source field the canonical schema does not replace with a blank."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    value: str


class CanonicalCase(BaseModel):
    """One test case. Provider identity and version stay attached."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    provider: str
    edition: str
    version: str = ""
    scenario: str = ""
    priority: str
    test_case: str
    precondition: str = ""
    steps: tuple[str, ...]
    expected_result: str
    result: str = "Untested"
    notes: str = ""
    evidence: str = ""
    automation_suite_id: str = ""
    preserved_fields: tuple[PreservedField, ...] = ()


class CanonicalSuite(BaseModel):
    """A provider suite id lifted from a preserved field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    provider: str
    edition: str
    name: str = ""


class CanonicalPlan(BaseModel):
    """A provider plan id and the cases that named it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    provider: str
    edition: str
    name: str = ""
    case_ids: tuple[str, ...] = ()


class CanonicalExecution(BaseModel):
    """A provider run. A run id is not a test result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    provider: str
    edition: str
    plan_id: str = ""
    case_ids: tuple[str, ...] = ()


class CanonicalResult(BaseModel):
    """One mapped result for one case inside one execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str
    source_id: str
    provider: str
    result: str
    evidence: str = ""
    notes: str = ""


class ColumnMap(BaseModel):
    """Source column names for the canonical fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    test_case: str
    steps: str
    expected_result: str
    priority: str
    scenario: str = ""
    precondition: str = ""
    result: str = ""
    notes: str = ""
    evidence: str = ""
    version: str = ""
    automation_suite_id: str = ""


class FieldMapping(BaseModel):
    """A reviewed mapping. Remote publishing stays off unless explicitly allowed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    provider: str
    edition: str
    format: str = "api"
    source: str = ""
    connection_id: str = ""
    spreadsheet_id: str = ""
    project_id: str = ""
    base_url: str = ""
    allow_publish: bool = False
    step_format: str = "multiline"
    columns: ColumnMap
    priorities: dict[str, str]
    results: dict[str, str]


class ImportPreview(BaseModel):
    """A dry-run import. This model cannot represent a completed write."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_id: str
    dry_run: bool = True
    written: bool = False
    cases: tuple[CanonicalCase, ...]
    preserved_fields: tuple[str, ...] = ()


class ExportPreview(BaseModel):
    """A local export plan. ``written`` is false during dry-run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_id: str
    dry_run: bool
    written: bool
    path: str
    digest: str
    formula_neutralized: tuple[str, ...] = ()
    preview_truncated: bool = False
    reason: str = "preview"


class CaseComparison(BaseModel):
    """Field-by-field differences between two canonical cases."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    compatible: bool
    differences: tuple[str, ...]
    preserved_left: tuple[str, ...] = ()
    preserved_right: tuple[str, ...] = ()


class PublicationPreview(BaseModel):
    """A result-publication plan. The MCP tool leaves ``executed`` false."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    executed: bool = False
    reason: str
    execution_id: str
    source_ids: tuple[str, ...] = ()


def neutralize_formula(value: str) -> tuple[str, bool]:
    """Prefix spreadsheet formulas so a generated file does not execute them."""
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value, True
    return value, False


def join_steps(steps: tuple[str, ...]) -> str:
    """Join steps with a separator that leaves newlines inside a step intact."""
    return _STEP_BREAK.join(steps)


def split_steps(value: str, step_format: str) -> tuple[str, ...]:
    """Split steps only in the format the mapping selected."""
    if value == "":
        return ()
    if step_format == "delimiter":
        parts = [part.strip() for part in value.split("||")]
        return tuple(part for part in parts if part)
    if step_format == "blocks":
        return tuple(value.split(_STEP_BREAK))
    if step_format != "multiline":
        raise HubError("mapping_rejected", "step format is not recognized")
    return (value,)


def import_rows(
    rows: list[dict[str, str]],
    mapping: FieldMapping,
    *,
    extras: list[tuple[PreservedField, ...]] | None = None,
) -> tuple[CanonicalCase, ...]:
    """Map rows into canonical cases. Unknown values and duplicate ids fail."""
    _validate_maps(mapping)
    seen: set[str] = set()
    cases: list[CanonicalCase] = []
    extra_rows = extras or [() for _ in rows]
    if len(extra_rows) != len(rows):
        raise HubError("mapping_rejected", "preserved fields do not match the rows")
    for row, preserved in zip(rows, extra_rows, strict=True):
        case = _one_case(row, mapping, preserved)
        if case.source_id in seen:
            raise HubError("duplicate_case", "test case id is duplicated")
        seen.add(case.source_id)
        cases.append(case)
    return tuple(cases)


def compare_cases(left: CanonicalCase, right: CanonicalCase) -> CaseComparison:
    """Compare two cases on the shared field set."""
    differences: list[str] = []
    for name in (
        "source_id",
        "provider",
        "edition",
        "version",
        "scenario",
        "priority",
        "test_case",
        "precondition",
        "steps",
        "expected_result",
        "result",
        "notes",
        "evidence",
        "automation_suite_id",
    ):
        if getattr(left, name) != getattr(right, name):
            differences.append(name)
    return CaseComparison(
        compatible=True,
        differences=tuple(differences),
        preserved_left=tuple(item.name for item in left.preserved_fields),
        preserved_right=tuple(item.name for item in right.preserved_fields),
    )


def load_mappings(workspace: Path) -> dict[str, FieldMapping]:
    """Load reviewed mappings from the QA workspace."""
    root = workspace / "test-management" / "mappings"
    if not root.is_dir():
        return {}
    found: dict[str, FieldMapping] = {}
    for path in sorted(root.glob("*.yaml")):
        resolved = resolve_within(path, [workspace])
        if resolved.stat().st_size > _FILE_LIMIT:
            raise HubError("mapping_invalid", "mapping file is too large")
        loaded = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise HubError("mapping_invalid", "mapping file is not a mapping")
        try:
            item = FieldMapping.model_validate(loaded)
        except ValidationError as exc:
            raise HubError("mapping_invalid", "mapping file is invalid") from exc
        if item.id in found:
            raise HubError("duplicate_case", "mapping id is duplicated")
        found[item.id] = item
    return found


def require_mapping(mappings: dict[str, FieldMapping], mapping_id: str) -> FieldMapping:
    """Return one reviewed mapping."""
    item = mappings.get(mapping_id)
    if item is None:
        raise HubError("mapping_not_registered", "mapping is not in the workspace")
    return item


def content_digest(text: str) -> str:
    """Hash export bytes so a repeated export can be recognized."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def related_records(
    cases: tuple[CanonicalCase, ...],
) -> tuple[tuple[CanonicalSuite, ...], tuple[CanonicalPlan, ...]]:
    """Lift preserved suite and plan ids without dropping them from the case."""
    suites: dict[str, CanonicalSuite] = {}
    plans: dict[str, list[str]] = {}
    identity: dict[str, tuple[str, str]] = {}
    for case in cases:
        for field in case.preserved_fields:
            if field.name == "suite_id" and field.value not in suites:
                suites[field.value] = CanonicalSuite(
                    source_id=field.value,
                    provider=case.provider,
                    edition=case.edition,
                )
            if field.name == "plan_id":
                plans.setdefault(field.value, []).append(case.source_id)
                identity[field.value] = (case.provider, case.edition)
    plan_records = tuple(
        CanonicalPlan(
            source_id=plan_id,
            provider=identity[plan_id][0],
            edition=identity[plan_id][1],
            case_ids=tuple(plans[plan_id]),
        )
        for plan_id in plans
    )
    return tuple(suites.values()), plan_records


def execution_records(
    runs: list[object],
    *,
    provider: str,
    edition: str,
) -> tuple[CanonicalExecution, ...]:
    """Translate provider runs into execution ids. Status text is not copied."""
    found: list[CanonicalExecution] = []
    for item in runs:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id")
        if not isinstance(raw_id, int):
            continue
        plan = item.get("plan_id")
        found.append(
            CanonicalExecution(
                source_id=str(raw_id),
                provider=provider,
                edition=edition,
                plan_id=str(plan) if isinstance(plan, int) else "",
            )
        )
    return tuple(found)


def result_record(
    *,
    execution_id: str,
    source_id: str,
    provider: str,
    result: str,
) -> CanonicalResult:
    """Accept only a canonical result value."""
    if result not in _RESULTS:
        raise HubError("mapping_rejected", "result value is not mapped")
    return CanonicalResult(
        execution_id=execution_id,
        source_id=source_id,
        provider=provider,
        result=result,
    )


def _one_case(
    row: dict[str, str],
    mapping: FieldMapping,
    preserved: tuple[PreservedField, ...],
) -> CanonicalCase:
    values = {name: _cell(row, getattr(mapping.columns, name)) for name in _REQUIRED}
    for name, value in values.items():
        if value == "":
            raise HubError("missing_field", f"{name} is missing")
    priority = _mapped(mapping.priorities, values["priority"], "priority", _PRIORITIES)
    result_cell = _cell(row, mapping.columns.result)
    result = (
        "Untested"
        if result_cell == ""
        else _mapped(mapping.results, result_cell, "result", _RESULTS)
    )
    steps = split_steps(values["steps"], mapping.step_format)
    if not steps or any(step == "" for step in steps):
        raise HubError("missing_field", "steps is missing")
    _reject_oversized(values["test_case"])
    _reject_oversized(values["expected_result"])
    return CanonicalCase(
        source_id=values["source_id"],
        provider=mapping.provider,
        edition=mapping.edition,
        version=_cell(row, mapping.columns.version),
        scenario=_cell(row, mapping.columns.scenario),
        priority=priority,
        test_case=values["test_case"],
        precondition=_cell(row, mapping.columns.precondition),
        steps=steps,
        expected_result=values["expected_result"],
        result=result,
        notes=_cell(row, mapping.columns.notes),
        evidence=_cell(row, mapping.columns.evidence),
        automation_suite_id=_cell(row, mapping.columns.automation_suite_id),
        preserved_fields=preserved,
    )


def _cell(row: dict[str, str], column: str) -> str:
    if column == "":
        return ""
    if column not in row:
        raise HubError("missing_field", f"{column} column is missing")
    return row[column]


def _mapped(table: dict[str, str], raw: str, kind: str, allowed: frozenset[str]) -> str:
    if raw not in table:
        raise HubError("mapping_rejected", f"{kind} value is not mapped")
    canonical = table[raw]
    if canonical not in allowed:
        raise HubError("mapping_rejected", f"{kind} value is not mapped")
    return canonical


def _validate_maps(mapping: FieldMapping) -> None:
    if not mapping.priorities or not mapping.results:
        raise HubError("mapping_rejected", "priority and result maps are required")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", mapping.id):
        raise HubError("mapping_invalid", "mapping id is invalid")


def _reject_oversized(value: str) -> None:
    if len(value) > 8000:
        raise HubError("field_too_large", "a field exceeded the size limit")
