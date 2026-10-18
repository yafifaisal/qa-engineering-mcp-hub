"""Shared database mechanics for registered, parameterized, read-only assertions.

Purpose: cap rows, redact sensitive columns, and describe a read-only session.
Milestone: 07
Status: IMPLEMENTED
Ownership: adapters.database.base
Dependencies: SQL policy and redaction.
Expected tests: row caps, redaction, and read-only session statements.
"""

from typing import Protocol

from qa_mcp_hub.auth.redaction import REDACTED
from qa_mcp_hub.core.errors import HubError

_SENSITIVE = frozenset(
    {
        "password",
        "secret",
        "token",
        "email",
        "ssn",
        "phone",
        "authorization",
        "api_key",
        "credential",
    }
)


class DatabaseReader(Protocol):
    """A read-only session. It does not accept caller-written SQL."""

    def prepare(self, protections: tuple[str, ...]) -> None:
        """Record the session protections that must run before a query."""

    def query(
        self,
        statement: str,
        parameters: tuple[str, ...],
        timeout_ms: int,
    ) -> tuple[dict[str, str], ...]:
        """Return rows for one already prepared statement."""


def statement_timeout_ms(timeout_ms: int) -> int:
    """Return a timeout inside the allowed statement window."""
    if timeout_ms < 1 or timeout_ms > 60_000:
        raise HubError("sql_rejected", "timeout is outside the allowed range")
    return timeout_ms


def redact_rows(rows: tuple[dict[str, str], ...]) -> tuple[dict[str, str], ...]:
    """Replace sensitive or oversized values before a result is stored."""
    cleaned: list[dict[str, str]] = []
    for row in rows:
        item: dict[str, str] = {}
        for key, value in row.items():
            if key.casefold() in _SENSITIVE or len(value) > 1024:
                item[key] = REDACTED
            else:
                item[key] = value
        cleaned.append(item)
    return tuple(cleaned)


def sensitive_column(name: str) -> bool:
    """Return whether a column must not be used as an assertion result."""
    return name.casefold() in _SENSITIVE
