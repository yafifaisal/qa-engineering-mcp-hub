"""Layered, profile-scoped configuration resolution.

Precedence is explicit CLI input, environment, selected profile, user config, then
application defaults. The result is a deep, frozen snapshot so switching the active
profile on disk cannot alter an execution that has already started.
"""

import os
from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict

from qa_mcp_hub.config.models import (
    ConnectionConfig,
    ExecutionPreferences,
    HubConfig,
    LogLevel,
    ProfileConfig,
    RepositoryReference,
)


class ConfigResolutionError(ValueError):
    """Raised when configuration layers cannot produce a safe snapshot."""


class ResolutionSource(StrEnum):
    """Layer that supplied one resolved value."""

    EXPLICIT = "explicit"
    ENVIRONMENT = "environment"
    PROFILE = "profile"
    USER = "user"
    DEFAULT = "default"


class ResolvedFieldSource(BaseModel):
    """Value-free provenance for one resolved field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    source: ResolutionSource


class ResolvedConfig(BaseModel):
    """Immutable, detached runtime view of exactly one profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    active_profile: str
    profile: ProfileConfig
    workspace_id: str | None
    workspace_path: str | None
    connections: tuple[ConnectionConfig, ...]
    repositories: tuple[RepositoryReference, ...]
    execution: ExecutionPreferences
    log_level: LogLevel
    provenance: tuple[ResolvedFieldSource, ...]


def _parse_bool(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ConfigResolutionError(f"{field} override must be a boolean")


def _parse_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ConfigResolutionError(f"{field} override must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            pass
    raise ConfigResolutionError(f"{field} override must be an integer")


def _parse_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigResolutionError(f"{field} override must be non-empty text")
    normalized = value.strip()
    if any(ord(character) < 32 for character in normalized):
        raise ConfigResolutionError(f"{field} override contains control characters")
    return normalized


def _parse_log_level(value: object, field: str) -> LogLevel:
    parsed = _parse_text(value, field)
    if parsed not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ConfigResolutionError(f"{field} override is not a supported log level")
    return parsed  # type: ignore[return-value]


def _select_value[T](
    *,
    field: str,
    explicit: Mapping[str, object],
    explicit_key: str,
    environment: Mapping[str, str],
    environment_key: str,
    profile_value: object | None,
    user_value: object | None,
    default_value: T,
    parser: Callable[[object, str], T],
) -> tuple[T, ResolutionSource]:
    if explicit_key in explicit and explicit[explicit_key] is not None:
        return parser(explicit[explicit_key], field), ResolutionSource.EXPLICIT
    if environment_key in environment:
        return parser(environment[environment_key], field), ResolutionSource.ENVIRONMENT
    if profile_value is not None:
        return parser(profile_value, field), ResolutionSource.PROFILE
    if user_value is not None:
        return parser(user_value, field), ResolutionSource.USER
    return default_value, ResolutionSource.DEFAULT


def _detached[T: BaseModel](model_type: type[T], value: T) -> T:
    return model_type.model_validate(value.model_dump(mode="python"))


def resolve_config(
    config: HubConfig,
    *,
    explicit: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ResolvedConfig:
    """Resolve and freeze one profile according to the documented precedence."""
    explicit_values = dict(explicit or {})
    environment = os.environ if environ is None else environ
    supported_explicit = {
        "active_profile",
        "workspace_path",
        "log_level",
        "timeout_seconds",
        "max_concurrency",
        "dry_run",
        "allow_mutations",
    }
    if set(explicit_values) - supported_explicit:
        raise ConfigResolutionError("explicit configuration contains an unknown option")

    default_profile: str | None = "default" if "default" in config.profiles else None
    profile_name, profile_source = _select_value(
        field="active_profile",
        explicit=explicit_values,
        explicit_key="active_profile",
        environment=environment,
        environment_key="QA_MCP_ACTIVE_PROFILE",
        profile_value=None,
        user_value=config.active_profile,
        default_value=default_profile,
        parser=_parse_text,
    )
    if profile_name is None:
        raise ConfigResolutionError("no active profile is configured")
    profile = config.profiles.get(profile_name)
    if profile is None:
        raise ConfigResolutionError("selected profile does not exist")

    workspace_by_id = {item.id: item for item in config.workspaces}
    configured_workspace = (
        workspace_by_id.get(profile.workspace_id)
        if profile.workspace_id is not None
        else None
    )
    workspace_path, workspace_source = _select_value(
        field="workspace_path",
        explicit=explicit_values,
        explicit_key="workspace_path",
        environment=environment,
        environment_key="QA_MCP_WORKSPACE_PATH",
        profile_value=(configured_workspace.path if configured_workspace else None),
        user_value=None,
        default_value=None,
        parser=_parse_text,
    )

    defaults = ExecutionPreferences()
    resolved_execution: dict[str, object] = {}
    execution_sources: list[ResolvedFieldSource] = []
    parsers: dict[str, Callable[[object, str], Any]] = {
        "timeout_seconds": _parse_int,
        "max_concurrency": _parse_int,
        "dry_run": _parse_bool,
        "allow_mutations": _parse_bool,
    }
    environment_keys = {
        "timeout_seconds": "QA_MCP_TIMEOUT_SECONDS",
        "max_concurrency": "QA_MCP_MAX_CONCURRENCY",
        "dry_run": "QA_MCP_DRY_RUN",
        "allow_mutations": "QA_MCP_ALLOW_MUTATIONS",
    }
    for field, parser in parsers.items():
        value, source = _select_value(
            field=field,
            explicit=explicit_values,
            explicit_key=field,
            environment=environment,
            environment_key=environment_keys[field],
            profile_value=getattr(profile.execution, field),
            user_value=(
                getattr(config.execution, field)
                if field in config.execution.model_fields_set
                else None
            ),
            default_value=getattr(defaults, field),
            parser=parser,
        )
        resolved_execution[field] = value
        execution_sources.append(ResolvedFieldSource(field=field, source=source))
    try:
        execution = ExecutionPreferences.model_validate(resolved_execution)
    except ValueError as exc:
        raise ConfigResolutionError(
            "resolved execution preferences are invalid"
        ) from exc

    selected_log_level, log_source = _select_value(
        field="log_level",
        explicit=explicit_values,
        explicit_key="log_level",
        environment=environment,
        environment_key="QA_MCP_LOG_LEVEL",
        profile_value=profile.log_level,
        user_value=(
            config.log_level if "log_level" in config.model_fields_set else None
        ),
        default_value="INFO",
        parser=_parse_log_level,
    )
    log_level = cast(LogLevel, selected_log_level)

    connection_by_id = {item.id: item for item in config.connections}
    repository_by_id = {item.id: item for item in config.repositories}
    connections = tuple(
        _detached(ConnectionConfig, connection_by_id[item_id])
        for item_id in profile.connection_ids
    )
    repositories = tuple(
        _detached(RepositoryReference, repository_by_id[item_id])
        for item_id in profile.repository_ids
    )

    provenance = (
        ResolvedFieldSource(field="active_profile", source=profile_source),
        ResolvedFieldSource(field="workspace_path", source=workspace_source),
        *execution_sources,
        ResolvedFieldSource(field="log_level", source=log_source),
    )
    return ResolvedConfig(
        active_profile=profile_name,
        profile=_detached(ProfileConfig, profile),
        workspace_id=profile.workspace_id,
        workspace_path=workspace_path,
        connections=connections,
        repositories=repositories,
        execution=execution,
        log_level=log_level,
        provenance=provenance,
    )
