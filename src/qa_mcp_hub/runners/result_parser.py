"""Parsers for pinned Bruno and Newman JSON reporters.

Purpose: read assertion results without starting a runner.
Milestone: 06
Status: IMPLEMENTED
Ownership: runners.result_parser
Dependencies: Bounded reporter text.
Expected tests: valid, malformed, and empty assertion reports.
"""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

_MAX_REPORT = 1_048_576


class ParsedAssertion(BaseModel):
    """One assertion named by a reporter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    passed: bool


class ParsedReport(BaseModel):
    """Reporter output. A summary count without names is not an assertion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    valid: bool
    assertions: tuple[ParsedAssertion, ...] = ()
    reason: str | None = None


def parse_report(kind: Literal["bruno", "postman"], text: str) -> ParsedReport:
    """Parse one reporter document for the suite's runner."""
    if len(text.encode("utf-8")) > _MAX_REPORT:
        return ParsedReport(valid=False, reason="invalid_reporter")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ParsedReport(valid=False, reason="invalid_reporter")
    if not isinstance(payload, dict):
        return ParsedReport(valid=False, reason="invalid_reporter")
    if kind == "bruno":
        return _parse_bruno(payload)
    return _parse_newman(payload)


def _parse_bruno(payload: dict[str, object]) -> ParsedReport:
    results = payload.get("results")
    assertions: list[ParsedAssertion] = []
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            for key in ("assertionResults", "testResults"):
                rows = item.get(key)
                assertions.extend(_bruno_rows(rows))
    if assertions:
        return ParsedReport(valid=True, assertions=tuple(assertions))
    summary = payload.get("summary")
    if isinstance(summary, dict):
        failed = _count(summary.get("failedAssertions"))
        if failed > 0:
            return ParsedReport(
                valid=True,
                assertions=tuple(
                    ParsedAssertion(name=f"summary-{index}", passed=False)
                    for index in range(failed)
                ),
                reason="assertions_not_itemized",
            )
    return ParsedReport(valid=True, reason="no_assertions")


def _bruno_rows(rows: object) -> list[ParsedAssertion]:
    if not isinstance(rows, list):
        return []
    parsed: list[ParsedAssertion] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "")).lower()
        if status not in {"pass", "passed", "fail", "failed", "error"}:
            continue
        name = row.get("description") or row.get("name") or "assertion"
        parsed.append(
            ParsedAssertion(name=str(name)[:200], passed=status in {"pass", "passed"})
        )
    return parsed


def _parse_newman(payload: dict[str, object]) -> ParsedReport:
    run = payload.get("run")
    if not isinstance(run, dict):
        return ParsedReport(valid=False, reason="invalid_reporter")
    executions = run.get("executions")
    assertions: list[ParsedAssertion] = []
    if isinstance(executions, list):
        for execution in executions:
            if not isinstance(execution, dict):
                continue
            rows = execution.get("assertions")
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict) or row.get("skipped") is True:
                    continue
                name = str(row.get("assertion") or "assertion")[:200]
                failed = row.get("error") not in (None, "")
                assertions.append(ParsedAssertion(name=name, passed=not failed))
    if not assertions:
        return ParsedReport(valid=True, reason="no_assertions")
    return ParsedReport(valid=True, assertions=tuple(assertions))


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)
