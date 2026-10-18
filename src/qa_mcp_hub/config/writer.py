"""Atomic, permission-restricted persistence for non-secret configuration.

Purpose: replace configuration files atomically with owner-only permissions.
Milestone: 01
Status: IMPLEMENTED
Ownership: config.writer
Dependencies: pathlib, os, and PyYAML.
Expected tests: round-trip persistence, permissions, and temporary-file cleanup.
"""

import os
import tempfile
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from qa_mcp_hub.config.models import HubConfig
from qa_mcp_hub.config.paths import default_config_path

CONFIG_FILE_MODE = 0o600
CONFIG_DIRECTORY_MODE = 0o700


class ConfigWriteError(OSError):
    """Raised when an atomic configuration write cannot be completed."""


class _NoAliasDumper(yaml.SafeDumper):  # type: ignore[misc]
    """Produce explicit YAML rather than anchors tied to Python object identity."""

    def ignore_aliases(self, data: object) -> bool:
        del data
        return True


def serialize_config(config: HubConfig) -> str:
    """Serialize a validated configuration without Python-specific YAML tags."""
    document = config.model_dump(mode="json", exclude_none=True)
    return str(
        yaml.dump(
            document,
            Dumper=_NoAliasDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    )


def _secure_chmod(path: Path, mode: int) -> None:
    """Apply POSIX permissions where meaningful; Windows ACLs are OS-managed."""
    try:
        path.chmod(mode)
    except OSError as exc:
        if os.name != "nt":
            raise ConfigWriteError(f"cannot secure configuration path: {path}") from exc


def atomic_write_text(path: Path, text: str) -> None:
    """Replace ``path`` atomically with UTF-8 text and owner-only permissions."""
    parent = path.parent
    parent_existed = parent.exists()
    try:
        parent.mkdir(mode=CONFIG_DIRECTORY_MODE, parents=True, exist_ok=True)
        # Never chmod an arbitrary existing parent (for example /tmp). A newly
        # created native application directory is private from its first write.
        if not parent_existed:
            _secure_chmod(parent, CONFIG_DIRECTORY_MODE)
    except OSError as exc:
        raise ConfigWriteError(
            f"cannot prepare configuration directory: {parent}"
        ) from exc

    file_descriptor = -1
    temporary_path: Path | None = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            text=True,
        )
        temporary_path = Path(temporary_name)
        if hasattr(os, "fchmod"):
            os.fchmod(file_descriptor, CONFIG_FILE_MODE)
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as stream:
            file_descriptor = -1
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        _secure_chmod(path, CONFIG_FILE_MODE)
    except OSError as exc:
        raise ConfigWriteError(
            f"cannot atomically write configuration: {path}"
        ) from exc
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def save_config(config: HubConfig, path: Path | None = None) -> Path:
    """Persist an already validated configuration and return its final path."""
    config_path = path if path is not None else default_config_path()
    # Revalidation catches unsafe mutation of nested dictionaries by callers.
    validated = HubConfig.model_validate(config.model_dump(mode="python"))
    atomic_write_text(config_path, serialize_config(validated))
    return config_path
