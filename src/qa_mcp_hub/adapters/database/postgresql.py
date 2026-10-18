"""PostgreSQL session protections for a registered read-only assertion.

Purpose: force a read-only transaction and a statement timeout.
Milestone: 07
Status: IMPLEMENTED
Ownership: adapters.database.postgresql
Dependencies: Database adapter base. A live driver is not bundled.
Expected tests: read-only session, timeout, and gated live refusal.
"""

import os

from qa_mcp_hub.adapters.database.base import DatabaseReader, statement_timeout_ms
from qa_mcp_hub.core.errors import HubError


def postgresql_protections(timeout_ms: int) -> tuple[str, ...]:
    """Return the session statements issued before a registered query."""
    timeout = statement_timeout_ms(timeout_ms)
    return (
        "SET default_transaction_read_only = on",
        "BEGIN READ ONLY",
        f"SET statement_timeout = {timeout}",
    )


def open_postgresql(connection_id: str) -> DatabaseReader:
    """Refuse a live connection unless a future gated driver is supplied.

    The returned reader is never a stand-in that reports successful rows.
    """
    if not connection_id:
        raise HubError("connection_not_approved", "connection id is missing")
    if os.environ.get("QA_MCP_LIVE_DATABASES") != "1":
        raise HubError(
            "infrastructure_unavailable",
            "live PostgreSQL checks are not enabled",
        )
    raise HubError(
        "infrastructure_unavailable",
        "a PostgreSQL driver is not bundled for live checks",
    )
