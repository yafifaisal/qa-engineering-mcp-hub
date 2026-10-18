"""External-company onboarding through the public CLI. No provider is contacted."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from typer.testing import CliRunner

from qa_mcp_hub.cli.main import app
from qa_mcp_hub.config.loader import load_config
from qa_mcp_hub.evidence.service import generate_evidence
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.workflows.models import (
    ApiOnlyEvidence,
    ExecutionRecord,
    ExecutionStatus,
    StepEvidence,
)

runner = CliRunner()
NOW = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)
REVISION = "b" * 40
WORKFLOW = """\
schema_version: 1
id: {workflow_id}
name: {workflow_id}
description: Disabled onboarding example.
implementation_status: IMPLEMENTED
enabled: false
approved: false
required_capabilities: [api_automation]
evidence_policy: api-only
steps:
  - id: execute-api-suite
    kind: api_suite
    target: example-api-smoke
    depends_on: []
    assertion_ids: [status-ok]
"""


def test_company_profiles_stay_separated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.yaml"
    company_a = _workspace(tmp_path / "company-a", "company-a-api")
    company_c = _workspace(tmp_path / "company-c", "company-c-api")
    _setup(config_path, "company-a", company_a)
    _setup(config_path, "company-c", company_c)
    _connect(
        config_path,
        "company-a",
        (
            ("a-github", "github", "cloud", None, "pat", "QA_MCP_COMPANY_A_GITHUB"),
            ("a-jira", "jira", "cloud", "https://a.example.com", "pat", None),
            ("a-postman", "postman", "local", None, "none", None),
            ("a-postgres", "postgresql", "local", None, "none", None),
            ("a-kafka", "kafka", "local", None, "none", None),
            ("a-actions", "github_actions", "cloud", None, "none", None),
            (
                "a-testrail",
                "testrail",
                "cloud",
                "https://a.example.com",
                "api_token",
                "QA_MCP_COMPANY_A_TESTRAIL",
            ),
        ),
    )
    _connect(
        config_path,
        "company-c",
        (
            (
                "c-gitlab",
                "gitlab",
                "cloud",
                "https://c.example.com",
                "pat",
                "QA_MCP_COMPANY_C_GITLAB",
            ),
            ("c-jira", "jira", "cloud", "https://c.example.com", "pat", None),
            ("c-bruno", "bruno", "local", None, "none", None),
            ("c-mysql", "mysql", "local", None, "none", None),
            ("c-kafka", "kafka", "local", None, "none", None),
            (
                "c-jenkins",
                "jenkins",
                "self_managed",
                "https://c.example.com",
                "api_token",
                None,
            ),
            ("c-xray", "xray", "cloud", "https://c.example.com", "none", None),
        ),
    )
    _repository(config_path, "company-a", "a-billing", "company-a/billing", "a-github")
    _repository(config_path, "company-c", "c-billing", "company-c/billing", "c-gitlab")

    listed_a = _invoke(
        ["integrations", "list", "--profile", "company-a", "--config", str(config_path)]
    )
    listed_c = _invoke(
        ["integrations", "list", "--profile", "company-c", "--config", str(config_path)]
    )
    assert "github" in listed_a and "testrail" in listed_a
    assert "gitlab" not in listed_a and "xray" not in listed_a
    assert "gitlab" in listed_c and "xray" in listed_c
    assert "github" not in listed_c and "testrail" not in listed_c

    repos_a = _invoke(
        ["repositories", "list", "--profile", "company-a", "--config", str(config_path)]
    )
    repos_c = _invoke(
        ["repositories", "list", "--profile", "company-c", "--config", str(config_path)]
    )
    assert "a-billing" in repos_a and "c-billing" not in repos_a
    assert "c-billing" in repos_c and "a-billing" not in repos_c

    flows_a = _invoke(
        ["workflows", "list", "--profile", "company-a", "--config", str(config_path)]
    )
    flows_c = _invoke(
        ["workflows", "list", "--profile", "company-c", "--config", str(config_path)]
    )
    assert "company-a-api" in flows_a and "none were executed" in flows_a
    assert "company-c-api" not in flows_a
    assert "company-c-api" in flows_c and "company-a-api" not in flows_c

    missing = runner.invoke(
        app,
        ["integrations", "test", "a-github", "--config", str(config_path)],
    )
    assert missing.exit_code == 1
    assert "NOT_IMPLEMENTED" in missing.output
    monkeypatch.setenv("QA_MCP_COMPANY_A_GITHUB", "qa_mcp_company_a_value")
    present = runner.invoke(
        app,
        ["integrations", "test", "a-github", "--config", str(config_path)],
    )
    assert present.exit_code == 0, present.output
    assert "PRESENT" in present.output
    assert "qa_mcp_company_a_value" not in present.output
    assert "qa_mcp_company_a_value" not in config_path.read_text(encoding="utf-8")

    store_path = tmp_path / "runs.sqlite"
    monkeypatch.setenv("QA_MCP_EXECUTION_PATH", str(store_path))
    store = ExecutionStore(store_path)
    store.save(_record("company-a", "a-run"))
    store.save(_record("company-c", "c-run"))
    config = load_config(config_path)
    manifest_a = generate_evidence(
        "a-run", "api-only", profile="company-a", config=config
    )
    manifest_c = generate_evidence(
        "c-run", "api-only", profile="company-c", config=config
    )
    assert manifest_a.profile_id == "company-a"
    assert manifest_c.profile_id == "company-c"
    assert (company_a / "evidence" / "artifacts" / "a-run" / "report.json").is_file()
    assert not (company_a / "evidence" / "artifacts" / "c-run").exists()
    assert (company_c / "evidence" / "artifacts" / "c-run" / "report.json").is_file()
    assert not (company_c / "evidence" / "artifacts" / "a-run").exists()

    config_path.unlink()
    absent = runner.invoke(app, ["doctor", "--config", str(config_path)])
    assert absent.exit_code == 0
    assert "User configuration: absent" in absent.output
    _setup(config_path, "company-a", company_a)
    loaded = load_config(config_path)
    assert loaded.schema_version == 1
    assert "company-a" in loaded.profiles


def _setup(config_path: Path, profile: str, workspace: Path) -> None:
    _invoke(
        [
            "setup",
            "--non-interactive",
            "--profile",
            profile,
            "--workspace",
            str(workspace),
            "--config",
            str(config_path),
        ]
    )


def _connect(
    config_path: Path,
    profile: str,
    rows: tuple[tuple[str, str, str, str | None, str, str | None], ...],
) -> None:
    for connection_id, provider, deployment, base_url, auth_kind, reference in rows:
        command = [
            "integrations",
            "add",
            connection_id,
            "--provider",
            provider,
            "--profile",
            profile,
            "--deployment",
            deployment,
            "--auth-kind",
            auth_kind,
            "--config",
            str(config_path),
        ]
        if base_url is not None:
            command.extend(["--base-url", base_url])
        _invoke(command)
        if reference is None:
            continue
        _invoke(
            [
                "integrations",
                "auth",
                connection_id,
                "--kind",
                auth_kind,
                "--store",
                "environment",
                "--reference",
                reference,
                "--config",
                str(config_path),
            ]
        )


def _repository(
    config_path: Path,
    profile: str,
    repository_id: str,
    remote: str,
    connection: str,
) -> None:
    _invoke(
        [
            "repositories",
            "add",
            repository_id,
            "--remote",
            remote,
            "--connection",
            connection,
            "--profile",
            profile,
            "--config",
            str(config_path),
        ]
    )


def _workspace(path: Path, workflow_id: str) -> Path:
    policies = path / "evidence-policies"
    policies.mkdir(parents=True)
    source = Path("templates/qa-workspace/evidence-policies")
    for item in source.glob("*.yaml"):
        shutil.copy(item, policies / item.name)
    workflow_dir = path / "workflows" / "api"
    workflow_dir.mkdir(parents=True)
    document = WORKFLOW.format(workflow_id=workflow_id)
    yaml.safe_load(document)
    (workflow_dir / "api-only.yaml").write_text(document, encoding="utf-8")
    return path


def _record(profile_id: str, execution_id: str) -> ExecutionRecord:
    evidence = ApiOnlyEvidence(
        execution_id=execution_id,
        profile_id=profile_id,
        workflow_id=f"{profile_id}-api",
        suite_ids=("example-api-smoke",),
        suite_version="1",
        source_revision=REVISION,
        checks=("api",),
        assertion_total=1,
        assertion_failed=0,
        status=ExecutionStatus.passed,
        runner_exit_code=0,
        runner_completed=True,
    )
    return ExecutionRecord(
        execution_id=execution_id,
        profile_id=profile_id,
        workflow_id=f"{profile_id}-api",
        suite_ids=("example-api-smoke",),
        suite_version="1",
        source_revision=REVISION,
        status=ExecutionStatus.passed,
        assertion_status=ExecutionStatus.passed,
        runner_completed=True,
        runner_exit_code=0,
        transitions=("QUEUED", "PASSED"),
        queued_at=NOW,
        started_at=NOW,
        finished_at=NOW,
        evidence=evidence,
        excerpt="status=ok",
        step_results=(
            StepEvidence(
                step_id="api",
                kind="api_suite",
                target="example-api-smoke",
                status=ExecutionStatus.passed,
                executed=True,
                verified=True,
                reason="observed",
                evidence_ref="step-ref",
            ),
        ),
    )


def _invoke(command: list[str]) -> str:
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output
    return result.output
