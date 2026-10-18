"""Load approved workflow files from a QA Workspace.

Purpose: read versioned YAML without executing it.
Milestone: 06
Status: IMPLEMENTED
Ownership: workflows.discovery
Dependencies: Workflow models and the path allowlist.
Expected tests: malformed files, bounds, and stable ordering.
"""

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from qa_mcp_hub.core.errors import HubError, PathAllowlistError
from qa_mcp_hub.security.path_allowlist import resolve_within
from qa_mcp_hub.workflows.models import WorkflowDefinition

_MAX_FILES = 100
_MAX_BYTES = 256_000
_DIRECTORIES = ("api", "e2e")


def discover_workflows(workspace: Path) -> tuple[WorkflowDefinition, ...]:
    """Load workflow YAML from workflows/api and workflows/e2e."""
    found: list[WorkflowDefinition] = []
    for name in _DIRECTORIES:
        directory = workspace / "workflows" / name
        if not directory.is_dir():
            continue
        files = sorted(path for path in directory.glob("*.yaml") if path.is_file())
        if len(files) > _MAX_FILES:
            raise HubError("workflow_limit", "workflow directory exceeds the file cap")
        for path in files:
            found.append(_load_one(workspace, path))
    ids = [item.id for item in found]
    if len(ids) != len(set(ids)):
        raise HubError("duplicate_workflow", "workflow ids are not unique")
    return tuple(sorted(found, key=lambda item: item.id))


def _load_one(workspace: Path, path: Path) -> WorkflowDefinition:
    try:
        resolved = resolve_within(path, (workspace,))
    except PathAllowlistError as exc:
        raise HubError("unsafe_path", exc.message) from exc
    raw = resolved.read_bytes()
    if len(raw) > _MAX_BYTES:
        raise HubError("workflow_rejected", "workflow file exceeds the size limit")
    loaded = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(loaded, dict):
        raise HubError("workflow_rejected", "workflow file is not a document")
    loaded["source_path"] = str(resolved.relative_to(workspace))
    try:
        return WorkflowDefinition.model_validate(loaded)
    except ValidationError as exc:
        raise HubError("workflow_rejected", "workflow file is not valid") from exc
