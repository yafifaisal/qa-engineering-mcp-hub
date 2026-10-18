"""Security regression tests for the local-only Milestone 00 boundary."""

import sys

from qa_mcp_hub.config import HubSettings
from qa_mcp_hub.server import mcp


def test_settings_have_no_secret_fields() -> None:
    field_names = set(HubSettings.model_fields)
    forbidden = {"password", "secret", "token", "api_key", "credential"}
    assert field_names.isdisjoint(forbidden)


def test_server_has_no_remote_transport_configuration() -> None:
    assert mcp.name == "QA Engineering MCP Hub"
    assert HubSettings().transport == "stdio"


def test_runtime_does_not_import_future_domains() -> None:
    future_domains = (
        "qa_mcp_hub.adapters",
        "qa_mcp_hub.auth",
        "qa_mcp_hub.evidence",
        "qa_mcp_hub.knowledge",
        "qa_mcp_hub.planning",
        "qa_mcp_hub.providers",
        "qa_mcp_hub.release",
        "qa_mcp_hub.repositories",
        "qa_mcp_hub.runners",
        "qa_mcp_hub.storage",
        "qa_mcp_hub.suites",
        "qa_mcp_hub.verification",
        "qa_mcp_hub.workflows",
    )
    loaded = set(sys.modules)
    assert not any(
        module == domain or module.startswith(f"{domain}.")
        for domain in future_domains
        for module in loaded
    )
