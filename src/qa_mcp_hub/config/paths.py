"""Cross-platform user configuration path resolution.

Purpose: choose native application config paths without hardcoded user homes.
Milestone: 00
Status: IMPLEMENTED
Ownership: config.path_resolution
Dependencies: pathlib and platformdirs.
Expected tests: native lookup plus simulated Windows, macOS, and Linux behavior.
"""

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from platformdirs import user_config_path

APP_NAME = "qa-mcp-hub"
CONFIG_FILENAME = "config.yaml"


def default_config_dir(
    home: Path | None = None,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the native config directory or a deterministic simulated path.

    Passing ``home`` or ``platform`` is intended for tests and documentation. A
    normal runtime call delegates to platformdirs.
    """
    if home is None and platform is None and environ is None:
        # ``roaming=True`` is material on Windows: it selects APPDATA instead of
        # LOCALAPPDATA and therefore matches the deterministic simulation below.
        return user_config_path(
            APP_NAME,
            appauthor=False,
            roaming=True,
            ensure_exists=False,
        )

    platform_name = platform or sys.platform
    base_home = home or Path.home()
    environment = environ if environ is not None else os.environ
    if platform_name == "win32":
        roaming = Path(
            environment.get("APPDATA", str(base_home / "AppData" / "Roaming"))
        )
        return roaming / APP_NAME
    if platform_name == "darwin":
        return base_home / "Library" / "Application Support" / APP_NAME
    xdg_root = Path(environment.get("XDG_CONFIG_HOME", str(base_home / ".config")))
    return xdg_root / APP_NAME


def default_config_path(
    home: Path | None = None,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the native path of the consolidated user configuration file."""
    return (
        default_config_dir(home=home, platform=platform, environ=environ)
        / CONFIG_FILENAME
    )
