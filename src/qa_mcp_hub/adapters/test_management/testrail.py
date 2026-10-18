"""TestRail case, suite, section, run, and result translation.

Purpose: read TestRail structures into the canonical case model.
Milestone: 09
Status: IMPLEMENTED
Ownership: adapters.test_management.testrail
Dependencies: Canonical mapping and the read-only HTTP client.
Expected tests: separated steps, priority ids, permission, and runs.
"""

from qa_mcp_hub.adapters.git.base import ReadOnlyClient, json_object
from qa_mcp_hub.adapters.test_management.base import (
    CanonicalCase,
    FieldMapping,
    PreservedField,
    execution_records,
    import_rows,
)
from qa_mcp_hub.core.errors import ProviderRequestError


def parse_cases(
    payload: dict[str, object],
) -> tuple[list[dict[str, str]], list[tuple[PreservedField, ...]]]:
    """Translate cases. Separated steps stay ordered and keep their newlines."""
    raw = payload.get("cases")
    items = raw if isinstance(raw, list) else [payload]
    rows: list[dict[str, str]] = []
    extras: list[tuple[PreservedField, ...]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ProviderRequestError(
                "invalid_response",
                "provider response had an unexpected shape",
                status_code=0,
            )
        steps, expected = _steps(item)
        priority = item.get("priority_id")
        rows.append(
            {
                "id": _text(item.get("id")),
                "title": _text(item.get("title")),
                "steps": steps,
                "expected": expected,
                "priority": _text(priority),
                "precondition": _text(item.get("custom_preconds")),
                "refs": _text(item.get("refs")),
                "version": _text(item.get("custom_case_version")),
            }
        )
        extras.append(_context(item))
    return rows, extras


def cases_from_payload(
    payload: dict[str, object], mapping: FieldMapping
) -> tuple[CanonicalCase, ...]:
    """Map TestRail cases with the reviewed priority table."""
    rows, extras = parse_cases(payload)
    return import_rows(rows, mapping, extras=extras)


def fetch_cases(
    client: ReadOnlyClient, *, base_url: str, project_id: str, token: str
) -> dict[str, object]:
    """Read one page of cases for a project."""
    if not project_id.isdigit():
        raise ProviderRequestError(
            "invalid_response",
            "TestRail project id is invalid",
            status_code=0,
        )
    response = client.get(
        _endpoint(base_url, f"/api/v2/get_cases/{project_id}"),
        headers=_headers(token),
    )
    return json_object(response)


def fetch_runs(
    client: ReadOnlyClient, *, base_url: str, project_id: str, token: str
) -> tuple[str, ...]:
    """Return run ids. A run id is not a test result."""
    response = client.get(
        _endpoint(base_url, f"/api/v2/get_runs/{project_id}"),
        headers=_headers(token),
    )
    payload = json_object(response)
    runs = payload.get("runs")
    if not isinstance(runs, list):
        raise ProviderRequestError(
            "invalid_response",
            "provider response had an unexpected shape",
            status_code=0,
        )
    return tuple(
        item.source_id
        for item in execution_records(runs, provider="testrail", edition="cloud")
    )


def _steps(item: dict[str, object]) -> tuple[str, str]:
    separated = item.get("custom_steps_separated")
    if isinstance(separated, list):
        actions: list[str] = []
        expected: list[str] = []
        for step in separated:
            if not isinstance(step, dict):
                continue
            actions.append(_text(step.get("content")))
            expected.append(_text(step.get("expected")))
        return "\n---\n".join(actions), "\n---\n".join(expected)
    text = item.get("custom_steps")
    if isinstance(text, str):
        return text, _text(item.get("custom_expected"))
    return "", ""


def _context(item: dict[str, object]) -> tuple[PreservedField, ...]:
    preserved: list[PreservedField] = []
    for key in ("suite_id", "section_id"):
        value = item.get(key)
        if isinstance(value, int):
            preserved.append(PreservedField(name=key, value=str(value)))
    return tuple(preserved)


def _endpoint(base_url: str, method: str) -> str:
    """Keep the TestRail method in the query string, including the page size."""
    return f"{base_url.rstrip('/')}/index.php?{method}&limit=20&offset=0"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return ""
