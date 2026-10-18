"""Milestone 00 settings loader.

Purpose: provide one typed construction boundary for environment-backed settings.
Milestone: 00
Status: IMPLEMENTED
Ownership: config.settings_loader
Dependencies: local Pydantic settings model.
Expected tests: default and explicit override loading with validation errors.
"""

from typing import Any

from pydantic import ValidationError

from qa_mcp_hub.config.models import HubSettings


class SettingsLoadError(ValueError):
    """Raised when non-secret process configuration is invalid."""


def load_settings(**overrides: Any) -> HubSettings:
    """Load validated settings and expose a stable configuration error boundary."""
    try:
        return HubSettings(**overrides)
    except ValidationError as exc:
        raise SettingsLoadError("invalid QA MCP configuration") from exc
