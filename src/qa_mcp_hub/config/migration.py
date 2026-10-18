"""Versioned, backed-up configuration migration with rollback."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qa_mcp_hub.config.loader import ConfigLoadError, load_config, load_yaml_text
from qa_mcp_hub.config.models import CURRENT_SCHEMA_VERSION, HubConfig
from qa_mcp_hub.config.validator import ConfigValidationError, validate_config
from qa_mcp_hub.config.writer import atomic_write_text, serialize_config


class ConfigMigrationError(ValueError):
    """Raised when a migration is unsupported or cannot complete safely."""


class ConfigRollbackError(ConfigMigrationError):
    """Raised when both migration and restoration fail."""


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """Machine-readable migration outcome."""

    config: HubConfig
    migrated: bool
    source_version: int
    target_version: int
    backup_path: Path | None


def _detect_version(document: Mapping[str, Any]) -> int:
    schema_version = document.get("schema_version")
    legacy_version = document.get("version")
    if schema_version is not None and legacy_version is not None:
        raise ConfigMigrationError("configuration declares multiple schema versions")
    value = schema_version if schema_version is not None else legacy_version
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigMigrationError("configuration schema version must be an integer")
    return int(value)


def _migrate_v0_to_v1(document: Mapping[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(dict(document))
    if "registries" in migrated:
        raise ConfigMigrationError(
            "the scaffold registry-index format is not a runtime configuration; "
            "create a consolidated configuration with qa-mcp setup"
        )
    migrated.pop("version", None)
    migrated["schema_version"] = 1
    if "current_profile" in migrated:
        if "active_profile" in migrated:
            raise ConfigMigrationError("legacy profile fields conflict")
        migrated["active_profile"] = migrated.pop("current_profile")
    migrated.setdefault("active_profile", None)
    migrated.setdefault("profiles", {})
    migrated.setdefault("connections", [])
    migrated.setdefault("repositories", [])
    migrated.setdefault("workspaces", [])
    migrated.setdefault("execution", {})
    migrated.setdefault("log_level", "INFO")
    return migrated


def migrate_document(document: Mapping[str, Any]) -> tuple[HubConfig, int, bool]:
    """Migrate one in-memory document without mutating the caller's mapping."""
    source_version = _detect_version(document)
    if source_version > CURRENT_SCHEMA_VERSION:
        raise ConfigMigrationError(
            "configuration schema is newer than this application"
        )
    if source_version < 0:
        raise ConfigMigrationError("configuration schema version cannot be negative")
    if source_version == CURRENT_SCHEMA_VERSION:
        try:
            return validate_config(document), source_version, False
        except ConfigValidationError as exc:
            raise ConfigMigrationError("current configuration is invalid") from exc
    if source_version != 0:
        raise ConfigMigrationError("configuration migration path is unsupported")
    migrated = _migrate_v0_to_v1(document)
    try:
        return validate_config(migrated), source_version, True
    except ConfigValidationError as exc:
        raise ConfigMigrationError("migrated configuration is invalid") from exc


def _next_backup_path(path: Path, source_version: int) -> Path:
    base = path.with_name(f"{path.name}.v{source_version}.bak")
    if not base.exists():
        return base
    counter = 1
    while True:
        candidate = path.with_name(f"{base.name}.{counter}")
        if not candidate.exists():
            return candidate
        counter += 1


def migrate_config(
    path: Path,
    *,
    write_target: Callable[[Path, str], None] | None = None,
) -> MigrationResult:
    """Migrate ``path`` atomically, retaining a versioned backup and rolling back."""
    try:
        original_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigMigrationError(f"configuration file not found: {path}") from None
    except OSError as exc:
        raise ConfigMigrationError(
            f"configuration file cannot be read: {path}"
        ) from exc
    try:
        document = load_yaml_text(original_text)
    except ConfigLoadError as exc:
        raise ConfigMigrationError(
            "configuration cannot be parsed for migration"
        ) from exc

    config, source_version, migrated = migrate_document(document)
    if not migrated:
        return MigrationResult(
            config=config,
            migrated=False,
            source_version=source_version,
            target_version=CURRENT_SCHEMA_VERSION,
            backup_path=None,
        )

    backup_path = _next_backup_path(path, source_version)
    try:
        atomic_write_text(backup_path, original_text)
    except OSError as exc:
        raise ConfigMigrationError("configuration backup could not be created") from exc

    target_writer = write_target or atomic_write_text
    try:
        target_writer(path, serialize_config(config))
        if load_config(path) != config:
            raise ConfigMigrationError("persisted migration did not validate")
    except Exception as migration_error:
        try:
            atomic_write_text(path, original_text)
        except OSError as rollback_error:
            raise ConfigRollbackError(
                "configuration migration failed and rollback could not be completed"
            ) from rollback_error
        raise ConfigMigrationError(
            "configuration migration failed; the original file was restored"
        ) from migration_error

    return MigrationResult(
        config=config,
        migrated=True,
        source_version=source_version,
        target_version=CURRENT_SCHEMA_VERSION,
        backup_path=backup_path,
    )
