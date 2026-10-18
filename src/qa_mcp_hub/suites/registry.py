"""Workspace-scoped lookup of registered suites.

Purpose: load suites.yaml and reject duplicate ids.
Milestone: 06
Status: IMPLEMENTED
Ownership: suites.registry
Dependencies: Suite models and the suite validator.
Expected tests: duplicate ids, listing, and reloads.
"""

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from qa_mcp_hub.adapters.api_automation.base import discover_bruno, discover_postman
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.suites.models import (
    CollectionDiscovery,
    SuiteCatalog,
    SuiteDefinition,
    SuiteRegistryFile,
)
from qa_mcp_hub.suites.validator import validate_suite

_MAX_BYTES = 256_000


def registry_path(workspace: Path) -> Path:
    """Return the suite registry file inside a workspace."""
    return workspace / "suites" / "suites.yaml"


def load_suite_registry(workspace: Path) -> SuiteRegistryFile:
    """Load and validate the suite registry. Duplicate ids are rejected."""
    path = registry_path(workspace)
    if not path.is_file():
        raise HubError("suite_registry_missing", "suites.yaml is not in the workspace")
    raw = path.read_bytes()
    if len(raw) > _MAX_BYTES:
        raise HubError("suite_registry_rejected", "suites.yaml exceeds the size limit")
    loaded = yaml.safe_load(raw.decode("utf-8"))
    try:
        document = SuiteRegistryFile.model_validate(loaded)
    except ValidationError as exc:
        raise HubError("suite_registry_rejected", "suites.yaml is not valid") from exc
    seen: set[str] = set()
    for suite in document.suites:
        if suite.id in seen:
            raise HubError("duplicate_suite", f"duplicate suite id: {suite.id}")
        seen.add(suite.id)
        validate_suite(suite, workspace)
    return document


def catalog_for(workspace: Path, profile_id: str) -> SuiteCatalog:
    """List registered suites and the files at each registered path."""
    document = load_suite_registry(workspace)
    executable = document.implementation_status == "IMPLEMENTED"
    discovered: list[CollectionDiscovery] = []
    for suite in document.suites:
        target = validate_suite(suite, workspace)
        if suite.runner == "bruno":
            files = discover_bruno(target)
        else:
            files = discover_postman(target)
        discovered.append(
            CollectionDiscovery(
                suite_id=suite.id,
                runner=suite.runner,
                path=suite.path,
                files=files,
                found=bool(files),
            )
        )
    return SuiteCatalog(
        profile_id=profile_id,
        registry_status=document.implementation_status,
        executable=executable,
        suites=document.suites,
        discovered=tuple(discovered),
    )


def suite_by_id(document: SuiteRegistryFile, suite_id: str) -> SuiteDefinition:
    """Return one suite or reject an unknown id."""
    for suite in document.suites:
        if suite.id == suite_id:
            return suite
    raise HubError("unknown_suite", f"suite is not registered: {suite_id}")
