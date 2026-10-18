"""Credential-aware redaction for diagnostic text and nested values.

Purpose: remove secrets from diagnostics while preserving opaque references.
Milestone: 01
Status: IMPLEMENTED
Ownership: auth.redaction
Dependencies: standard library text and URL parsing.
Expected tests: nested values, URLs, and authorization text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, SecretStr

REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "code_verifier",
    "cookie",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "set_cookie",
    "token",
    "access_token",
}
_REFERENCE_KEYS = {"credential_ref", "credential_reference", "reference"}
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|password|cookie)\b(\s*[:=]\s*)([^\s,;]+)"
)
_AUTH_PATTERN = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")
_URL_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
    re.DOTALL,
)


def _normalized_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")


def _is_sensitive_key(key: object) -> bool:
    normalized = _normalized_key(key)
    if normalized in _REFERENCE_KEYS:
        return False
    return normalized in _SENSITIVE_KEYS or any(
        normalized.endswith(f"_{suffix}")
        for suffix in ("password", "secret", "token", "api_key", "private_key")
    )


def _redact_url(match: re.Match[str]) -> str:
    raw_url = match.group(0)
    trailing = ""
    while raw_url and raw_url[-1] in ".,;)]":
        trailing = raw_url[-1] + trailing
        raw_url = raw_url[:-1]
    try:
        parts = urlsplit(raw_url)
        host = parts.hostname or ""
        if parts.port is not None:
            host = f"{host}:{parts.port}"
        netloc = host
        if parts.username is not None or parts.password is not None:
            netloc = f"{REDACTED}@{host}"
        query = urlencode(
            [
                (key, REDACTED if _is_sensitive_key(key) else value)
                for key, value in parse_qsl(parts.query, keep_blank_values=True)
            ]
        )
        return (
            urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))
            + trailing
        )
    except ValueError:
        return REDACTED + trailing


def redact_text(text: str, *, secrets: Sequence[str] = ()) -> str:
    """Redact known values and common credential-bearing text forms."""
    redacted = text
    for secret in sorted({value for value in secrets if value}, key=len, reverse=True):
        redacted = redacted.replace(secret, REDACTED)
    redacted = _PRIVATE_KEY_PATTERN.sub(REDACTED, redacted)
    redacted = _AUTH_PATTERN.sub(lambda match: f"{match.group(1)} {REDACTED}", redacted)
    redacted = _ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
        redacted,
    )
    return _URL_PATTERN.sub(_redact_url, redacted)


def redact(value: Any, *, secrets: Sequence[str] = ()) -> Any:
    """Return a recursively redacted, presentation-safe copy of ``value``."""
    if isinstance(value, SecretStr):
        return REDACTED
    if isinstance(value, (bytes, bytearray)):
        return REDACTED
    if isinstance(value, BaseModel):
        return redact(value.model_dump(mode="python"), secrets=secrets)
    if isinstance(value, Mapping):
        return {
            key: REDACTED if _is_sensitive_key(key) else redact(item, secrets=secrets)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact(item, secrets=secrets) for item in value)
    if isinstance(value, list):
        return [redact(item, secrets=secrets) for item in value]
    if isinstance(value, set):
        return {redact(item, secrets=secrets) for item in value}
    if isinstance(value, str):
        return redact_text(value, secrets=secrets)
    return value


redact_value = redact
