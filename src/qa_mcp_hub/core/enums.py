"""Framework enumerations shared by provider-neutral contracts.

Purpose: publish categorical values for results, provider categories, and indexing.
Milestone: 02
Status: IMPLEMENTED
Ownership: core.enums
Dependencies: Python standard library only.
Expected tests: stable values, exhaustive serialization, and compatibility.
"""

from enum import StrEnum


class EpistemicStatus(StrEnum):
    """How strongly a result is grounded in inspected evidence."""

    verified = "VERIFIED"
    inferred = "INFERRED"
    unknown = "UNKNOWN"
    conflicting = "CONFLICTING"


class OperationStatus(StrEnum):
    """Outcome of one provider or repository operation."""

    success = "success"
    failed = "failed"
    not_implemented = "not_implemented"
    unsupported = "unsupported"
    available = "available"


class ProviderCategory(StrEnum):
    """Capability families in the canonical provider catalog."""

    git = "git"
    tickets = "tickets"
    documentation = "documentation"
    api_automation = "api_automation"
    database = "database"
    streaming = "streaming"
    cicd = "cicd"
    test_management = "test_management"


class IndexingPermission(StrEnum):
    """Explicit permission recorded for a later indexing milestone."""

    none = "none"
    metadata_only = "metadata_only"
    content = "content"
