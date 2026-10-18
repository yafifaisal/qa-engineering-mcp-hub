"""Policy-aware conversion of a suite id into an immutable run plan.

Purpose: resolve a registered suite without accepting a caller command.
Milestone: 06
Status: IMPLEMENTED
Ownership: suites.resolver
Dependencies: Suite registry, path allowlist, and runner argument builders.
Expected tests: unknown ids, path scope, and plan stability.
"""

import re
import shutil
import subprocess
from pathlib import Path

from qa_mcp_hub.adapters.api_automation.base import (
    bruno_collection_ready,
    postman_collection_file,
)
from qa_mcp_hub.adapters.api_automation.bruno import bruno_arguments, compose_argv
from qa_mcp_hub.adapters.api_automation.postman import newman_arguments
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.suites.models import ResolvedSuite, SuiteDefinition
from qa_mcp_hub.suites.validator import validate_suite

_SHA = re.compile(r"^[0-9a-f]{40}$")


def source_revision(path: Path) -> str | None:
    """Read HEAD when the suite lives in a Git checkout. Failure stays unknown."""
    start = path if path.is_dir() else path.parent
    git = shutil.which("git")
    if git is None:
        return None
    try:
        completed = subprocess.run(  # noqa: S603 - fixed git argument list
            [git, "-C", str(start), "rev-parse", "HEAD"],
            shell=False,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    sha = completed.stdout.strip()
    if completed.returncode != 0 or not _SHA.fullmatch(sha):
        return None
    return sha


def resolve_suite(
    suite: SuiteDefinition,
    workspace: Path,
    *,
    binary: Path,
    report_path: Path,
    env_file: Path | None,
    environment: str | None,
) -> ResolvedSuite:
    """Build the argv for one registered suite. Extra arguments are not accepted."""
    target = validate_suite(suite, workspace)
    if environment is not None and environment != suite.environment:
        raise HubError(
            "unsupported_environment",
            "requested environment is not registered for this suite",
        )
    selected = environment if environment is not None else suite.environment
    if suite.runner == "bruno":
        if not bruno_collection_ready(target):
            raise HubError("collection_missing", "Bruno collection marker is missing")
        arguments = bruno_arguments(
            report_path=report_path,
            environment=selected,
            env_file=env_file,
        )
        working = target
        collection = target
    else:
        collection_file = postman_collection_file(target)
        if collection_file is None:
            raise HubError("collection_missing", "Postman collection file is missing")
        arguments = newman_arguments(
            collection_path=collection_file,
            report_path=report_path,
            env_file=env_file,
        )
        working = collection_file.parent
        collection = collection_file
    argv = compose_argv(binary, arguments)
    return ResolvedSuite(
        suite=suite,
        collection_path=str(collection),
        working_directory=str(working),
        source_revision=source_revision(working),
        argv=argv,
    )
