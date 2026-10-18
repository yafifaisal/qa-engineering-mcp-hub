"""Profile-scoped repository registration.

Purpose: add, list, and remove repository definitions without indexing them.
Milestone: 02
Status: IMPLEMENTED
Ownership: repositories.registry
Dependencies: Repository models, configuration, storage, and path allowlists.
Expected tests: duplicate IDs, profile isolation, deterministic listing, and removal.
"""

from pathlib import Path, PurePosixPath

from qa_mcp_hub.config.models import HubConfig, ProfileConfig, RepositoryReference
from qa_mcp_hub.core.errors import PathAllowlistError, RepositoryRegistryError
from qa_mcp_hub.security.path_allowlist import resolve_within

MANDATORY_SECRET_EXCLUDES: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_dsa",
    ".ssh/**",
    "secrets/**",
)


def approved_roots(config: HubConfig, profile_id: str) -> tuple[Path, ...]:
    """Return the workspace path explicitly attached to one profile."""
    profile = _profile(config, profile_id)
    if profile.workspace_id is None:
        return ()
    workspace = next(
        (item for item in config.workspaces if item.id == profile.workspace_id),
        None,
    )
    if workspace is None:
        return ()
    return (Path(workspace.path),)


def list_repositories(
    config: HubConfig, profile_id: str
) -> tuple[RepositoryReference, ...]:
    """Return repositories assigned to one profile, ordered by id."""
    profile = _profile(config, profile_id)
    selected = {
        item.id: item
        for item in config.repositories
        if item.id in profile.repository_ids
    }
    return tuple(selected[key] for key in sorted(selected))


def get_repository(
    config: HubConfig,
    profile_id: str,
    repository_id: str,
) -> RepositoryReference:
    """Return one repository owned by the profile."""
    owned = list_repositories(config, profile_id)
    match = next((item for item in owned if item.id == repository_id), None)
    if match is None:
        raise RepositoryRegistryError("repository is not in this profile")
    return match


def register_repository(
    config: HubConfig,
    profile_id: str,
    repository: RepositoryReference,
) -> HubConfig:
    """Attach a repository to one profile and revalidate the whole configuration."""
    profile = _profile(config, profile_id)
    if any(item.id == repository.id for item in config.repositories):
        raise RepositoryRegistryError("duplicate repository id")
    if repository.connection_id is not None and (
        repository.connection_id not in profile.connection_ids
    ):
        raise RepositoryRegistryError("connection is not available in this profile")
    if repository.path is not None:
        roots = approved_roots(config, profile_id)
        normalized = str(resolve_within(Path(repository.path), roots))
        for item in config.repositories:
            if item.path is None:
                continue
            try:
                existing = str(resolve_within(Path(item.path), roots))
            except PathAllowlistError:
                continue
            if existing == normalized:
                raise RepositoryRegistryError("duplicate repository path")
        repository = repository.model_copy(update={"path": normalized})
    document = config.model_dump(mode="python")
    profiles = document["profiles"]
    current = profiles[profile_id]
    current["repository_ids"] = [*profile.repository_ids, repository.id]
    document["repositories"] = [
        *document["repositories"],
        repository.model_dump(mode="python"),
    ]
    return HubConfig.model_validate(document)


def remove_repository(
    config: HubConfig, profile_id: str, repository_id: str
) -> HubConfig:
    """Remove a repository only when the selected profile owns it."""
    get_repository(config, profile_id, repository_id)
    document = config.model_dump(mode="python")
    document["repositories"] = [
        item for item in document["repositories"] if item["id"] != repository_id
    ]
    for profile in document["profiles"].values():
        profile["repository_ids"] = [
            item for item in profile["repository_ids"] if item != repository_id
        ]
    return HubConfig.model_validate(document)


def normalize_local_path(
    path: Path,
    roots: tuple[Path, ...] | list[Path],
) -> str:
    """Resolve one local checkout and return its approved absolute path."""
    return str(resolve_within(path, roots))


def effective_excludes(configured: tuple[str, ...]) -> tuple[str, ...]:
    """Union caller excludes with patterns that must never be indexed."""
    return tuple(dict.fromkeys((*MANDATORY_SECRET_EXCLUDES, *configured)))


def effective_includes(
    include: tuple[str, ...], exclude: tuple[str, ...]
) -> tuple[str, ...]:
    """Drop include patterns that name a mandatory secret path."""
    blocked = set(effective_excludes(exclude))
    return tuple(
        item for item in include if item not in blocked and not _is_secret_pattern(item)
    )


def _is_secret_pattern(pattern: str) -> bool:
    candidate = PurePosixPath(pattern)
    return candidate.name in {".env", "id_rsa", "id_dsa"} or candidate.suffix in {
        ".pem",
        ".key",
        ".p12",
        ".pfx",
    }


def _profile(config: HubConfig, profile_id: str) -> ProfileConfig:
    profile = config.profiles.get(profile_id)
    if profile is None:
        raise RepositoryRegistryError("profile does not exist")
    return profile
