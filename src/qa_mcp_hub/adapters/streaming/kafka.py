"""Kafka observation that never commits a consumer offset.

Purpose: bound topic reads and keep production consumer groups unchanged.
Milestone: 07
Status: IMPLEMENTED
Ownership: adapters.streaming.kafka
Dependencies: Authorized client settings. A live client is not bundled.
Expected tests: SASL settings, missing events, DLQ, and offset immutability.
"""

import os
from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from qa_mcp_hub.core.errors import HubError

_PROTOCOLS = frozenset({"SSL", "SASL_SSL"})
_MECHANISMS = frozenset({"PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"})


class TopicRead(BaseModel):
    """One bounded topic inspection. Offset commits stay at zero."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    messages: tuple[dict[str, str], ...] = ()
    offsets_committed: int = 0
    retention_gap: bool = False
    scanned: int = Field(ge=0)


class TopicReader(Protocol):
    """Reads a permitted topic without a commit method that succeeds."""

    offsets_committed: int

    def read_topic(
        self,
        topic: str,
        *,
        max_messages: int,
        timeout_seconds: float,
    ) -> TopicRead:
        """Return at most the requested number of already buffered messages."""

    def commit(self) -> None:
        """Observers reject offset commits."""


def observer_settings(
    *,
    protocol: str,
    mechanism: str | None,
    group_id: str,
) -> dict[str, str | bool]:
    """Build a client configuration that cannot auto-commit offsets."""
    if protocol not in _PROTOCOLS:
        raise HubError("kafka_rejected", "kafka protocol is not approved")
    if not group_id.startswith("qa-mcp-observer-"):
        raise HubError("kafka_rejected", "consumer group is not an observer group")
    settings: dict[str, str | bool] = {
        "enable.auto.commit": False,
        "security.protocol": protocol,
        "group.id": group_id,
        "auto.offset.reset": "latest",
    }
    if mechanism is not None:
        if mechanism not in _MECHANISMS:
            raise HubError("kafka_rejected", "sasl mechanism is not approved")
        settings["sasl.mechanism"] = mechanism
    return settings


class BoundedObserver:
    """In-memory topic buffer used when no broker is contacted.

    A live broker read stays behind ``QA_MCP_LIVE_KAFKA`` and is not faked here.
    """

    def __init__(
        self,
        settings: Mapping[str, object],
        messages: Mapping[str, tuple[dict[str, str], ...]] | None = None,
        *,
        retention_gaps: frozenset[str] = frozenset(),
    ) -> None:
        if settings.get("enable.auto.commit") is not False:
            raise HubError("kafka_rejected", "auto commit must be disabled")
        self.settings = dict(settings)
        self._messages = dict(messages or {})
        self._gaps = retention_gaps
        self.offsets_committed = 0
        self.topics: list[str] = []

    def read_topic(
        self,
        topic: str,
        *,
        max_messages: int,
        timeout_seconds: float,
    ) -> TopicRead:
        """Return a capped slice. This method does not commit offsets."""
        if max_messages < 1 or max_messages > 200:
            raise HubError("kafka_rejected", "message cap is outside the allowed range")
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise HubError(
                "kafka_rejected", "kafka timeout is outside the allowed range"
            )
        self.topics.append(topic)
        available = self._messages.get(topic, ())
        selected = available[:max_messages]
        return TopicRead(
            messages=selected,
            offsets_committed=self.offsets_committed,
            retention_gap=topic in self._gaps,
            scanned=len(selected),
        )

    def commit(self) -> None:
        """Refuse to move a consumer group."""
        raise HubError("kafka_rejected", "observer does not commit offsets")


def open_observer(settings: Mapping[str, object]) -> TopicReader:
    """Refuse a live broker when the gated client is not enabled."""
    if settings.get("enable.auto.commit") is not False:
        raise HubError("kafka_rejected", "auto commit must be disabled")
    if os.environ.get("QA_MCP_LIVE_KAFKA") != "1":
        raise HubError(
            "infrastructure_unavailable",
            "live Kafka checks are not enabled",
        )
    raise HubError(
        "infrastructure_unavailable",
        "a Kafka client is not bundled for live checks",
    )
