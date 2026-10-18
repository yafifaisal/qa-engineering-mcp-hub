"""Parsed SELECT-only policy for registered assertions.

Purpose: reject arbitrary SQL, bind parameters, and cap rows.
Milestone: 07
Status: IMPLEMENTED
Ownership: security.sql_policy
Dependencies: Registered assertion text and dialect placeholders.
Expected tests: multi-statement rejection, CTEs, binding, and limits.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from qa_mcp_hub.core.errors import HubError

Dialect = Literal["postgresql", "mysql"]
_TABLE = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?"
_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|copy|"
    r"call|do|load|outfile|dumpfile|pg_read_file|pg_sleep|benchmark|sleep|"
    r"into)\b",
    re.IGNORECASE,
)


class PreparedQuery(BaseModel):
    """A bound read statement. Values stay outside the SQL text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str
    parameters: tuple[str, ...]
    tables: tuple[str, ...]
    dialect: Dialect


def prepare_select(
    sql: str,
    *,
    dialect: str,
    parameters: dict[str, str],
    allow_tables: tuple[str, ...],
    max_rows: int,
) -> PreparedQuery:
    """Return one bound SELECT or reject the statement."""
    if dialect not in {"postgresql", "mysql"}:
        raise HubError("sql_rejected", "sql dialect is not approved")
    if max_rows < 1 or max_rows > 100:
        raise HubError("sql_rejected", "row limit is outside the allowed range")
    text = sql.strip()
    if (
        not text
        or len(text) > 2000
        or "\x00" in text
        or ";" in text
        or "--" in text
        or "/*" in text
        or "*/" in text
        or "'" in text
        or '"' in text
        or "\\" in text
        or re.search(r"\d", text)
    ):
        raise HubError("sql_rejected", "sql text is not a single bound read")
    if not re.match(r"(?is)^(select|with)\b", text):
        raise HubError("sql_rejected", "only a read statement is allowed")
    if _FORBIDDEN.search(text):
        raise HubError("sql_rejected", "statement is not read-only")
    if not allow_tables:
        raise HubError("sql_rejected", "table allowlist is empty")
    allowed = {item.casefold() for item in allow_tables}
    ctes = {
        item.casefold()
        for item in re.findall(rf"(?i)(?:\bwith|,)\s+({_NAME})\s+as\s*\(", text)
    }
    tables = re.findall(rf"(?i)\b(?:from|join)\s+({_TABLE})\b", text)
    if not tables:
        raise HubError("sql_rejected", "statement has no allowlisted table")
    for table in tables:
        folded = table.casefold()
        if folded not in allowed and folded not in ctes:
            raise HubError("sql_rejected", "table is not allowlisted")
    names = re.findall(rf":({_NAME})\b", text)
    for name in names:
        if name not in parameters:
            raise HubError("sql_rejected", "statement parameter is missing")
    values: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        values.append(parameters[match.group(1)])
        if dialect == "postgresql":
            return f"${len(values)}"
        return "%s"

    bound = re.sub(rf":({_NAME})\b", _replace, text)
    if re.search(r":[A-Za-z_]", bound):
        raise HubError("sql_rejected", "statement parameter was not bound")
    statement = f"{bound} LIMIT {max_rows}"
    return PreparedQuery(
        statement=statement,
        parameters=tuple(values),
        tables=tuple(tables),
        dialect=dialect,  # type: ignore[arg-type]
    )
