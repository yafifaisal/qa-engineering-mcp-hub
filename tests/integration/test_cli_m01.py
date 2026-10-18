"""CLI tests for Milestone 01 setup, profiles, credentials, and client files."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from typer.testing import CliRunner

from qa_mcp_hub.auth.models import CredentialReference, CredentialStoreKind
from qa_mcp_hub.cli import app
from qa_mcp_hub.config import load_config, resolve_config
from qa_mcp_hub.config.writer import ConfigWriteError

runner = CliRunner()
ENV_FIXTURE = "env-fixture-value"
KEYRING_FIXTURE = "keyring-fixture-value"


def _config_args(path: Path) -> list[str]:
    return ["--config", str(path)]


def test_setup_wizard_is_idempotent_and_can_be_cancelled(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    cancelled = runner.invoke(app, ["setup", *_config_args(path)], input="")
    assert cancelled.exit_code != 0
    assert not path.exists()

    created = runner.invoke(
        app,
        ["setup", *_config_args(path)],
        input="qa-lab\n\n",
    )
    assert created.exit_code == 0, created.output
    assert "created" in created.output
    assert load_config(path).active_profile == "qa-lab"

    reused = runner.invoke(
        app,
        ["setup", "--non-interactive", "--profile", "qa-lab", *_config_args(path)],
    )
    assert reused.exit_code == 0, reused.output
    assert "reused" in reused.output
    assert list(load_config(path).profiles) == ["qa-lab"]


def test_profile_commands_reject_duplicates_and_keep_snapshots(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    created = runner.invoke(
        app,
        ["profiles", "add", "alpha", "--use", *_config_args(path)],
    )
    assert created.exit_code == 0, created.output
    original = path.read_text(encoding="utf-8")
    duplicate = runner.invoke(
        app,
        ["profiles", "add", "alpha", *_config_args(path)],
    )
    assert duplicate.exit_code == 2
    assert path.read_text(encoding="utf-8") == original

    added = runner.invoke(app, ["profiles", "add", "beta", *_config_args(path)])
    assert added.exit_code == 0, added.output
    first = resolve_config(load_config(path), environ={})
    selected = runner.invoke(app, ["profiles", "use", "beta", *_config_args(path)])
    assert selected.exit_code == 0, selected.output
    assert first.active_profile == "alpha"
    assert resolve_config(load_config(path), environ={}).active_profile == "beta"

    shown = runner.invoke(app, ["profiles", "show", "alpha", *_config_args(path)])
    assert shown.exit_code == 0, shown.output
    assert "alpha" in shown.output
    edited = runner.invoke(
        app,
        [
            "profiles",
            "edit",
            "alpha",
            "--description",
            "password=must-not-remain-visible",
            *_config_args(path),
        ],
    )
    assert edited.exit_code == 0, edited.output
    rendered = runner.invoke(app, ["config", "show", *_config_args(path)])
    assert rendered.exit_code == 0, rendered.output
    assert "must-not-remain-visible" not in rendered.output
    assert "[REDACTED]" in rendered.output


def test_same_provider_can_have_isolated_connections(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    assert (
        runner.invoke(
            app, ["profiles", "add", "alpha", "--use", *_config_args(path)]
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(app, ["profiles", "add", "beta", *_config_args(path)]).exit_code
        == 0
    )
    for connection_id, profile in (
        ("github-alpha", "alpha"),
        ("github-beta", "beta"),
    ):
        result = runner.invoke(
            app,
            [
                "integrations",
                "add",
                connection_id,
                "--provider",
                "github",
                "--profile",
                profile,
                "--base-url",
                "https://api.github.com",
                "--account",
                profile,
                "--auth-kind",
                "pat",
                *_config_args(path),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "NOT_IMPLEMENTED" in result.output
    config = load_config(path)
    assert [item.provider.value for item in config.connections] == ["github", "github"]
    blocked = runner.invoke(
        app,
        ["profiles", "remove", "alpha", "--force-active", *_config_args(path)],
    )
    assert blocked.exit_code == 2
    assert "alpha" in load_config(path).profiles


def test_environment_credentials_stay_out_of_files_and_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "config.yaml"
    monkeypatch.setenv("QA_MCP_GITHUB_TOKEN", ENV_FIXTURE)
    assert (
        runner.invoke(
            app, ["profiles", "add", "alpha", "--use", *_config_args(path)]
        ).exit_code
        == 0
    )
    added = runner.invoke(
        app,
        [
            "integrations",
            "add",
            "github-main",
            "--provider",
            "github",
            "--base-url",
            "https://api.github.com",
            "--account",
            "qa-user",
            "--auth-kind",
            "pat",
            *_config_args(path),
        ],
    )
    assert added.exit_code == 0, added.output
    authenticated = runner.invoke(
        app,
        [
            "integrations",
            "auth",
            "github-main",
            "--kind",
            "pat",
            "--store",
            "environment",
            "--reference",
            "QA_MCP_GITHUB_TOKEN",
            *_config_args(path),
        ],
    )
    assert authenticated.exit_code == 0, authenticated.output
    stored = path.read_text(encoding="utf-8")
    assert ENV_FIXTURE not in stored
    assert ENV_FIXTURE not in authenticated.output
    assert "QA_MCP_GITHUB_TOKEN" in stored

    tested = runner.invoke(
        app,
        ["integrations", "test", "github-main", *_config_args(path)],
    )
    assert tested.exit_code == 0, tested.output
    assert "Credential readiness: PRESENT" in tested.output
    assert "Provider network connectivity: NOT_IMPLEMENTED" in tested.output
    assert ENV_FIXTURE not in tested.output

    monkeypatch.delenv("QA_MCP_GITHUB_TOKEN")
    missing = runner.invoke(
        app,
        ["integrations", "test", "github-main", *_config_args(path)],
    )
    assert missing.exit_code == 1
    assert "Credential is missing" in missing.output
    assert "NOT_IMPLEMENTED" in missing.output


def test_keyring_auth_is_scoped_and_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "config.yaml"
    values: dict[str, str] = {}

    class _FakeKeyring:
        kind = CredentialStoreKind.keyring

        def get(self, reference: CredentialReference) -> str | None:
            return values.get(reference.scope.storage_key(reference.reference))

        def set(self, reference: CredentialReference, secret: str) -> None:
            values[reference.scope.storage_key(reference.reference)] = secret

        def delete(self, reference: CredentialReference) -> None:
            values.pop(reference.scope.storage_key(reference.reference), None)

    monkeypatch.setattr(
        "qa_mcp_hub.cli.integrations.KeyringCredentialStore",
        _FakeKeyring,
    )
    for profile in ("alpha", "beta"):
        assert (
            runner.invoke(
                app,
                ["profiles", "add", profile, *_config_args(path)],
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                app,
                [
                    "integrations",
                    "add",
                    f"github-{profile}",
                    "--provider",
                    "github",
                    "--profile",
                    profile,
                    "--auth-kind",
                    "pat",
                    *_config_args(path),
                ],
            ).exit_code
            == 0
        )
        authenticated = runner.invoke(
            app,
            [
                "integrations",
                "auth",
                f"github-{profile}",
                "--kind",
                "pat",
                "--store",
                "keyring",
                *_config_args(path),
            ],
            input=f"{profile}-{KEYRING_FIXTURE}\n{profile}-{KEYRING_FIXTURE}\n",
        )
        assert authenticated.exit_code == 0, authenticated.output
        assert KEYRING_FIXTURE not in authenticated.output
        assert KEYRING_FIXTURE not in path.read_text(encoding="utf-8")
    assert len(values) == 2
    assert len(set(values.values())) == 2

    def fail_write(config: object, destination: Path | None) -> Path:
        del config, destination
        raise ConfigWriteError("cannot atomically write configuration")

    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr("qa_mcp_hub.cli.integrations.persist_config", fail_write)
    rotated = runner.invoke(
        app,
        ["integrations", "rotate", "github-alpha", *_config_args(path)],
        input="replacement-value\nreplacement-value\n",
    )
    assert rotated.exit_code == 2
    assert "replacement-value" not in rotated.output
    assert path.read_text(encoding="utf-8") == before
    assert values
    assert "replacement-value" not in values.values()


def test_oauth_reference_does_not_claim_provider_connectivity(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    assert (
        runner.invoke(
            app, ["profiles", "add", "alpha", "--use", *_config_args(path)]
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "integrations",
                "add",
                "google-docs",
                "--provider",
                "google_docs",
                "--auth-kind",
                "oauth",
                *_config_args(path),
            ],
        ).exit_code
        == 0
    )
    authenticated = runner.invoke(
        app,
        [
            "integrations",
            "auth",
            "google-docs",
            "--kind",
            "oauth",
            "--store",
            "oauth_reference",
            "--reference",
            "pending",
            *_config_args(path),
        ],
    )
    assert authenticated.exit_code == 0, authenticated.output
    assert "NOT_IMPLEMENTED" in authenticated.output
    tested = runner.invoke(
        app,
        ["integrations", "test", "google-docs", *_config_args(path)],
    )
    assert tested.exit_code == 1
    assert "NOT_IMPLEMENTED" in tested.output


def test_client_generation_parses_and_contains_no_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QA_MCP_GITHUB_TOKEN", ENV_FIXTURE)
    codex = runner.invoke(app, ["clients", "generate", "codex"])
    assert codex.exit_code == 0, codex.output
    parsed = tomllib.loads(codex.stdout)
    server = parsed["mcp_servers"]["qa_hub"]
    assert server["command"] == "qa-mcp"
    assert server["args"] == ["serve"]
    assert "env" not in server
    assert ENV_FIXTURE not in codex.stdout

    vscode = runner.invoke(app, ["clients", "generate", "vscode"])
    assert vscode.exit_code == 0, vscode.output
    document = json.loads(vscode.stdout)
    assert document["servers"]["qa_hub"]["type"] == "stdio"
    assert document["servers"]["qa_hub"]["args"] == ["serve"]
    assert ENV_FIXTURE not in vscode.stdout

    cursor = runner.invoke(app, ["clients", "generate", "cursor"])
    assert cursor.exit_code == 0, cursor.output
    cursor_document = json.loads(cursor.stdout)
    cursor_server = cursor_document["mcpServers"]["qa_hub"]
    assert cursor_server["type"] == "stdio"
    assert cursor_server["command"] == "uv"
    assert cursor_server["args"] == [
        "run",
        "--project",
        "${workspaceFolder}",
        "qa-mcp",
        "serve",
    ]
    assert "env" not in cursor_server
    assert ENV_FIXTURE not in cursor.stdout
    root = Path(__file__).resolve().parents[2]
    assert (root / "config" / "examples" / "cursor.example.json").read_text(
        encoding="utf-8"
    ) == cursor.stdout
    assert (root / ".cursor" / "mcp.json").read_text(encoding="utf-8") == cursor.stdout


def test_cursor_install_preserves_unrelated_servers(tmp_path: Path) -> None:
    destination = tmp_path / "mcp.json"
    destination.write_text(
        json.dumps({"mcpServers": {"other": {"command": "other"}}}) + "\n",
        encoding="utf-8",
    )
    installed = runner.invoke(
        app,
        ["clients", "install", "cursor", "--path", str(destination)],
    )
    assert installed.exit_code == 0, installed.output
    document = json.loads(destination.read_text(encoding="utf-8"))
    assert document["mcpServers"]["other"]["command"] == "other"
    assert document["mcpServers"]["qa_hub"]["type"] == "stdio"
    assert "env" not in document["mcpServers"]["qa_hub"]
    current = runner.invoke(
        app,
        ["clients", "install", "cursor", "--path", str(destination)],
    )
    assert current.exit_code == 0, current.output
    assert "Already current" in current.output


def test_client_install_preserves_unrelated_settings(tmp_path: Path) -> None:
    destination = tmp_path / "mcp.json"
    destination.write_text(
        json.dumps({"theme": "dark", "servers": {"other": {"command": "other"}}})
        + "\n",
        encoding="utf-8",
    )
    installed = runner.invoke(
        app,
        ["clients", "install", "vscode", "--path", str(destination)],
    )
    assert installed.exit_code == 0, installed.output
    document = json.loads(destination.read_text(encoding="utf-8"))
    assert document["theme"] == "dark"
    assert document["servers"]["other"]["command"] == "other"
    assert document["servers"]["qa_hub"]["command"] == "qa-mcp"
    current = runner.invoke(
        app,
        ["clients", "install", "vscode", "--path", str(destination)],
    )
    assert current.exit_code == 0, current.output
    assert "Already current" in current.output


def test_config_validation_hides_malformed_values(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("schema_version: [\n  do-not-echo-this\n", encoding="utf-8")
    result = runner.invoke(app, ["config", "validate", *_config_args(path)])
    assert result.exit_code == 2
    assert "do-not-echo-this" not in result.output
    assert "malformed" in result.output


def test_doctor_reports_invalid_user_configuration_without_secrets(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.yaml"
    rejected = "qa_mcp_do_not_echo"
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "token": rejected}),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["doctor", *_config_args(path)])
    assert result.exit_code == 1
    assert "User configuration: INVALID" in result.output
    assert rejected not in result.output
    assert "NOT_IMPLEMENTED" in result.output
