"""Strict loaders for process settings and non-secret YAML configuration.

Configuration errors deliberately omit submitted values. A malformed document can
contain a credential pasted by mistake, so propagating raw YAML or Pydantic error
text would violate the command-line and logging redaction boundary.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError
from yaml.constructor import ConstructorError  # type: ignore[import-untyped]
from yaml.nodes import MappingNode  # type: ignore[import-untyped]

from qa_mcp_hub.config.models import HubConfig, HubSettings
from qa_mcp_hub.config.paths import default_config_path

MAX_CONFIG_BYTES = 1_048_576


class SettingsLoadError(ValueError):
    """Raised when non-secret process configuration is invalid."""


class ConfigLoadError(ValueError):
    """Base error for safe YAML configuration loading."""


class ConfigNotFoundError(ConfigLoadError):
    """Raised when the requested configuration file does not exist."""


class DuplicateKeyError(ConfigLoadError):
    """Raised when YAML contains an ambiguous duplicate mapping key."""


class _UniqueKeyLoader(yaml.SafeLoader):  # type: ignore[misc]
    """Safe YAML loader that rejects duplicate mapping keys at every depth."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found a duplicate mapping key",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_settings(**overrides: Any) -> HubSettings:
    """Load validated settings and expose a stable configuration error boundary."""
    try:
        return HubSettings(**overrides)
    except ValidationError as exc:
        raise SettingsLoadError("invalid QA MCP configuration") from exc


def load_yaml_text(text: str) -> dict[str, Any]:
    """Parse one safe YAML mapping while rejecting duplicate keys."""
    if len(text.encode("utf-8")) > MAX_CONFIG_BYTES:
        raise ConfigLoadError("configuration exceeds the 1 MiB size limit")
    try:
        # The custom loader subclasses SafeLoader solely to reject duplicate keys.
        value = yaml.load(text, Loader=_UniqueKeyLoader)  # noqa: S506
    except ConstructorError as exc:
        if "duplicate mapping key" in str(exc):
            raise DuplicateKeyError("configuration contains a duplicate key") from None
        raise ConfigLoadError("configuration YAML has an invalid mapping") from None
    except yaml.YAMLError:
        raise ConfigLoadError("configuration YAML is malformed") from None
    if not isinstance(value, Mapping):
        raise ConfigLoadError("configuration root must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise ConfigLoadError("configuration keys must be strings")
    return dict(value)


def load_yaml_document(path: Path) -> dict[str, Any]:
    """Read and parse a YAML mapping from ``path`` without exposing its content."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigNotFoundError(f"configuration file not found: {path}") from None
    except OSError:
        raise ConfigLoadError(f"configuration file cannot be read: {path}") from None
    return load_yaml_text(raw)


def parse_config(document: Mapping[str, Any]) -> HubConfig:
    """Validate a current-version configuration mapping."""
    try:
        return HubConfig.model_validate(dict(document))
    except ValidationError as exc:
        # Do not include ``str(exc)``: Pydantic includes rejected input values.
        raise ConfigLoadError("configuration does not match schema version 1") from exc


def load_config(path: Path | None = None) -> HubConfig:
    """Load the consolidated, current-version YAML configuration."""
    config_path = path if path is not None else default_config_path()
    return parse_config(load_yaml_document(config_path))
