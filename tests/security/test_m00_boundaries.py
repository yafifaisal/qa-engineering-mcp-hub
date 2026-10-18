"""Security regression tests for the local-only M00/M01 runtime boundary."""

import json
import subprocess
import sys
from pathlib import Path

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
    """A server process may load registered E2E verification, not later domains."""
    project_root = Path(__file__).resolve().parents[2]
    probe = """
import json
import sys
import qa_mcp_hub.server

future_domains = (
    "qa_mcp_hub.evidence",
    "qa_mcp_hub.release",
    "qa_mcp_hub.storage.artifact_store",
)
loaded = set(sys.modules)
forbidden = sorted(
    module
    for module in loaded
    if any(
        module == domain or module.startswith(f"{domain}.")
        for domain in future_domains
    )
)
print(json.dumps({
    "forbidden": forbidden,
    "config_loaded": "qa_mcp_hub.config" in loaded,
    "auth_loaded": "qa_mcp_hub.auth" in loaded,
}))
"""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and probe
        [sys.executable, "-c", probe],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["config_loaded"] is True
    assert result["auth_loaded"] is True
    assert result["forbidden"] == []
