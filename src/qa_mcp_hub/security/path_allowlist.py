"""Canonical path containment for approved repository roots.

Purpose: normalize paths and reject traversal or symlink escape before access.
Milestone: 02
Status: IMPLEMENTED
Ownership: security.path_allowlist
Dependencies: Repository registry, workspace configuration, and native path rules.
Expected tests: traversal, symlinks, case rules, UNC paths, and missing roots.
"""

from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

from qa_mcp_hub.core.errors import PathAllowlistError


def case_sensitive(platform: str) -> bool:
    """Windows and macOS comparisons fold case. Linux comparisons do not."""
    return platform not in {"win32", "darwin"}


def logical_parts(value: str, *, platform: str) -> tuple[str, ...] | None:
    """Collapse ``.`` and ``..`` without touching the filesystem.

    Returns None when the value is relative, contains a null, or escapes its anchor.
    """
    if "\x00" in value:
        return None
    pure: PurePath
    pure = PureWindowsPath(value) if platform == "win32" else PurePosixPath(value)
    if not pure.is_absolute():
        return None
    collapsed: list[str] = [pure.parts[0]]
    for part in pure.parts[1:]:
        if part in {"", "."}:
            continue
        if part == "..":
            if len(collapsed) == 1:
                return None
            collapsed.pop()
            continue
        collapsed.append(part)
    if not case_sensitive(platform):
        return tuple(part.casefold() for part in collapsed)
    return tuple(collapsed)


def logically_contained(candidate: str, root: str, *, platform: str) -> bool:
    """Return whether a logical path stays inside a logical root."""
    candidate_parts = logical_parts(candidate, platform=platform)
    root_parts = logical_parts(root, platform=platform)
    if candidate_parts is None or root_parts is None:
        return False
    if candidate_parts == root_parts:
        return True
    return candidate_parts[: len(root_parts)] == root_parts


def resolve_within(path: Path, roots: tuple[Path, ...] | list[Path]) -> Path:
    """Resolve a path, including symlinks, and require an approved root."""
    if "\x00" in str(path):
        raise PathAllowlistError("path contains a null byte")
    if not roots:
        raise PathAllowlistError("no approved directory root")
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve(strict=False)
    for root in roots:
        approved = root.expanduser().resolve(strict=False)
        if resolved == approved or approved in resolved.parents:
            return resolved
    raise PathAllowlistError("path is outside an approved root")
