"""Integration tests for the Typer command surface."""

import pytest
from typer.testing import CliRunner

from qa_mcp_hub.cli import app

runner = CliRunner()


def test_help_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "QA Engineering MCP Hub" in result.output
    assert "serve" in result.output


def test_standalone_version_option() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_doctor_command() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "not implemented" in result.output
    assert "Transport: stdio" in result.output


def test_doctor_reports_invalid_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_MCP_LOG_LEVEL", "TRACE")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 2
    assert "Configuration error: invalid QA MCP configuration" in result.output


def test_capabilities_command() -> None:
    result = runner.invoke(app, ["capabilities"])
    assert result.exit_code == 0
    assert "hub_health" in result.output
    assert "profiles_and_credentials" in result.output
