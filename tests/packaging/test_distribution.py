"""Isolated Community Edition installation. These tests do not publish."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from qa_mcp_hub.security.secret_scanner import scan_distribution

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "qa_mcp_build_package",
    ROOT / "scripts" / "build_package.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_BUILD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BUILD)


def _uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        pytest.fail("uv is required")
    return uv


def test_locked_sbom_and_unqueried_vulnerability_report(tmp_path: Path) -> None:
    sbom_path = _BUILD.write_sbom(ROOT / "uv.lock", tmp_path / "sbom.cdx.json")
    document = json.loads(sbom_path.read_text(encoding="utf-8"))
    assert document["bomFormat"] == "CycloneDX"
    assert document["metadata"]["component"]["version"] == "0.1.0"
    names = {item["name"] for item in document["components"]}
    assert "fastmcp" in names
    assert "pydantic" in names
    report = _BUILD.write_vulnerability_report(
        ROOT / "uv.lock",
        tmp_path / "vulnerability-report.json",
        query=False,
    )
    assert report["status"] == "NOT_QUERIED"
    assert report["findings"] == []
    assert report["package_count"] >= 1


def test_wheel_install_uvx_reinstall_and_uninstall(tmp_path: Path) -> None:
    uv = _uv()
    output = tmp_path / "dist"
    built = subprocess.run(  # noqa: S603 - fixed uv build, no user input
        [uv, "build", "--no-sources", "--out-dir", str(output)],
        cwd=ROOT,
        check=False,
    )
    assert built.returncode == 0
    wheel = next(output.glob("*.whl"))
    source = next(output.glob("*.tar.gz"))
    assert scan_distribution(wheel) == ()
    assert scan_distribution(source) == ()

    venv = tmp_path / "venv"
    created = subprocess.run(  # noqa: S603
        [uv, "venv", str(venv), "--python", "3.12"],
        check=False,
    )
    assert created.returncode == 0
    python = venv / "bin" / "python"
    command = venv / "bin" / "qa-mcp"
    installed = subprocess.run(  # noqa: S603
        [uv, "pip", "install", "--python", str(python), str(wheel)],
        check=False,
    )
    assert installed.returncode == 0
    _assert_version(command)
    doctor = subprocess.run(  # noqa: S603
        [str(command), "doctor", "--config", str(tmp_path / "missing.yaml")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert doctor.returncode == 0
    assert "User configuration: absent" in doctor.stderr + doctor.stdout
    help_text = subprocess.run(  # noqa: S603
        [str(command), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_text.returncode == 0
    for name in ("setup", "doctor", "profiles", "integrations", "workflows"):
        assert name in help_text.stdout
    smoke = subprocess.run(  # noqa: S603
        [str(python), str(ROOT / "scripts" / "smoke_test.py")],
        check=False,
    )
    assert smoke.returncode == 0

    removed = subprocess.run(  # noqa: S603
        [uv, "pip", "uninstall", "--python", str(python), "qa-engineering-mcp-hub"],
        check=False,
    )
    assert removed.returncode == 0
    missing = subprocess.run(  # noqa: S603
        [str(python), "-c", "import qa_mcp_hub"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0

    reinstalled = subprocess.run(  # noqa: S603
        [uv, "pip", "install", "--python", str(python), str(wheel)],
        check=False,
    )
    assert reinstalled.returncode == 0
    _assert_version(command)

    uvx = shutil.which("uvx")
    if uvx is None:
        pytest.fail("uvx is required")
    invoked = subprocess.run(  # noqa: S603
        [uvx, "--from", str(wheel), "qa-mcp", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert invoked.returncode == 0
    assert "0.1.0" in invoked.stdout + invoked.stderr


def _assert_version(command: Path) -> None:
    completed = subprocess.run(  # noqa: S603
        [str(command), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "0.1.0" in completed.stdout + completed.stderr
