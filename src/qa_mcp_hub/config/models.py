"""Versioned, non-secret application configuration models.

Milestone 01 configuration stores identities, paths, preferences, and opaque
credential references. It cannot represent a plaintext credential. Provider
connections are global records referenced by profiles so duplicate provider kinds
remain valid while connection identity stays unambiguous.

Purpose: define the versioned user-configuration contract.
Milestone: 01
Status: IMPLEMENTED
Ownership: config.models
Dependencies: Pydantic and the authentication reference models.
Expected tests: schema validation, isolation, and unknown-provider rejection.
"""

import re
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from qa_mcp_hub.auth.models import AuthKind, CredentialReference
from qa_mcp_hub.core.enums import IndexingPermission
from qa_mcp_hub.core.models import ProviderKind

CURRENT_SCHEMA_VERSION: Literal[1] = 1
IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9._-]*$"
ENVIRONMENT_NAME_PATTERN = r"^[A-Z][A-Z0-9_]*$"

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=IDENTIFIER_PATTERN,
    ),
]
NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1024),
]
EnvironmentName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=ENVIRONMENT_NAME_PATTERN,
        max_length=256,
    ),
]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class HubSettings(BaseSettings):
    """Minimal local settings; credentials are deliberately not fields."""

    model_config = SettingsConfigDict(
        env_prefix="QA_MCP_",
        extra="forbid",
        case_sensitive=False,
        str_strip_whitespace=True,
    )

    log_level: LogLevel = "INFO"
    server_name: str = Field(default="QA Engineering MCP Hub", min_length=1)
    transport: Literal["stdio"] = "stdio"


class DeploymentKind(StrEnum):
    """Supported deployment shapes; this does not imply provider connectivity."""

    CLOUD = "cloud"
    SELF_MANAGED = "self_managed"
    LOCAL = "local"
    FILE = "file"


class ExecutionPreferences(BaseModel):
    """Safe defaults for later, registered execution capabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    max_concurrency: int = Field(default=1, ge=1, le=32)
    dry_run: bool = True
    allow_mutations: bool = False


class ExecutionOverrides(BaseModel):
    """Optional profile values layered over application preferences."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    timeout_seconds: int | None = Field(default=None, ge=1, le=3600)
    max_concurrency: int | None = Field(default=None, ge=1, le=32)
    dry_run: bool | None = None
    allow_mutations: bool | None = None


class ConnectionConfig(BaseModel):
    """A provider endpoint and opaque credential reference, never a secret."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    id: Identifier
    provider: ProviderKind
    deployment: DeploymentKind
    base_url: str | None = None
    account: NonEmptyString | None = None
    auth_kind: AuthKind = AuthKind.none
    credential: CredentialReference | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def validate_endpoint(self) -> Self:
        if self.auth_kind is AuthKind.none and self.credential is not None:
            raise ValueError(
                "credential must be absent when authentication kind is none"
            )
        if self.credential is not None and self.credential.kind is not self.auth_kind:
            raise ValueError("credential authentication kind does not match connection")
        if self.base_url is None:
            return self
        endpoint = urlsplit(self.base_url)
        try:
            _ = endpoint.port
        except ValueError as exc:
            raise ValueError("base_url contains an invalid port") from exc
        if (
            endpoint.scheme != "https"
            or endpoint.hostname is None
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.fragment
        ):
            raise ValueError(
                "base_url must be an HTTPS URL without credentials or fragment"
            )
        return self

    @property
    def host(self) -> str | None:
        """Return the normalized endpoint host for credential-scope checks."""
        if self.base_url is None:
            return None
        endpoint = urlsplit(self.base_url)
        hostname = endpoint.hostname
        if hostname is None:
            return None
        normalized = hostname.lower().rstrip(".")
        if endpoint.port is None:
            return normalized
        return f"{normalized}:{endpoint.port}"


def _reject_unsafe_pattern(value: str) -> None:
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or "\x00" in value
        or re.match(r"^[A-Za-z]:", value)
    ):
        raise ValueError("repository pattern must be a relative path")


def _reject_unsafe_remote(value: str) -> None:
    if any(character in value for character in ("@", " ", "\\", "\x00")):
        raise ValueError("remote repository reference is invalid")
    if ".." in value.split("/"):
        raise ValueError("remote repository reference is invalid")


class RepositoryReference(BaseModel):
    """A local checkout, a remote definition, or both. Registration does not index."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    id: Identifier
    display_name: NonEmptyString
    path: NonEmptyString | None = None
    path_env: EnvironmentName | None = None
    remote: NonEmptyString | None = None
    connection_id: Identifier | None = None
    default_branch: NonEmptyString = "main"
    include: tuple[NonEmptyString, ...] = ()
    exclude: tuple[NonEmptyString, ...] = ()
    indexing: IndexingPermission = IndexingPermission.none
    enabled: bool = True

    @model_validator(mode="after")
    def one_unambiguous_source(self) -> Self:
        has_path = self.path is not None
        has_env = self.path_env is not None
        has_remote = self.remote is not None
        if has_path and has_env:
            raise ValueError("repository source is ambiguous")
        if not has_path and not has_env and not has_remote:
            raise ValueError("repository requires a local path or a remote definition")
        if has_remote and self.connection_id is None:
            raise ValueError("remote repository requires a connection reference")
        for pattern in (*self.include, *self.exclude):
            _reject_unsafe_pattern(pattern)
        if self.remote is not None:
            _reject_unsafe_remote(self.remote)
        return self


class QAWorkspaceReference(BaseModel):
    """A named reference to company-owned QA workspace data."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    id: Identifier
    path: NonEmptyString


class ProfileConfig(BaseModel):
    """References composing one isolated workspace profile."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    description: str | None = Field(default=None, max_length=500)
    workspace_id: Identifier | None = None
    repository_ids: tuple[Identifier, ...] = ()
    connection_ids: tuple[Identifier, ...] = ()
    execution: ExecutionOverrides = Field(default_factory=ExecutionOverrides)
    log_level: LogLevel | None = None

    @model_validator(mode="after")
    def unique_references(self) -> Self:
        if len(self.repository_ids) != len(set(self.repository_ids)):
            raise ValueError("duplicate repository id in profile")
        if len(self.connection_ids) != len(set(self.connection_ids)):
            raise ValueError("duplicate connection id in profile")
        return self


class HubConfig(BaseModel):
    """Current consolidated user configuration schema."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal[1]
    active_profile: Identifier | None = None
    profiles: dict[Identifier, ProfileConfig] = Field(default_factory=dict)
    connections: tuple[ConnectionConfig, ...] = ()
    repositories: tuple[RepositoryReference, ...] = ()
    workspaces: tuple[QAWorkspaceReference, ...] = ()
    execution: ExecutionPreferences = Field(default_factory=ExecutionPreferences)
    log_level: LogLevel = "INFO"

    @model_validator(mode="after")
    def validate_references_and_isolation(self) -> Self:
        if self.active_profile is not None and self.active_profile not in self.profiles:
            raise ValueError("active profile does not exist")

        connection_by_id = _unique_by_id(self.connections, "connection")
        repository_by_id = _unique_by_id(self.repositories, "repository")
        workspace_by_id = _unique_by_id(self.workspaces, "workspace")

        assigned_connection: dict[str, str] = {}
        assigned_repository: dict[str, str] = {}
        for profile_name, profile in self.profiles.items():
            if not re.fullmatch(IDENTIFIER_PATTERN, profile_name):
                raise ValueError("profile name is invalid")
            if (
                profile.workspace_id is not None
                and profile.workspace_id not in workspace_by_id
            ):
                raise ValueError("profile references an unknown workspace")
            unknown_repositories = set(profile.repository_ids) - repository_by_id.keys()
            if unknown_repositories:
                raise ValueError("profile references an unknown repository")
            unknown_connections = set(profile.connection_ids) - connection_by_id.keys()
            if unknown_connections:
                raise ValueError("profile references an unknown connection")
            for connection_id in profile.connection_ids:
                previous_profile = assigned_connection.setdefault(
                    connection_id, profile_name
                )
                if previous_profile != profile_name:
                    raise ValueError("connection cannot be shared across profiles")
            for repository_id in profile.repository_ids:
                previous_repository = assigned_repository.setdefault(
                    repository_id, profile_name
                )
                if previous_repository != profile_name:
                    raise ValueError("repository cannot be shared across profiles")

        for repository in self.repositories:
            if (
                repository.connection_id is not None
                and repository.connection_id not in connection_by_id
            ):
                raise ValueError("repository references an unknown connection")
            if repository.connection_id is not None:
                owner = assigned_repository.get(repository.id)
                connection_owner = assigned_connection.get(repository.connection_id)
                if owner is None or owner != connection_owner:
                    raise ValueError("repository connection crosses profiles")

        for connection in self.connections:
            credential = connection.credential
            if credential is None:
                continue
            assigned_profile_name = assigned_connection.get(connection.id)
            if assigned_profile_name is None:
                raise ValueError(
                    "credential-bearing connection must belong to a profile"
                )
            scope = credential.scope
            if (
                scope.profile != assigned_profile_name
                or scope.provider != connection.provider
                or scope.connection_id != connection.id
            ):
                raise ValueError(
                    "credential scope does not match its profile connection"
                )
            if scope.host is not None and scope.host != connection.host:
                raise ValueError("credential host scope does not match connection")
            if scope.account is not None and scope.account != connection.account:
                raise ValueError("credential account scope does not match connection")
        return self


def _unique_by_id[T: BaseModel](items: tuple[T, ...], label: str) -> dict[str, T]:
    indexed: dict[str, T] = {}
    for item in items:
        item_id = getattr(item, "id", None)
        if not isinstance(item_id, str):
            raise ValueError(f"{label} is missing an id")
        if item_id in indexed:
            raise ValueError(f"duplicate {label} id")
        indexed[item_id] = item
    return indexed


ApplicationConfig = HubConfig
