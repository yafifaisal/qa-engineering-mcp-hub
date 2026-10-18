"""Checks that a suite cannot become an unrestricted process.

Purpose: reject shell text, unsafe paths, and unknown runners.
Milestone: 06
Status: IMPLEMENTED
Ownership: suites.validator
Dependencies: Suite models and the path allowlist.
Expected tests: shell rejection, unsafe paths, and environment names.
"""

import re
from pathlib import Path

from qa_mcp_hub.core.errors import HubError, PathAllowlistError
from qa_mcp_hub.security.path_allowlist import resolve_within
from qa_mcp_hub.suites.models import SuiteDefinition

_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ENV = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHELL = set("&|;$`<>\n\r\x00")


def assert_safe_token(value: str, label: str) -> None:
    """Reject a token that could change a shell command."""
    if not value or any(character in _SHELL for character in value):
        raise HubError("unsafe_token", f"{label} contains an unsupported character")


def validate_suite(suite: SuiteDefinition, workspace: Path) -> Path:
    """Resolve a suite path inside the workspace or reject it."""
    if not _ID.fullmatch(suite.id):
        raise HubError("invalid_suite", "suite id is not a stable identifier")
    if not suite.version or len(suite.version) > 64:
        raise HubError("invalid_suite", "suite version is missing")
    assert_safe_token(suite.version, "suite version")
    if suite.environment is not None and not _ENV.fullmatch(suite.environment):
        raise HubError("unsupported_environment", "suite environment is not allowed")
    if suite.runner not in {"bruno", "postman"}:
        raise HubError("invalid_suite", "suite runner is not registered")
    if any(character in _SHELL for character in suite.path) or suite.path.startswith(
        ("/", "\\")
    ):
        raise HubError("unsafe_path", "suite path must stay inside the workspace")
    for assertion_id in suite.assertion_ids:
        if not _ID.fullmatch(assertion_id):
            raise HubError("invalid_suite", "assertion id is not stable")
    for binding in suite.credential_env:
        if not _ENV_NAME.fullmatch(binding.name) or not _REFERENCE.fullmatch(
            binding.reference
        ):
            raise HubError("invalid_suite", "credential binding is not a reference")
    try:
        resolved = resolve_within(workspace / suite.path, (workspace,))
    except PathAllowlistError as exc:
        raise HubError("unsafe_path", exc.message) from exc
    return resolved
