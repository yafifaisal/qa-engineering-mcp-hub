"""Installed metadata and package import tests."""

from importlib.metadata import distribution

import qa_mcp_hub
from qa_mcp_hub.cli.main import main


def test_package_imports() -> None:
    assert qa_mcp_hub.__version__ == "0.1.0"
    assert callable(main)


def test_console_entrypoint_metadata() -> None:
    metadata = distribution("qa-engineering-mcp-hub")
    assert metadata.version == qa_mcp_hub.__version__
    assert metadata.metadata["License-Expression"] == "MIT"
    entry_points = {
        entry.name: entry.value
        for entry in metadata.entry_points
        if entry.group == "console_scripts"
    }
    assert entry_points["qa-mcp"] == "qa_mcp_hub.cli.main:main"
