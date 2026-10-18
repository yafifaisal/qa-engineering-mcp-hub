"""Render a release report as JSON and escaped HTML.

Purpose: show the recommendation and keep approval false in both formats.
Milestone: 10
Status: IMPLEMENTED
Ownership: release.report_builder
Dependencies: Release report model.
Expected tests: escaped text and a false approval flag.
"""

import html
import json

from qa_mcp_hub.release.models import ReleaseReport


def report_json(report: ReleaseReport) -> bytes:
    """Serialize a report. ``release_approved`` is false."""
    payload = report.model_dump(mode="json")
    payload["release_approved"] = False
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def report_html(report: ReleaseReport) -> bytes:
    """Render escaped HTML. The page does not mark the release approved."""
    reasons = "".join(f"<li>{html.escape(item)}</li>" for item in report.reasons)
    percent = (
        "not recorded"
        if report.coverage_percent is None
        else str(report.coverage_percent)
    )
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{html.escape(report.execution_id)}</title></head><body>"
        f"<h1>{html.escape(report.recommendation)}</h1>"
        f"<p>Review: {html.escape(report.review_state.value)}</p>"
        "<p>Release approved: false</p>"
        f"<p>Coverage: {html.escape(percent)}</p><ul>{reasons}</ul></body></html>"
    )
    return document.encode("utf-8")
