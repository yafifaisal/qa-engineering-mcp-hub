"""Workspace lookup of reviewed assertions by stable id.

Purpose: load registered files and ignore disabled or unfinished ones.
Milestone: 07
Status: IMPLEMENTED
Ownership: verification.assertion_registry
Dependencies: Assertion models and path containment.
Expected tests: duplicate ids, isolation, and unsupported kinds.
"""

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.security.path_allowlist import resolve_within
from qa_mcp_hub.verification.models import AssertionDefinition

_KINDS = {
    "database": "assertions/database",
    "sql": "assertions/sql",
    "kafka": "assertions/kafka",
    "business": "assertions/business",
}
_MAX_FILES = 100
_MAX_BYTES = 65_536


def load_assertions(workspace: Path) -> dict[str, AssertionDefinition]:
    """Return enabled, implemented assertions inside the workspace."""
    found: dict[str, AssertionDefinition] = {}
    count = 0
    for kind, relative in _KINDS.items():
        root = workspace / relative
        if not root.exists():
            continue
        for path in sorted(root.glob("*.yaml")):
            count += 1
            if count > _MAX_FILES:
                raise HubError("assertion_limit", "assertion registry is too large")
            contained = resolve_within(path, [workspace])
            text = contained.read_text(encoding="utf-8")
            if len(text.encode("utf-8")) > _MAX_BYTES:
                raise HubError("assertion_limit", "assertion file is too large")
            loaded = yaml.safe_load(text)
            if not isinstance(loaded, dict):
                raise HubError("assertion_invalid", "assertion file is not a mapping")
            assertion = AssertionDefinition.model_validate(loaded)
            if assertion.kind != kind:
                raise HubError(
                    "assertion_invalid",
                    "assertion kind does not match its directory",
                )
            if assertion.id in found:
                raise HubError("duplicate_assertion", "duplicate assertion id")
            if assertion.enabled and assertion.implementation_status == "IMPLEMENTED":
                found[assertion.id] = assertion
    return found


def executable(
    assertions: dict[str, AssertionDefinition], assertion_id: str
) -> AssertionDefinition:
    """Return one registered assertion or a safe not-found error."""
    assertion = assertions.get(assertion_id)
    if assertion is None:
        raise HubError("assertion_not_registered", "assertion is not registered")
    return assertion
