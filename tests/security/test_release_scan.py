"""Package secret scanning for community artifacts."""

import zipfile
from pathlib import Path

import pytest

from qa_mcp_hub.security.secret_scanner import findings_in_text, scan_distribution


def test_known_token_shapes_are_reported() -> None:
    planted = "ghp_" + ("a" * 36)
    assert "GitHub token" in findings_in_text(planted)
    assert findings_in_text("token=qa_mcp_company_a_value") == ()


def test_distribution_scan_rejects_unsafe_members(tmp_path: Path) -> None:
    clean = tmp_path / "clean.whl"
    _zip(clean, {"qa_mcp_hub/__init__.py": "version = '0.1.0'\n"})
    assert scan_distribution(clean) == ()
    planted = tmp_path / "planted.whl"
    label = "password"
    sample = "not-a-real-value"
    token = "ghp_" + ("b" * 36)
    _zip(
        planted,
        {
            ".env": f"GH_TOKEN={token}\n",
            "qa_mcp_hub/leak.py": f"{label} = '{sample}'\n",
        },
    )
    findings = scan_distribution(planted)
    assert any("unsafe archive path" in item for item in findings)
    assert any("GitHub token" in item for item in findings)
    assert any("assigned secret" in item for item in findings)


def test_unsupported_distribution_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("plain", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported distribution"):
        scan_distribution(path)


def _zip(path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
