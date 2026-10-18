"""Correlation keys declared by registered assertions.

Purpose: accept only approved keys and compare observed values.
Milestone: 07
Status: IMPLEMENTED
Ownership: verification.correlation
Dependencies: Assertion definitions.
Expected tests: missing keys, rejected keys, and value mismatch.
"""

import re

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.verification.models import AssertionDefinition

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def declared_keys(assertions: tuple[AssertionDefinition, ...]) -> frozenset[str]:
    """Collect parameter and correlation names from registered assertions."""
    keys: set[str] = set()
    for assertion in assertions:
        raw = assertion.definition.get("parameters")
        if isinstance(raw, list):
            keys.update(str(item) for item in raw)
        key = assertion.definition.get("correlation_key")
        if isinstance(key, str):
            keys.add(key)
    return frozenset(keys)


def clean_correlation(
    provided: dict[str, str],
    *,
    declared: frozenset[str],
) -> dict[str, str]:
    """Keep declared keys and reject undeclared or unsafe values."""
    unknown = set(provided) - declared
    if unknown:
        raise HubError("correlation_rejected", "correlation key is not declared")
    cleaned: dict[str, str] = {}
    for key, value in provided.items():
        if _NAME.fullmatch(key) is None:
            raise HubError("correlation_rejected", "correlation key is not declared")
        if not isinstance(value, str) or not value or len(value) > 200:
            raise HubError("correlation_rejected", "correlation value is not allowed")
        if any(character in value for character in ("\x00", "\n", "\r")):
            raise HubError("correlation_rejected", "correlation value is not allowed")
        cleaned[key] = value
    return cleaned


def require_keys(values: dict[str, str], required: tuple[str, ...]) -> dict[str, str]:
    """Return the required subset or report a missing approved key."""
    missing = [key for key in required if key not in values]
    if missing:
        raise HubError("correlation_missing", "correlation key was not supplied")
    return {key: values[key] for key in required}


def matches(expected: str, actual: str | None) -> bool:
    """Compare one observed value with the approved correlation value."""
    return actual is not None and actual == expected
