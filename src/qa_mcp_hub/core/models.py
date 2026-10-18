"""Shared provider identity and compatibility imports.

``qa_mcp_hub.config.models`` owns the Milestone 01 configuration schema. The
provider enum remains in ``core`` because authentication and configuration both
depend on it. Legacy ``Connection``, ``Profile``, and ``HubConfig`` imports are
resolved lazily so existing callers receive the canonical models without
creating a ``config.models -> core.models -> config.models`` import cycle.
"""

from enum import StrEnum
from typing import TYPE_CHECKING
from warnings import warn

from pydantic import BaseModel

if TYPE_CHECKING:
    from qa_mcp_hub.config.models import ConnectionConfig as Connection
    from qa_mcp_hub.config.models import HubConfig
    from qa_mcp_hub.config.models import ProfileConfig as Profile


class ProviderKind(StrEnum):
    """Provider identifiers accepted by the versioned configuration schema."""

    github = "github"
    gitlab = "gitlab"
    bitbucket = "bitbucket"
    jira = "jira"
    confluence = "confluence"
    google_docs = "google_docs"
    bruno = "bruno"
    postman = "postman"
    postgresql = "postgresql"
    mysql = "mysql"
    kafka = "kafka"
    bitbucket_pipelines = "bitbucket_pipelines"
    github_actions = "github_actions"
    jenkins = "jenkins"
    xray = "xray"
    testrail = "testrail"
    spreadsheet = "spreadsheet"
    google_sheets = "google_sheets"


_LEGACY_MODEL_NAMES = frozenset({"Connection", "Profile", "HubConfig"})


def __getattr__(name: str) -> type[BaseModel]:
    """Resolve removed legacy model names to their canonical M01 equivalents."""
    if name not in _LEGACY_MODEL_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    # Deliberately local: importing config models at module import time would be a
    # cycle because those models use ProviderKind from this module.
    from qa_mcp_hub.config.models import (
        ConnectionConfig,
        HubConfig,
        ProfileConfig,
    )

    aliases: dict[str, type[BaseModel]] = {
        "Connection": ConnectionConfig,
        "Profile": ProfileConfig,
        "HubConfig": HubConfig,
    }
    warn(
        f"qa_mcp_hub.core.models.{name} is deprecated; import the canonical "
        "model from qa_mcp_hub.config instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return aliases[name]


__all__ = ["Connection", "HubConfig", "Profile", "ProviderKind"]
