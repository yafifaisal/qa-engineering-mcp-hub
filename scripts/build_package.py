#!/usr/bin/env python3
"""Build the Community Edition distributions, SBOM, and inspection report.

Purpose: produce a reviewable package without publishing it.
Milestone: 11
Status: IMPLEMENTED
Ownership: scripts.package_builder
Dependencies: uv, the locked metadata, and the secret scanner.
Expected tests: SBOM contents, clean distributions, and no publish step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tomllib
import urllib.request
from pathlib import Path
from typing import Any

from qa_mcp_hub.security.secret_scanner import scan_distribution

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "qa-engineering-mcp-hub"
PACKAGE_VERSION = "0.1.0"


def locked_packages(lock_path: Path) -> tuple[dict[str, str], ...]:
    """Return name, version, and sdist digest rows from the lockfile."""
    document = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for package in document.get("package", ()):
        name = str(package["name"])
        version = str(package["version"])
        identity = (name, version)
        if identity in seen:
            continue
        seen.add(identity)
        sdist = package.get("sdist") or {}
        digest = str(sdist.get("hash", "")).removeprefix("sha256:")
        rows.append({"name": name, "version": version, "sha256": digest})
    return tuple(sorted(rows, key=lambda item: item["name"]))


def write_sbom(lock_path: Path, destination: Path) -> Path:
    """Write a CycloneDX 1.5 document for the locked Python packages."""
    components = []
    for package in locked_packages(lock_path):
        component: dict[str, Any] = {
            "type": "library",
            "name": package["name"],
            "version": package["version"],
            "purl": f"pkg:pypi/{package['name']}@{package['version']}",
        }
        if package["sha256"]:
            component["hashes"] = [{"alg": "SHA-256", "content": package["sha256"]}]
        components.append(component)
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": PACKAGE_NAME,
                "version": PACKAGE_VERSION,
            }
        },
        "components": components,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return destination


def query_osv(packages: tuple[dict[str, str], ...]) -> dict[str, Any]:
    """Ask the OSV batch API about locked PyPI versions. This does not upgrade them."""
    body = {
        "queries": [
            {
                "package": {"name": item["name"], "ecosystem": "PyPI"},
                "version": item["version"],
            }
            for item in packages
        ]
    }
    request = urllib.request.Request(
        "https://api.osv.dev/v1/querybatch",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    results = payload.get("results", [])
    return {"status": "QUERIED", "findings": osv_findings(packages, results)}


def osv_findings(
    packages: tuple[dict[str, str], ...],
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pair each locked package with one OSV result. A short response is an error."""
    if len(results) != len(packages):
        raise ValueError(
            f"OSV returned {len(results)} results for {len(packages)} packages"
        )
    findings: list[dict[str, Any]] = []
    for package, result in zip(packages, results, strict=True):
        vulns = result.get("vulns") or []
        if vulns:
            findings.append(
                {
                    "name": package["name"],
                    "version": package["version"],
                    "ids": [str(item.get("id", "")) for item in vulns],
                }
            )
    return findings


def write_vulnerability_report(
    lock_path: Path,
    destination: Path,
    *,
    query: bool,
) -> dict[str, Any]:
    """Write a vulnerability report. A skipped query stays explicitly unqueried."""
    packages = locked_packages(lock_path)
    if query:
        report: dict[str, Any] = query_osv(packages)
    else:
        report = {
            "status": "NOT_QUERIED",
            "reason": "OSV was not contacted. Pass --query-osv to query it.",
            "findings": [],
        }
    report["package_count"] = len(packages)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def inspect_distributions(directory: Path) -> tuple[str, ...]:
    """Scan built wheels and source distributions for secrets and unsafe paths."""
    artifacts = sorted(
        path
        for path in directory.iterdir()
        if path.name.endswith(".whl") or path.name.endswith(".tar.gz")
    )
    if len(artifacts) < 2:
        return ("expected both a wheel and a source distribution",)
    findings: list[str] = []
    for artifact in artifacts:
        findings.extend(scan_distribution(artifact))
    return tuple(findings)


def file_sha256(path: Path) -> str:
    """Return the hex digest of one built artifact."""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    """Build distributions and reports. This command does not publish."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query-osv",
        action="store_true",
        help="Contact the OSV API and fail when a locked package has a finding.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "dist",
        help="Directory for wheels, the SBOM, and the vulnerability report.",
    )
    args = parser.parse_args()
    uv = shutil.which("uv")
    if uv is None:
        print("uv is required but was not found on PATH")
        return 127
    output = args.out_dir
    output.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(  # noqa: S603 - fixed command, no user input
        [uv, "build", "--no-sources", "--out-dir", str(output)],
        cwd=ROOT,
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode
    write_sbom(ROOT / "uv.lock", output / "sbom.cdx.json")
    report = write_vulnerability_report(
        ROOT / "uv.lock",
        output / "vulnerability-report.json",
        query=args.query_osv,
    )
    findings = inspect_distributions(output)
    if findings:
        for finding in findings:
            print(finding)
        return 1
    provenance = {
        "name": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "published": False,
        "builder": "local-uv-build",
        "artifacts": {
            path.name: file_sha256(path)
            for path in sorted(output.iterdir())
            if path.name.endswith(".whl") or path.name.endswith(".tar.gz")
        },
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    )
    print(f"package reports written under {output}")
    print("published: false")
    if report["status"] == "QUERIED" and report["findings"]:
        print(json.dumps(report["findings"]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
