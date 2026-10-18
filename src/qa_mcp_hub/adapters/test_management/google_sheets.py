"""Google Sheets read adapter.

Purpose: read one sheet range with the spreadsheets readonly scope.
Milestone: 09
Status: IMPLEMENTED
Ownership: adapters.test_management.google_sheets
Dependencies: Canonical mapping and the read-only HTTP client.
Expected tests: mocked values, scope rejection, and column mapping.
"""

from qa_mcp_hub.adapters.git.base import ReadOnlyClient, json_object
from qa_mcp_hub.adapters.test_management.base import CanonicalCase, FieldMapping
from qa_mcp_hub.adapters.test_management.spreadsheet import _import_table
from qa_mcp_hub.core.errors import ProviderRequestError

SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
_HOST = "sheets.googleapis.com"


def require_readonly_scope(scopes: tuple[str, ...]) -> None:
    """Accept a token only when the minimal readonly scope is present."""
    if SHEETS_READONLY_SCOPE not in scopes:
        raise ProviderRequestError(
            "insufficient_scope",
            "google oauth token is missing the Sheets readonly scope",
            status_code=0,
        )


def fetch_values(
    client: ReadOnlyClient,
    *,
    spreadsheet_id: str,
    token: str,
    scopes: tuple[str, ...],
) -> dict[str, object]:
    """Read one bounded range. The write scope is not requested."""
    require_readonly_scope(scopes)
    if not spreadsheet_id or "/" in spreadsheet_id or ".." in spreadsheet_id:
        raise ProviderRequestError(
            "invalid_response",
            "spreadsheet id is invalid",
            status_code=0,
        )
    response = client.get(
        f"https://{_HOST}/v4/spreadsheets/{spreadsheet_id}/values/Cases!A1:L50",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    return json_object(response)


def cases_from_values(
    payload: dict[str, object], mapping: FieldMapping
) -> tuple[CanonicalCase, ...]:
    """Map a values response through the reviewed columns."""
    grid = payload.get("values")
    if not isinstance(grid, list) or not grid:
        raise ProviderRequestError(
            "invalid_response",
            "provider response had an unexpected shape",
            status_code=0,
        )
    header = grid[0]
    if not isinstance(header, list):
        raise ProviderRequestError(
            "invalid_response",
            "provider response had an unexpected shape",
            status_code=0,
        )
    names = [item if isinstance(item, str) else "" for item in header]
    rows: list[dict[str, str]] = []
    for values in grid[1:]:
        if not isinstance(values, list):
            continue
        row = {
            names[index]: values[index]
            if index < len(values) and isinstance(values[index], str)
            else ""
            for index in range(len(names))
            if names[index]
        }
        rows.append(row)
    return _import_table(rows, mapping)
