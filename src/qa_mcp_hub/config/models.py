"""Typed non-secret configuration models.

Purpose: validate the local server settings implemented in Milestone 00.
Milestone: 00
Status: IMPLEMENTED
Ownership: config.settings_models
Dependencies: Pydantic v2 and pydantic-settings v2.
Expected tests: defaults, environment overrides, forbidden secret-shaped fields,
and validation failures.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HubSettings(BaseSettings):
    """Minimal local settings; credentials are deliberately not fields."""

    model_config = SettingsConfigDict(
        env_prefix="QA_MCP_",
        extra="ignore",
        case_sensitive=False,
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    server_name: str = Field(default="QA Engineering MCP Hub", min_length=1)
    transport: Literal["stdio"] = "stdio"
