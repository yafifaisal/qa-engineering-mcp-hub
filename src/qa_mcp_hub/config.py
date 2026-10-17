"""Typed, OS-aware, non-secret application configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_config_dir(home: Path | None = None, platform: str | None = None) -> Path:
    """Return a safe per-user configuration path on each operating system."""
    import os
    import sys

    platform_name = platform or sys.platform
    if home is not None:
        base_home = home
    else:
        base_home = Path.home()
    if platform_name == "win32":
        return (
            Path(os.environ.get("APPDATA", str(base_home / "AppData" / "Roaming")))
            / "qa-mcp-hub"
        )
    if platform_name == "darwin":
        return base_home / "Library" / "Application Support" / "qa-mcp-hub"
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", str(base_home / ".config")))
        / "qa-mcp-hub"
    )


class HubSettings(BaseSettings):
    """Minimal settings for M00. Credentials are explicitly out of scope."""

    model_config = SettingsConfigDict(env_prefix="QA_MCP_", extra="ignore")
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR)$")
    server_name: str = Field(default="QA Engineering MCP Hub", min_length=1)
