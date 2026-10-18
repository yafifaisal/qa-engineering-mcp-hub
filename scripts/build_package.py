#!/usr/bin/env python3
"""Build release artifacts through uv's configured backend.

Purpose: keep package building reproducible and independent of local source links.
Milestone: 00
Status: IMPLEMENTED
Ownership: scripts.package_builder
Dependencies: uv and the locked build backend.
Expected tests: wheel/sdist creation and isolated wheel smoke test.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Run the fixed portable-source build command."""
    uv = shutil.which("uv")
    if uv is None:
        print("uv is required but was not found on PATH")
        return 127
    completed = subprocess.run(  # noqa: S603 - fixed command, no user input
        [uv, "build", "--no-sources"],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
