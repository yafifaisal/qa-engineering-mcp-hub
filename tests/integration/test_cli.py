from typer.testing import CliRunner

from qa_mcp_hub.cli import app

runner = CliRunner()


def test_doctor_command() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "not implemented" in result.output


def test_capabilities_command() -> None:
    result = runner.invoke(app, ["capabilities"])
    assert result.exit_code == 0
    assert "hub_health" in result.output
    assert "profiles_and_credentials" in result.output
