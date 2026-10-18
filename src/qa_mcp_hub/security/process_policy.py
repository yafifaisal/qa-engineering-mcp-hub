"""Exact argv and environment rules for registered runners.

Purpose: keep process execution on an argument list with a small environment.
Milestone: 06
Status: IMPLEMENTED
Ownership: security.process_policy
Dependencies: Path allowlist and execution limits.
Expected tests: shell rejection, argument injection, and environment leaks.
"""

import os
import re
from pathlib import Path

from qa_mcp_hub.core.errors import HubError

_SAFE_ENV = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
)
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_OUTPUT_LIMIT = 1_048_576
_STORED_OUTPUT = 8_000


def output_limit() -> int:
    """Return the maximum combined output a runner may emit."""
    return _OUTPUT_LIMIT


def stored_output_limit() -> int:
    """Return the maximum output persisted on an execution record."""
    return _STORED_OUTPUT


def sanitized_env(extra: dict[str, str]) -> dict[str, str]:
    """Copy an allowlisted process environment and named extra variables."""
    env: dict[str, str] = {}
    for key in _SAFE_ENV:
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    for key, value in extra.items():
        if not _ENV_NAME.fullmatch(key) or "\x00" in value:
            raise HubError("unsafe_environment", "runner environment name is rejected")
        env[key] = value
    return env


def assert_executable(path: Path) -> Path:
    """Require one existing file. A path is not a shell expression."""
    if "\x00" in str(path) or any(token in path.name for token in ("&", "|", ";", "`")):
        raise HubError("unsafe_executable", "runner path is not a single executable")
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.is_file():
        raise HubError("runner_missing", "runner binary is not installed")
    return resolved


def assert_argument(value: str) -> None:
    """Reject a break or a shell metacharacter. Each argument stays one element."""
    if value == "" or any(character in value for character in "\x00\n\r&|;$`<>"):
        raise HubError("argv_rejected", "runner argument is empty or contains a break")
