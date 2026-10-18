"""Render evidence HTML with escaping and a fixed template subset.

Purpose: fill the checked-in templates without executing template code.
Milestone: 10
Status: IMPLEMENTED
Ownership: evidence.renderer
Dependencies: Evidence models and the HTML templates.
Expected tests: escaping, summary counts, and unsupported expressions.
"""

import html
import re
from pathlib import Path

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.evidence.models import EvidenceCheckStatus, EvidenceManifest

_IF = re.compile(
    r"\{%\s*if\s+([A-Za-z0-9_.]+)\s*%\}(.*?)\{%\s*endif\s*%\}",
    re.DOTALL,
)
_FOR = re.compile(
    r"\{%\s*for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([A-Za-z0-9_.]+)\s*%\}"
    r"(.*?)\{%\s*endfor\s*%\}",
    re.DOTALL,
)
_VAR = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*(\|\s*e\s*)?\}\}")


def template_dir() -> Path:
    """Return the repository evidence template directory."""
    root = Path(__file__).resolve().parents[3] / "templates" / "evidence"
    if not root.is_dir():
        raise HubError("mapping_rejected", "evidence templates are missing")
    return root


def render_report(manifest: EvidenceManifest) -> str:
    """Render the full report. Check text is escaped."""
    text = (template_dir() / "report.html.j2").read_text(encoding="utf-8")
    return _render(text, {"report": _report_view(manifest)})


def render_summary(manifest: EvidenceManifest) -> str:
    """Render the summary fragment."""
    text = (template_dir() / "summary.html.j2").read_text(encoding="utf-8")
    return _render(text, {"summary": _summary_view(manifest)})


def _report_view(manifest: EvidenceManifest) -> dict[str, object]:
    return {
        "title": f"Evidence {manifest.execution_id}",
        "status": manifest.overall.value,
        "execution_id": manifest.execution_id,
        "summary": _summary_sentence(manifest),
        "checks": [
            {
                "name": item.name,
                "result": item.result.value,
                "evidence_reference": item.evidence_reference,
            }
            for item in manifest.checks
        ],
    }


def _summary_view(manifest: EvidenceManifest) -> dict[str, object]:
    return {
        "title": f"Evidence {manifest.execution_id}",
        "status": manifest.overall.value,
        "passed_count": _count(manifest, EvidenceCheckStatus.passed),
        "failed_count": _count(manifest, EvidenceCheckStatus.failed),
        "inconclusive_count": _count(manifest, EvidenceCheckStatus.inconclusive),
        "limitations": list(manifest.limitations),
    }


def _summary_sentence(manifest: EvidenceManifest) -> str:
    return (
        f"Profile {manifest.profile_id}, suite {manifest.suite_version}, "
        f"revision {manifest.source_revision}."
    )


def _count(manifest: EvidenceManifest, status: EvidenceCheckStatus) -> int:
    return sum(1 for item in manifest.checks if item.result is status)


def _render(text: str, context: dict[str, object]) -> str:
    rendered = _IF.sub(lambda match: _if_block(match, context), text)
    rendered = _FOR.sub(lambda match: _for_block(match, context), rendered)
    rendered = _VAR.sub(lambda match: _value(match, context), rendered)
    if "{{" in rendered or "{%" in rendered:
        raise HubError("mapping_rejected", "template expression is not supported")
    return rendered


def _if_block(match: re.Match[str], context: dict[str, object]) -> str:
    value = _lookup(match.group(1), context)
    if not value:
        return ""
    return _render(match.group(2), context)


def _for_block(match: re.Match[str], context: dict[str, object]) -> str:
    items = _lookup(match.group(2), context)
    if not isinstance(items, list):
        raise HubError("mapping_rejected", "template loop target is invalid")
    parts: list[str] = []
    for item in items:
        child = dict(context)
        child[match.group(1)] = item
        parts.append(_render(match.group(3), child))
    return "".join(parts)


def _value(match: re.Match[str], context: dict[str, object]) -> str:
    value = _lookup(match.group(1), context)
    if isinstance(value, bool) or value is None:
        raise HubError("mapping_rejected", "template value is invalid")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return html.escape(value, quote=True)
    raise HubError("mapping_rejected", "template value is invalid")


def _lookup(path: str, context: dict[str, object]) -> object:
    current: object = context
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise HubError("mapping_rejected", "template field is missing")
    return current
