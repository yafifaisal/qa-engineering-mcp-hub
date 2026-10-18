#!/usr/bin/env python3
"""Audit the canonical repository structure and generate deterministic reports.

Purpose: enforce the Milestone 00 scaffold manifest and safety invariants.
Milestone: 00
Status: IMPLEMENTED
Ownership: scripts.structure_audit
Dependencies: Python 3.12, PyYAML, jsonschema, and the local FastMCP package.
Expected tests: exercised as a quality gate against known-good and fixture failures.
"""

from __future__ import annotations

import ast
import asyncio
import json
import math
import re
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml
from fastmcp import Client
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

ROOT = Path(__file__).resolve().parents[1]
HUMAN_MANIFEST = ROOT / "docs/implementation/SCAFFOLD_MANIFEST.md"
JSON_REPORT = ROOT / "docs/implementation/STRUCTURE_AUDIT.json"
MARKDOWN_REPORT = ROOT / "docs/implementation/STRUCTURE_AUDIT.md"

IGNORED_PARTS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
}
SECRET_NAME_PARTS = {
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
}
SAFE_SECRET_MARKERS = {
    "",
    "changeme",
    "example",
    "not-set",
    "placeholder",
    "redacted",
    "unset",
}
KNOWN_SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GitHub token": re.compile(r"\bgh[opusr]_[A-Za-z0-9]{30,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
MANIFEST_POINTER = re.compile(r"Machine manifest:\s*`([^`]+)`")


@dataclass(frozen=True)
class Finding:
    """One deterministic audit finding."""

    check: str
    path: str
    message: str
    severity: str = "ERROR"


def relative(path: Path) -> str:
    """Return a stable POSIX repository-relative path."""
    return path.relative_to(ROOT).as_posix()


def load_manifest() -> tuple[dict[str, Any], Path]:
    """Read the human manifest first, then its declared machine manifest."""
    human_text = HUMAN_MANIFEST.read_text(encoding="utf-8")
    match = MANIFEST_POINTER.search(human_text)
    if match is None:
        raise ValueError("SCAFFOLD_MANIFEST.md has no machine manifest pointer")
    machine_path = (ROOT / match.group(1)).resolve()
    if ROOT not in machine_path.parents:
        raise ValueError("machine manifest must remain inside the repository")
    payload = yaml.safe_load(machine_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("machine manifest root must be a mapping")
    return payload, machine_path


def expected_files(manifest: dict[str, Any]) -> tuple[dict[str, str], set[str]]:
    """Flatten status groups and reject duplicate manifest entries."""
    groups = manifest.get("files")
    if not isinstance(groups, dict):
        raise ValueError("manifest files must be grouped by status")
    statuses: dict[str, str] = {}
    duplicates: set[str] = set()
    for status, paths in groups.items():
        if not isinstance(paths, list):
            raise ValueError(f"manifest status {status!r} must contain a list")
        for path in paths:
            if not isinstance(path, str):
                raise ValueError("manifest paths must be strings")
            if path in statuses:
                duplicates.add(path)
            statuses[path] = str(status)
    return statuses, duplicates


def actual_files() -> set[str]:
    """List source-controlled candidates while excluding generated environments."""
    found: set[str] = set()
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        found.add(relative(path))
    return found


def python_is_placeholder(path: Path) -> bool:
    """Use the AST to recognize modules containing only documentation metadata."""
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    body = list(module.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
    ):
        if isinstance(body[0].value.value, str):
            body.pop(0)
    for node in body:
        if isinstance(node, ast.Assign):
            if all(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                continue
        return False
    return True


def parse_ownership(path: Path) -> str | None:
    """Read declared module ownership from the AST docstring."""
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstring = ast.get_docstring(module, clean=False) or ""
    for line in docstring.splitlines():
        if line.strip().startswith("Ownership:"):
            return line.split(":", maxsplit=1)[1].strip()
    return None


def config_parse_findings(files: set[str]) -> list[Finding]:
    """Parse every YAML, JSON, and TOML source document."""
    findings: list[Finding] = []
    for name in sorted(files):
        path = ROOT / name
        try:
            if path.suffix in {".yaml", ".yml"}:
                yaml.safe_load(path.read_text(encoding="utf-8"))
            elif path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".toml":
                tomllib.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, tomllib.TOMLDecodeError, yaml.YAMLError) as exc:
            findings.append(Finding("config-parse", name, str(exc)))
    return findings


def schema_findings(manifest: dict[str, Any]) -> list[Finding]:
    """Validate declared YAML documents against real Draft 2020-12 schemas."""
    findings: list[Finding] = []
    for schema_name in manifest.get("json_schemas", []):
        try:
            schema = json.loads((ROOT / schema_name).read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except (OSError, SchemaError, json.JSONDecodeError) as exc:
            findings.append(
                Finding("schema-definition", schema_name, f"invalid schema: {exc}")
            )
    validations = manifest.get("schema_validations", [])
    for pair in validations:
        document_name = pair["document"]
        schema_name = pair["schema"]
        try:
            schema = json.loads((ROOT / schema_name).read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            document = yaml.safe_load(
                (ROOT / document_name).read_text(encoding="utf-8")
            )
            Draft202012Validator(schema).validate(document)
        except (
            OSError,
            SchemaError,
            ValidationError,
            json.JSONDecodeError,
            yaml.YAMLError,
        ) as exc:
            findings.append(
                Finding(
                    "schema-validation",
                    document_name,
                    f"does not validate against {schema_name}: {exc}",
                )
            )
    return findings


def markdown_link_findings(files: set[str]) -> list[Finding]:
    """Detect missing local Markdown link targets."""
    findings: list[Finding] = []
    for name in sorted(path for path in files if path.endswith(".md")):
        source = ROOT / name
        for raw_target in MARKDOWN_LINK.findall(source.read_text(encoding="utf-8")):
            target = raw_target.strip().strip("<>").split(maxsplit=1)[0]
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            file_part = unquote(target.split("#", maxsplit=1)[0])
            if not file_part:
                continue
            resolved = (source.parent / file_part).resolve()
            if ROOT != resolved and ROOT not in resolved.parents:
                findings.append(
                    Finding("local-link", name, f"link escapes repository: {target}")
                )
            elif not resolved.exists():
                findings.append(
                    Finding("local-link", name, f"missing link target: {target}")
                )
    return findings


def has_sensitive_name(name: str) -> bool:
    """Recognize secret-bearing identifier names by semantic components."""
    lowered = name.casefold().replace("-", "_")
    return any(part in lowered for part in SECRET_NAME_PARTS)


def looks_like_placeholder(value: str) -> bool:
    """Allow explicit references and unmistakable example markers."""
    lowered = value.strip().casefold()
    return (
        lowered in SAFE_SECRET_MARKERS
        or lowered.startswith(("env:", "keyring:", "${", "qa_mcp_"))
        or "example" in lowered
        or "placeholder" in lowered
        or lowered.endswith(("_token", "_password", "_secret"))
    )


def shannon_entropy(value: str) -> float:
    """Calculate string entropy for structured secret-value inspection."""
    if not value:
        return 0.0
    counts = Counter(value)
    return -sum(
        (count / len(value)) * math.log2(count / len(value))
        for count in counts.values()
    )


def structured_secret_values(value: Any, trail: tuple[str, ...] = ()) -> list[str]:
    """Find suspicious values under semantically sensitive structured keys."""
    suspicious: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            name = str(key)
            if isinstance(child, str) and has_sensitive_name(name):
                if not looks_like_placeholder(child) and (
                    len(child) >= 12 or shannon_entropy(child) >= 3.5
                ):
                    suspicious.append(".".join((*trail, name)))
            suspicious.extend(structured_secret_values(child, (*trail, name)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            suspicious.extend(structured_secret_values(child, (*trail, str(index))))
    return suspicious


def python_secret_findings(path: Path) -> list[Finding]:
    """Inspect AST assignments rather than relying only on token regexes."""
    findings: list[Finding] = []
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(module):
        name: str | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                name, value = target.id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name, value = node.target.id, node.value
        if (
            name is not None
            and value is not None
            and has_sensitive_name(name)
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and not looks_like_placeholder(value.value)
            and (len(value.value) >= 12 or shannon_entropy(value.value) >= 3.5)
        ):
            findings.append(
                Finding(
                    "secret-ast",
                    relative(path),
                    f"suspicious literal assigned to {name} on line {node.lineno}",
                )
            )
    return findings


def secret_findings(files: set[str]) -> list[Finding]:
    """Combine AST, structured-data, and known-format secret detection."""
    findings: list[Finding] = []
    for name in sorted(files):
        path = ROOT / name
        if name == "uv.lock" or path.suffix in {".css", ".lock"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".py":
            findings.extend(python_secret_findings(path))
        if path.suffix in {".yaml", ".yml", ".json"}:
            try:
                data = (
                    json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
                )
            except (json.JSONDecodeError, yaml.YAMLError):
                data = None
            for trail in structured_secret_values(data):
                findings.append(
                    Finding(
                        "secret-structured",
                        name,
                        f"suspicious value at {trail}",
                    )
                )
        for label, pattern in KNOWN_SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(Finding("secret-pattern", name, f"possible {label}"))
    return findings


async def discover_mcp_components() -> dict[str, list[str]]:
    """Query the real local FastMCP registry through its client protocol."""
    from qa_mcp_hub.app import mcp

    async with Client(mcp) as client:
        return {
            "tools": sorted(tool.name for tool in await client.list_tools()),
            "resources": sorted(
                str(item.uri) for item in await client.list_resources()
            ),
            "prompts": sorted(prompt.name for prompt in await client.list_prompts()),
        }


def mcp_findings(
    manifest: dict[str, Any],
) -> tuple[list[Finding], dict[str, list[str]]]:
    """Detect planned MCP components accidentally exposed at runtime."""
    expected = manifest.get("expected_mcp", {})
    discovered = asyncio.run(discover_mcp_components())
    findings: list[Finding] = []
    for kind in ("tools", "resources", "prompts"):
        expected_values = sorted(expected.get(kind, []))
        if discovered[kind] != expected_values:
            findings.append(
                Finding(
                    "mcp-exposure",
                    "src/qa_mcp_hub/app.py",
                    f"{kind}: expected {expected_values}, found {discovered[kind]}",
                )
            )
    return findings, discovered


def audit(manifest: dict[str, Any]) -> tuple[list[Finding], dict[str, Any]]:
    """Run every deterministic structure and safety check."""
    findings: list[Finding] = []
    statuses, manifest_duplicates = expected_files(manifest)
    allowed_empty = set(manifest.get("allowed_empty", []))
    actual = actual_files()
    expected = set(statuses)

    for name in sorted(manifest_duplicates):
        findings.append(Finding("manifest-duplicate", name, "listed more than once"))
    for name in sorted(expected - actual):
        findings.append(Finding("missing-file", name, "required file is absent"))
    for name in sorted(actual - expected):
        findings.append(Finding("unlisted-file", name, "file is not in the manifest"))

    expected_directories = {
        parent.as_posix()
        for name in expected
        for parent in Path(name).parents
        if parent.as_posix() != "."
    }
    for name in sorted(expected_directories):
        if not (ROOT / name).is_dir():
            findings.append(Finding("missing-directory", name, "directory is absent"))

    ownership: defaultdict[str, list[str]] = defaultdict(list)
    for name in sorted(expected & actual):
        path = ROOT / name
        if path.stat().st_size == 0 and name not in allowed_empty:
            findings.append(Finding("zero-byte", name, "zero-byte file is not allowed"))
        if path.suffix == ".md" and not path.read_text(encoding="utf-8").strip():
            findings.append(Finding("empty-markdown", name, "Markdown file is empty"))
        if path.suffix == ".py":
            try:
                placeholder = python_is_placeholder(path)
                status = statuses[name]
                if (
                    placeholder
                    and status != "SCAFFOLDED"
                    and path.name != "__init__.py"
                ):
                    findings.append(
                        Finding(
                            "python-placeholder",
                            name,
                            f"placeholder module has status {status}",
                        )
                    )
                if name.startswith("src/qa_mcp_hub/") and path.name != "__init__.py":
                    owner = parse_ownership(path)
                    if owner is None:
                        findings.append(
                            Finding(
                                "missing-ownership",
                                name,
                                "module docstring has no Ownership metadata",
                            )
                        )
                    else:
                        ownership[owner].append(name)
            except SyntaxError as exc:
                findings.append(Finding("python-syntax", name, str(exc)))

    for owner, paths in sorted(ownership.items()):
        if len(paths) > 1:
            findings.append(
                Finding(
                    "duplicate-ownership",
                    ", ".join(paths),
                    f"ownership {owner!r} is declared by multiple modules",
                )
            )

    findings.extend(config_parse_findings(expected & actual))
    findings.extend(schema_findings(manifest))
    findings.extend(markdown_link_findings(expected & actual))
    findings.extend(secret_findings(expected & actual))
    mcp_issues, discovered = mcp_findings(manifest)
    findings.extend(mcp_issues)

    counts = {
        "expected_files": len(expected),
        "existing_expected_files": len(expected & actual),
        "missing_files": len(expected - actual),
        "unlisted_files": len(actual - expected),
        "expected_directories": len(expected_directories),
        "missing_directories": sum(
            not (ROOT / name).is_dir() for name in expected_directories
        ),
        "zero_byte_files": sum(
            (ROOT / name).stat().st_size == 0
            for name in expected & actual
            if name not in allowed_empty
        ),
        "findings": len(findings),
    }
    evidence = {
        "manifest_version": manifest.get("version"),
        "counts": counts,
        "mcp_discovery": discovered,
        "status": "PASS" if not findings else "FAIL",
    }
    return findings, evidence


def write_reports(findings: list[Finding], evidence: dict[str, Any]) -> None:
    """Write stable machine-readable JSON and human Markdown summaries."""
    report = {**evidence, "findings": [asdict(item) for item in findings]}
    JSON_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    counts = evidence["counts"]
    lines = [
        "# Structure audit",
        "",
        "Generated by `scripts/structure_audit.py` from the canonical scaffold "
        "manifest.",
        "",
        f"Result: **{evidence['status']}**",
        "",
        "| Measure | Count |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {name.replace('_', ' ').title()} | {value} |"
        for name, value in counts.items()
    )
    lines.extend(
        [
            "",
            "## MCP discovery",
            "",
            f"- Tools: `{', '.join(evidence['mcp_discovery']['tools'])}`",
            f"- Resources: `{', '.join(evidence['mcp_discovery']['resources'])}`",
            f"- Prompts: `{', '.join(evidence['mcp_discovery']['prompts'])}`",
            "",
            "## Findings",
            "",
        ]
    )
    if findings:
        lines.extend(
            f"- **{item.severity} / {item.check}:** `{item.path}` — {item.message}"
            for item in findings
        )
    else:
        lines.append("No mandatory violations detected.")
    lines.extend(
        [
            "",
            "The JSON evidence is in [`STRUCTURE_AUDIT.json`](STRUCTURE_AUDIT.json).",
            "",
        ]
    )
    MARKDOWN_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    """Run the audit and return non-zero when mandatory violations exist."""
    try:
        manifest, machine_path = load_manifest()
        findings, evidence = audit(manifest)
        evidence["machine_manifest"] = relative(machine_path)
        write_reports(findings, evidence)
    except Exception as exc:  # noqa: BLE001 - audit must render an explicit failure
        failure = Finding("audit-runtime", "scripts/structure_audit.py", str(exc))
        write_reports(
            [failure],
            {
                "manifest_version": None,
                "counts": {
                    "expected_files": 0,
                    "existing_expected_files": 0,
                    "missing_files": 0,
                    "unlisted_files": 0,
                    "expected_directories": 0,
                    "missing_directories": 0,
                    "zero_byte_files": 0,
                    "findings": 1,
                },
                "mcp_discovery": {"tools": [], "resources": [], "prompts": []},
                "status": "FAIL",
            },
        )
        print(f"Structure audit failed to run: {exc}", file=sys.stderr)
        return 2

    print(
        f"Structure audit {evidence['status']}: "
        f"{evidence['counts']['findings']} finding(s)"
    )
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
