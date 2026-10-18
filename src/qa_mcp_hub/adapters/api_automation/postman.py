"""Newman command builder for a registered Postman collection.

Purpose: run collection v2 JSON through pinned Newman flags.
Milestone: 06
Status: IMPLEMENTED
Ownership: Postman collection runner integration for allowlisted suites only.
Dependencies: Process policy and collection discovery.
Expected tests: pass, fail, timeout, and argv fixtures.
"""

from pathlib import Path

from qa_mcp_hub.adapters.api_automation.bruno import compose_argv
from qa_mcp_hub.security.process_policy import assert_argument

# Newman 6.2.2 README and the Postman Newman command reference document
# `newman run`, `--reporters json`, `--reporter-json-export`, and `-e`.
# `--env-var` is not used; values would appear in the process list.
NEWMAN_PIN = "6.2.2"
NEWMAN_FLAG_SOURCE = (
    "https://learning.postman.com/docs/reference/newman-cli/newman-options.md"
)


def newman_arguments(
    *,
    collection_path: Path,
    report_path: Path,
    env_file: Path | None,
) -> tuple[str, ...]:
    """Return newman arguments after the executable. The caller supplies no extras."""
    arguments: list[str] = [
        "run",
        str(collection_path),
        "--reporters",
        "json",
        "--reporter-json-export",
        str(report_path),
    ]
    if env_file is not None:
        arguments.extend(("-e", str(env_file)))
    for argument in arguments:
        assert_argument(argument)
    return tuple(arguments)


def newman_argv(
    binary: Path,
    *,
    collection_path: Path,
    report_path: Path,
    env_file: Path | None,
) -> tuple[str, ...]:
    """Build the full Newman argument vector for one registered collection."""
    return compose_argv(
        binary,
        newman_arguments(
            collection_path=collection_path,
            report_path=report_path,
            env_file=env_file,
        ),
    )
