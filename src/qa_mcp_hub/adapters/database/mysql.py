"""MySQL session protections for a registered read-only assertion.

Purpose: force a read-only transaction and a statement execution limit.
Milestone: 07
Status: IMPLEMENTED
Ownership: adapters.database.mysql
Dependencies: Database adapter base. A live driver is not bundled.
Expected tests: read-only session, timeout, and gated live refusal.
"""

import os

from qa_mcp_hub.adapters.database.base import DatabaseReader, statement_timeout_ms
from qa_mcp_hub.core.errors import HubError


def mysql_protections(timeout_ms: int) -> tuple[str, ...]:
    """Return the session statements issued before a registered query."""
    timeout = statement_timeout_ms(timeout_ms)
    return (
        "SET SESSION TRANSACTION READ ONLY",
        "START TRANSACTION READ ONLY",
        f"SET SESSION MAX_EXECUTION_TIME = {timeout}",
    )


def open_mysql(connection_id: str) -> DatabaseReader:
    """Refuse a live connection unless a future gated driver is supplied."""
    if not connection_id:
        raise HubError("connection_not_approved", "connection id is missing")
    if os.environ.get("QA_MCP_LIVE_DATABASES") != "1":
        raise HubError(
            "infrastructure_unavailable",
            "live MySQL checks are not enabled",
        )
    raise HubError(
        "infrastructure_unavailable",
        "a MySQL driver is not bundled for live checks",
    )
