"""Shared collection discovery for registered API runners.

Purpose: find Bruno and Postman files at a registered path.
Milestone: 06
Status: IMPLEMENTED
Ownership: Shared API automation mechanics, excluding unrestricted command
execution.
Dependencies: Path checks and suite identities.
Expected tests: discovery without execution.
"""

from pathlib import Path

_MAX_FILES = 200


def discover_bruno(path: Path) -> tuple[str, ...]:
    """List collection markers and request files in one registered directory."""
    if not path.is_dir():
        return ()
    names: list[str] = []
    for marker in ("bruno.json", "opencollection.yml"):
        if (path / marker).is_file():
            names.append(marker)
    names.extend(sorted(item.name for item in path.glob("*.bru") if item.is_file()))
    return tuple(names[:_MAX_FILES])


def discover_postman(path: Path) -> tuple[str, ...]:
    """List a registered collection file or JSON files in its directory."""
    if path.is_file() and path.suffix == ".json":
        return (path.name,)
    if not path.is_dir():
        return ()
    names = sorted(item.name for item in path.glob("*.json") if item.is_file())
    return tuple(names[:_MAX_FILES])


def bruno_collection_ready(path: Path) -> bool:
    """A Bruno run needs a collection marker in the working directory."""
    return path.is_dir() and (
        (path / "bruno.json").is_file() or (path / "opencollection.yml").is_file()
    )


def postman_collection_file(path: Path) -> Path | None:
    """Return the one collection file named by a registered path."""
    if path.is_file() and path.suffix == ".json":
        return path
    if not path.is_dir():
        return None
    matches = sorted(path.glob("*.postman_collection.json"))
    if len(matches) == 1:
        return matches[0]
    return None
