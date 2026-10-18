"""Scan source and package artifacts for credential-shaped text.

Purpose: reject known token shapes before a community artifact is retained.
Milestone: 11
Status: IMPLEMENTED
Ownership: security.secret_scanner
Dependencies: the standard library only.
Expected tests: token shapes, archive paths, and clean packages.
"""

from __future__ import annotations

import re
import tarfile
import zipfile
from pathlib import Path

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[opusr]_[A-Za-z0-9]{30,}\b")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "assigned secret",
        re.compile(
            r"(?i)\b(?:password|secret|api_key|access_token)\s*=\s*"
            r"['\"](?!qa_mcp_)[A-Za-z0-9+/=_-]{12,}['\"]"
        ),
    ),
)
_UNSAFE_NAME = re.compile(
    r"(^|/)\.\.(?:/|$)|(?:^|/)(?:\.env|id_rsa|credentials\.json)(?:$|\.)|\.pem$",
    re.IGNORECASE,
)


def findings_in_text(text: str) -> tuple[str, ...]:
    """Return pattern labels found in one decoded document."""
    return tuple(label for label, pattern in _PATTERNS if pattern.search(text))


def _name_finding(name: str) -> str | None:
    normalized = name.replace("\\", "/")
    if _UNSAFE_NAME.search(normalized):
        return f"unsafe archive path: {normalized}"
    return None


def _text_findings(name: str, payload: bytes) -> tuple[str, ...]:
    if b"\x00" in payload[:1024]:
        return ()
    labels = findings_in_text(payload.decode("utf-8", errors="replace"))
    return tuple(f"{label} in {name}" for label in labels)


def scan_distribution(path: Path) -> tuple[str, ...]:
    """Scan a wheel or source distribution for unsafe paths and token shapes."""
    findings: list[str] = []
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                named = _name_finding(info.filename)
                if named is not None:
                    findings.append(named)
                if not info.is_dir():
                    findings.extend(_text_findings(info.filename, archive.read(info)))
        return tuple(findings)
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                named = _name_finding(member.name)
                if named is not None:
                    findings.append(named)
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                findings.extend(_text_findings(member.name, extracted.read()))
        return tuple(findings)
    raise ValueError(f"unsupported distribution: {path.name}")
