"""Shared pytest marker configuration for explicit transport evidence."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Document the real-subprocess stdio test separately from in-memory tests."""
    config.addinivalue_line(
        "markers",
        "stdio: launches the local MCP server through a real stdio subprocess",
    )
