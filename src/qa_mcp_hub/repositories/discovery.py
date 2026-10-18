"""Bounded discovery of local Git checkouts inside approved roots.

Purpose: find candidate repositories without registering or indexing them.
Milestone: 02
Status: IMPLEMENTED
Ownership: repositories.discovery
Dependencies: Git provider contracts, filesystem path policy, and repository models.
Expected tests: search bounds, symlink safety, pagination, cancellation, and provenance.
"""

import os
import re
from pathlib import Path

from qa_mcp_hub.core.errors import PathAllowlistError
from qa_mcp_hub.repositories.models import DiscoveredRepository
from qa_mcp_hub.security.path_allowlist import resolve_within

_SKIP_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".ssh",
        ".venv",
        "node_modules",
        "secrets",
        "venv",
    }
)
_IDENTIFIER = re.compile(r"[^a-z0-9._-]+")
_MAX_DEPTH = 4


def discover_local_repositories(
    root: Path,
    *,
    approved_roots: tuple[Path, ...] | list[Path],
    max_depth: int = _MAX_DEPTH,
) -> tuple[DiscoveredRepository, ...]:
    """Walk one approved root. Symlinked directories are not followed."""
    if max_depth < 0:
        raise PathAllowlistError("discovery depth is invalid")
    approved = resolve_within(root, approved_roots)
    found: list[DiscoveredRepository] = []
    for current, dirs, files in os.walk(approved, followlinks=False):
        current_path = Path(current)
        try:
            relative_depth = len(current_path.resolve().relative_to(approved).parts)
        except ValueError:
            dirs.clear()
            continue
        if relative_depth > max_depth:
            dirs.clear()
            continue
        if _is_git_checkout(current_path, files, dirs):
            found.append(_candidate(current_path))
            dirs.clear()
            continue
        dirs[:] = [
            name
            for name in dirs
            if name not in _SKIP_DIRECTORIES
            and not name.startswith(".")
            and not (current_path / name).is_symlink()
        ]
    found.sort(key=lambda item: item.path)
    return tuple(found)


def _is_git_checkout(path: Path, files: list[str], dirs: list[str]) -> bool:
    if path.is_symlink():
        return False
    if ".git" not in files and ".git" not in dirs:
        return False
    git_entry = path / ".git"
    return git_entry.exists() and not _symlink_escapes(path, git_entry)


def _symlink_escapes(repository: Path, git_entry: Path) -> bool:
    if not git_entry.is_symlink():
        return False
    try:
        resolved = git_entry.resolve(strict=False)
    except OSError:
        return True
    return repository.resolve() not in resolved.parents


def _candidate(path: Path) -> DiscoveredRepository:
    display_name = path.name or "repository"
    suggested = _IDENTIFIER.sub("-", display_name.casefold()).strip("-._")
    if not suggested or not suggested[0].isalnum():
        suggested = f"repo-{suggested}" if suggested else "repository"
    return DiscoveredRepository(
        path=str(path.resolve()),
        suggested_id=suggested[:128],
        display_name=display_name[:1024],
    )
