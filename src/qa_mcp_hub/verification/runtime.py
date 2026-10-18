"""Process-local readers for a verification call.

Purpose: let a test supply a fixture reader without a live broker or database.
Milestone: 07
Status: IMPLEMENTED
Ownership: verification.runtime
Dependencies: Database and Kafka reader protocols.
Expected tests: default readers stay unavailable.
"""

from qa_mcp_hub.adapters.database.base import DatabaseReader
from qa_mcp_hub.adapters.streaming.kafka import TopicReader

_database: DatabaseReader | None = None
_kafka: TopicReader | None = None


def current_database() -> DatabaseReader | None:
    """Return the installed database reader, or none when infrastructure is absent."""
    return _database


def current_kafka() -> TopicReader | None:
    """Return the installed Kafka observer, or none when infrastructure is absent."""
    return _kafka


def install_readers(
    *,
    database: DatabaseReader | None = None,
    kafka: TopicReader | None = None,
) -> None:
    """Replace the process-local readers. Production leaves both unset."""
    global _database, _kafka
    _database = database
    _kafka = kafka


def clear_readers() -> None:
    """Remove fixture readers so a later call cannot reuse them."""
    install_readers(database=None, kafka=None)
