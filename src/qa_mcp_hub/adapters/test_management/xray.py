"""Xray Cloud and Data Center case translation.

Purpose: read Xray tests into the canonical case model.
Milestone: 09
Status: IMPLEMENTED
Ownership: adapters.test_management.xray
Dependencies: Canonical mapping and the read-only HTTP client.
Expected tests: edition differences, permission, and preserved fields.
"""

from qa_mcp_hub.adapters.git.base import ReadOnlyClient, json_object
from qa_mcp_hub.adapters.test_management.base import (
    CanonicalCase,
    FieldMapping,
    PreservedField,
    import_rows,
)
from qa_mcp_hub.core.errors import ProviderRequestError

_CLOUD = "https://xray.cloud.getxray.app/api/v2/graphql"
_KEEP = {"issueId", "jira", "steps", "status", "priority", "testType"}


def edition_endpoint(edition: str, base_url: str) -> str:
    """Return the edition-specific read endpoint."""
    if edition == "cloud":
        return _CLOUD
    if edition == "data_center":
        return base_url.rstrip("/") + "/rest/raven/1.0/api/test"
    raise ProviderRequestError(
        "invalid_edition",
        "Xray edition must be cloud or data_center",
        status_code=0,
    )


def parse_cloud(
    payload: dict[str, object],
) -> tuple[list[dict[str, str]], list[tuple[PreservedField, ...]]]:
    """Translate an Xray Cloud GraphQL page. Step actions stay separate."""
    data = payload.get("data")
    tests = data.get("getTests") if isinstance(data, dict) else None
    results = tests.get("results") if isinstance(tests, dict) else None
    if not isinstance(results, list):
        raise ProviderRequestError(
            "invalid_response",
            "provider response had an unexpected shape",
            status_code=0,
        )
    rows: list[dict[str, str]] = []
    extras: list[tuple[PreservedField, ...]] = []
    for item in results:
        if not isinstance(item, dict):
            raise ProviderRequestError(
                "invalid_response",
                "provider response had an unexpected shape",
                status_code=0,
            )
        jira = item.get("jira")
        if not isinstance(jira, dict):
            raise ProviderRequestError(
                "invalid_response",
                "provider response had an unexpected shape",
                status_code=0,
            )
        actions, expected = _cloud_steps(item.get("steps"))
        priority = item.get("priority")
        priority_name = priority.get("name") if isinstance(priority, dict) else ""
        rows.append(
            {
                "key": _text(jira.get("key")),
                "summary": _text(jira.get("summary")),
                "steps": actions,
                "expected": expected,
                "priority": _text(priority_name),
                "scenario": _text(jira.get("summary")),
                "version": _text(item.get("issueId")),
            }
        )
        extras.append(_extras(item, _KEEP))
    return rows, extras


def parse_data_center(
    payload: dict[str, object],
) -> tuple[list[dict[str, str]], list[tuple[PreservedField, ...]]]:
    """Translate Xray Data Center steps. The step field is ``step``, not ``action``."""
    tests = payload.get("tests")
    items = tests if isinstance(tests, list) else [payload]
    rows: list[dict[str, str]] = []
    extras: list[tuple[PreservedField, ...]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ProviderRequestError(
                "invalid_response",
                "provider response had an unexpected shape",
                status_code=0,
            )
        actions, expected = _dc_steps(item.get("steps"))
        rows.append(
            {
                "key": _text(item.get("key")),
                "summary": _text(item.get("summary")),
                "steps": actions,
                "expected": expected,
                "priority": _text(item.get("priority")),
                "scenario": _text(item.get("definition")),
                "version": _text(item.get("version")),
            }
        )
        extras.append(
            _extras(
                item, {"key", "summary", "steps", "priority", "definition", "version"}
            )
        )
    return rows, extras


def fetch_cloud(client: ReadOnlyClient, token: str) -> dict[str, object]:
    """Read one Cloud GraphQL page. The query text is fixed, not caller input."""
    response = client.read_post(
        _CLOUD,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        body={"query": "{ getTests(limit: 20) { results { issueId jira { key } } } }"},
    )
    return json_object(response)


def fetch_data_center(
    client: ReadOnlyClient, *, base_url: str, token: str
) -> dict[str, object]:
    """Read Data Center tests from the Jira plugin REST path."""
    response = client.get(
        edition_endpoint("data_center", base_url),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    return json_object(response)


def cases_from_cloud(
    payload: dict[str, object], mapping: FieldMapping
) -> tuple[CanonicalCase, ...]:
    """Map a Cloud payload with the reviewed priority and result tables."""
    rows, extras = parse_cloud(payload)
    return import_rows(rows, mapping, extras=extras)


def cases_from_data_center(
    payload: dict[str, object], mapping: FieldMapping
) -> tuple[CanonicalCase, ...]:
    """Map a Data Center payload with the reviewed priority and result tables."""
    rows, extras = parse_data_center(payload)
    return import_rows(rows, mapping, extras=extras)


def _cloud_steps(value: object) -> tuple[str, str]:
    if not isinstance(value, list):
        return "", ""
    actions: list[str] = []
    expected: list[str] = []
    for step in value:
        if not isinstance(step, dict):
            continue
        actions.append(_text(step.get("action")))
        expected.append(_text(step.get("result")))
    return "\n---\n".join(actions), "\n---\n".join(expected)


def _dc_steps(value: object) -> tuple[str, str]:
    if not isinstance(value, list):
        return "", ""
    actions: list[str] = []
    expected: list[str] = []
    for step in value:
        if not isinstance(step, dict):
            continue
        actions.append(_text(step.get("step")))
        expected.append(_text(step.get("result")))
    return "\n---\n".join(actions), "\n---\n".join(expected)


def _extras(item: dict[str, object], known: set[str]) -> tuple[PreservedField, ...]:
    preserved: list[PreservedField] = []
    for key, value in item.items():
        if key in known or not isinstance(value, str) or not value:
            continue
        preserved.append(PreservedField(name=str(key), value=value))
    return tuple(preserved)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return ""
