#!/usr/bin/env python3
"""Run the complete local Milestone 00 quality gate in a fixed order.

Purpose: provide one deterministic developer validation entry point.
Milestone: 00
Status: IMPLEMENTED
Ownership: scripts.validation_orchestrator
Dependencies: uv and the locked development environment.
Expected tests: CI executes the same underlying commands independently.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    ("lock", "lock", "--check"),
    ("ruff", "run", "ruff", "check", "."),
    ("format", "run", "ruff", "format", "--check", "."),
    ("mypy", "run", "mypy", "src"),
    ("pytest", "run", "pytest", "-v"),
    ("structure", "run", "python", "scripts/structure_audit.py"),
    ("build", "build", "--no-sources"),
)


def main() -> int:
    """Run fixed uv subcommands and stop at the first failure."""
    uv = shutil.which("uv")
    if uv is None:
        print("uv is required but was not found on PATH")
        return 127
    for label, *arguments in COMMANDS:
        print(f"==> {label}")
        completed = subprocess.run(  # noqa: S603 - command is a fixed allowlist
            [uv, *arguments],
            cwd=ROOT,
            check=False,
        )
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
