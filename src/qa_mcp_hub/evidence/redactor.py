"""Redact secrets, tokens, cookies, PII, and sensitive financial text.

Purpose: sanitize evidence text before it is rendered or stored.
Milestone: 10
Status: IMPLEMENTED
Ownership: evidence.redactor
Dependencies: Auth redaction.
Expected tests: tokens, email, card numbers, and residual-secret failure.
"""

import re

from qa_mcp_hub.auth.redaction import REDACTED, redact_text

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_ACCOUNT = re.compile(r"(?i)\b(account|iban|card)\b(\s*[:=]\s*)([A-Za-z0-9-]{6,})")
_RESIDUAL = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._~+/=-]{8,}|password\s*[:=]\s*\S+|cookie\s*[:=]\s*\S+)"
)
_ASSIGNED = re.compile(
    r"(?i)\b(token|secret|password|cookie|authorization)\b(\s*[:=]\s*)(\S+)"
)


def redact_evidence(text: str, *, strict: bool) -> tuple[str, bool]:
    """Return sanitized text and whether a sensitive value remained."""
    detected = text != redact_text(text)
    redacted = redact_text(text)
    redacted = _ASSIGNED.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
        redacted,
    )

    def _mark(match: re.Match[str]) -> str:
        nonlocal detected
        detected = True
        return REDACTED

    redacted = _EMAIL.sub(_mark, redacted)
    redacted = _SSN.sub(_mark, redacted)
    redacted = _ACCOUNT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
        redacted,
    )
    if _CARD.search(redacted):
        detected = True
        redacted = _CARD.sub(REDACTED, redacted)
    if strict:
        return "", detected
    return redacted, _RESIDUAL.search(redacted) is not None
