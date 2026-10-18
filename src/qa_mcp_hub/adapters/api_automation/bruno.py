"""Bruno CLI command builder for a registered collection.

Purpose: build the pinned bru argument list. Secrets stay off the command line.
Milestone: 06
Status: IMPLEMENTED
Ownership: Bruno CLI integration for allowlisted suites only.
Dependencies: Process policy and collection discovery.
Expected tests: pass, fail, timeout, and argv fixtures.
"""

import sys
from pathlib import Path

from qa_mcp_hub.security.process_policy import assert_argument, assert_executable

# Flags checked against https://docs.usebruno.com/bru-cli/run/options on 2026-10-18.
# `--sandbox safe` is the documented default since Bruno CLI 3. `--reporter-json`
# replaces the deprecated `--output`/`--format` pair. `--env-var` is not used
# because it would place secret values on the process command line.
BRUNO_CLI_BASELINE = "3"
BRUNO_FLAG_SOURCE = "https://docs.usebruno.com/bru-cli/run/options"


def bruno_arguments(
    *,
    report_path: Path,
    environment: str | None,
    env_file: Path | None,
) -> tuple[str, ...]:
    """Return bru arguments after the executable. The caller supplies no extras."""
    arguments: list[str] = [
        "run",
        "--sandbox",
        "safe",
        "--reporter-skip-all-headers",
        "--reporter-skip-body",
        "--reporter-json",
        str(report_path),
    ]
    if environment is not None:
        arguments.extend(("--env", environment))
    if env_file is not None:
        arguments.extend(("--env-file", str(env_file)))
    for argument in arguments:
        assert_argument(argument)
    return tuple(arguments)


def compose_argv(binary: Path, arguments: tuple[str, ...]) -> tuple[str, ...]:
    """Place one executable in front of a fixed argument list."""
    resolved = assert_executable(binary)
    if resolved.suffix.lower() == ".py":
        prefix: tuple[str, ...] = (sys.executable, str(resolved))
    else:
        prefix = (str(resolved),)
    for argument in prefix:
        assert_argument(argument)
    return prefix + arguments
