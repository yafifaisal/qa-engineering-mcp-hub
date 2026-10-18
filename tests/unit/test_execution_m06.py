"""Milestone 06 registered suite execution and API workflows."""

import json
import shutil
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastmcp import Client
from pydantic import ValidationError

from qa_mcp_hub.adapters.api_automation.bruno import bruno_arguments
from qa_mcp_hub.config.models import (
    CURRENT_SCHEMA_VERSION,
    ExecutionOverrides,
    ExecutionPreferences,
    HubConfig,
    ProfileConfig,
    QAWorkspaceReference,
)
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.mcp.tools.execution import submit_test_run_tool
from qa_mcp_hub.runners.execution_context import ExecutionContext
from qa_mcp_hub.runners.job_manager import JobManager
from qa_mcp_hub.runners.polling import poll_until
from qa_mcp_hub.runners.process_runner import run_process
from qa_mcp_hub.server import mcp
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.suites.registry import load_suite_registry
from qa_mcp_hub.workflows.dependency_validator import validate_workflow
from qa_mcp_hub.workflows.models import (
    ExecutionStatus,
    StepKind,
    WorkflowDefinition,
    WorkflowStep,
)
from qa_mcp_hub.workflows.service import ExecutionService
from qa_mcp_hub.workflows.state_machine import transition

_NOW = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)
_RUNNER_VALUE = "qa_mcp_runner_secret"
_FAKE = """\
import json, os, sys
from pathlib import Path
import time
here = Path(__file__).resolve().parent
mode = (here / "mode.txt").read_text(encoding="utf-8").strip()
(here / "argv.json").write_text(json.dumps(sys.argv), encoding="utf-8")
args = sys.argv[1:]
report = None
for flag in ("--reporter-json", "--reporter-json-export"):
    if flag in args:
        report = Path(args[args.index(flag) + 1])
        break
if mode == "sleep":
    time.sleep(30)
if mode == "leak":
    sys.stdout.write(os.environ.get("API_TOKEN", ""))
if report is not None and mode != "sleep":
    if mode == "invalid":
        report.write_text("{", encoding="utf-8")
    elif mode in {"fail", "fail-zero"}:
        if "--reporters" in args:
            body = {"run": {"executions": [{"assertions": [
                {"assertion": "status", "error": {"message": "no"}}
            ]}]}}
        else:
            body = {"results": [{"assertionResults": [
                {"description": "status", "status": "fail"}
            ]}]}
        report.write_text(json.dumps(body), encoding="utf-8")
    elif mode == "no-assert":
        report.write_text(json.dumps({"results": []}), encoding="utf-8")
    elif mode == "summary":
        report.write_text(json.dumps({
            "summary": {
                "totalAssertions": 1,
                "passedAssertions": 1,
                "failedAssertions": 0,
            }
        }), encoding="utf-8")
    else:
        if "--reporters" in args:
            body = {"run": {"executions": [{"assertions": [{"assertion": "status"}]}]}}
        else:
            body = {"results": [{"assertionResults": [
                {"description": "status", "status": "pass"}
            ]}]}
        report.write_text(json.dumps(body), encoding="utf-8")
if mode == "fail":
    raise SystemExit(1)
if mode == "nonzero":
    raise SystemExit(2)
"""


def _fake(directory: Path, mode: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "runner.py"
    script.write_text(_FAKE, encoding="utf-8")
    (directory / "mode.txt").write_text(mode, encoding="utf-8")
    return script


def _git(repo: Path, *args: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        pytest.skip("git is not available")
    completed = subprocess.run(  # noqa: S603 - fixed git arguments in a test
        [executable, "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.fail(completed.stderr)
    return completed.stdout.strip()


def _init_git(path: Path) -> None:
    executable = shutil.which("git")
    if executable is None:
        pytest.skip("git is not available")
    subprocess.run(  # noqa: S603 - git init with a fixed argument list
        [executable, "init", "-b", "main", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(path, "config", "user.email", "qa@example.invalid")
    _git(path, "config", "user.name", "QA")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "initial")


def _collection(workspace: Path, *, credentials: bool = False) -> None:
    bruno = workspace / "suites" / "bruno" / "billing"
    bruno.mkdir(parents=True)
    (bruno / "bruno.json").write_text(
        '{"version":"1","name":"billing","type":"collection"}\n',
        encoding="utf-8",
    )
    (bruno / "health.bru").write_text("meta {\n  name: health\n}\n", encoding="utf-8")
    postman = workspace / "suites" / "postman"
    postman.mkdir(parents=True)
    (postman / "billing.postman_collection.json").write_text(
        '{"info":{"name":"billing","schema":"https://schema.getpostman.com/json/collection/v2.1.0/collection.json"}}\n',
        encoding="utf-8",
    )
    binding = ""
    if credentials:
        binding = (
            "\n    credential_env:\n"
            "      - name: API_TOKEN\n"
            "        reference: billing-token"
        )
    (workspace / "suites" / "suites.yaml").write_text(
        "schema_version: 1\n"
        "implementation_status: IMPLEMENTED\n"
        "suites:\n"
        "  - id: billing-bruno\n"
        "    runner: bruno\n"
        "    path: suites/bruno/billing\n"
        "    environment: local\n"
        "    enabled: true\n"
        '    version: "1"\n'
        "    allowed_operation: read\n"
        "    assertion_ids: [status-ok]\n"
        f"{binding}\n"
        "  - id: billing-postman\n"
        "    runner: postman\n"
        "    path: suites/postman/billing.postman_collection.json\n"
        "    environment: local\n"
        "    enabled: true\n"
        '    version: "1"\n'
        "    allowed_operation: read\n"
        "    assertion_ids: [status-ok]\n",
        encoding="utf-8",
    )
    api = workspace / "workflows" / "api"
    api.mkdir(parents=True)
    (api / "billing.yaml").write_text(
        "schema_version: 1\n"
        "id: billing-api\n"
        "name: Billing API\n"
        "description: API-only billing checks\n"
        "implementation_status: IMPLEMENTED\n"
        "enabled: true\n"
        "approved: true\n"
        "evidence_policy: api-only\n"
        "steps:\n"
        "  - id: run-bruno\n"
        "    kind: api_suite\n"
        "    target: billing-bruno\n"
        "    depends_on: []\n"
        "    assertion_ids: [status-ok]\n",
        encoding="utf-8",
    )
    e2e = workspace / "workflows" / "e2e"
    e2e.mkdir(parents=True)
    (e2e / "full.yaml").write_text(
        "schema_version: 1\n"
        "id: billing-e2e\n"
        "name: Billing end to end\n"
        "implementation_status: IMPLEMENTED\n"
        "enabled: true\n"
        "approved: true\n"
        "evidence_policy: full-e2e\n"
        "steps:\n"
        "  - id: run-bruno\n"
        "    kind: api_suite\n"
        "    target: billing-bruno\n"
        "    depends_on: []\n"
        "  - id: check-db\n"
        "    kind: database_assertion\n"
        "    target: order-row\n"
        "    depends_on: [run-bruno]\n"
        "  - id: check-event\n"
        "    kind: kafka_assertion\n"
        "    target: order-created\n"
        "    depends_on: [run-bruno]\n",
        encoding="utf-8",
    )


def _config(workspace: Path, *, dry_run: bool = False, timeout: int = 5) -> HubConfig:
    return HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={
            "alpha": ProfileConfig(
                workspace_id="ws",
                execution=ExecutionOverrides(
                    timeout_seconds=timeout,
                    max_concurrency=1,
                    dry_run=dry_run,
                    allow_mutations=False,
                ),
            ),
            "beta": ProfileConfig(workspace_id="ws"),
        },
        workspaces=(QAWorkspaceReference(id="ws", path=str(workspace)),),
        execution=ExecutionPreferences(dry_run=True, timeout_seconds=30),
    )


def _service(
    tmp_path: Path,
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str,
    dry_run: bool = False,
    timeout: int = 5,
    secrets: dict[str, str] | None = None,
) -> ExecutionService:
    script = _fake(tmp_path / "bin", mode)
    monkeypatch.setenv("QA_MCP_BRUNO_BIN", str(script))
    monkeypatch.setenv("QA_MCP_NEWMAN_BIN", str(script))
    monkeypatch.setenv("QA_MCP_EXECUTION_PATH", str(tmp_path / "runs.sqlite"))
    config = _config(workspace, dry_run=dry_run, timeout=timeout)
    return ExecutionService(
        ExecutionStore(tmp_path / "runs.sqlite"),
        clock=lambda: _NOW,
        config_loader=lambda: config,
        id_factory=lambda: "run-1",
        secrets=None if secrets is None else secrets.get,
    )


def _run(
    service: ExecutionService,
    *,
    workflow_id: str | None = None,
    suite_id: str | None = None,
    execute: bool = True,
    environment: str | None = None,
    profile: str | None = None,
    wait: bool = True,
):
    return service.submit(
        workflow_id=workflow_id,
        suite_id=suite_id,
        execute=execute,
        environment=environment,
        profile=profile,
        wait=wait,
    )


def test_bruno_and_postman_pass_and_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _collection(workspace)
    _init_git(workspace)
    service = _service(tmp_path, workspace, monkeypatch, mode="pass")
    passed = _run(service, suite_id="billing-bruno")
    assert passed.run is not None
    assert passed.run.status is ExecutionStatus.passed
    assert passed.run.runner_completed is True
    assert passed.run.evidence.database_verified is False
    assert passed.run.evidence.kafka_verified is False
    assert passed.run.evidence.assertion_total == 1
    assert passed.run.source_revision == _git(workspace, "rev-parse", "HEAD")
    assert "VERIFYING" in passed.run.transitions
    (tmp_path / "bin" / "mode.txt").write_text("fail-zero", encoding="utf-8")
    service._ids = lambda: "run-2"  # noqa: SLF001
    failed = _run(service, suite_id="billing-postman")
    assert failed.run is not None
    assert failed.run.status is ExecutionStatus.failed
    assert failed.run.runner_completed is True
    assert failed.run.assertion_status is ExecutionStatus.failed


def test_failure_exit_invalid_output_and_missing_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _collection(workspace)
    service = _service(tmp_path, workspace, monkeypatch, mode="fail")
    failed = _run(service, suite_id="billing-bruno")
    assert failed.run is not None
    assert failed.run.status is ExecutionStatus.failed
    assert failed.run.runner_completed is False
    (tmp_path / "bin" / "mode.txt").write_text("nonzero", encoding="utf-8")
    service._ids = lambda: "run-2"  # noqa: SLF001
    errored = _run(service, suite_id="billing-bruno")
    assert errored.run is not None
    assert errored.run.status is ExecutionStatus.error
    assert errored.run.assertion_status is ExecutionStatus.passed
    (tmp_path / "bin" / "mode.txt").write_text("invalid", encoding="utf-8")
    service._ids = lambda: "run-3"  # noqa: SLF001
    invalid = _run(service, suite_id="billing-bruno")
    assert invalid.run is not None
    assert invalid.run.status is ExecutionStatus.error
    (tmp_path / "bin" / "mode.txt").write_text("no-assert", encoding="utf-8")
    service._ids = lambda: "run-4"  # noqa: SLF001
    empty = _run(service, suite_id="billing-bruno")
    assert empty.run is not None
    assert empty.run.status is ExecutionStatus.inconclusive
    (tmp_path / "bin" / "mode.txt").write_text("summary", encoding="utf-8")
    service._ids = lambda: "run-5"  # noqa: SLF001
    summary = _run(service, suite_id="billing-bruno")
    assert summary.run is not None
    assert summary.run.status is not ExecutionStatus.passed
    monkeypatch.setenv("QA_MCP_BRUNO_BIN", str(tmp_path / "missing-bru"))
    service._ids = lambda: "run-6"  # noqa: SLF001
    missing = _run(service, suite_id="billing-bruno")
    assert missing.run is not None
    assert missing.run.status is ExecutionStatus.error
    assert missing.run.runner_completed is False


def test_timeout_cancellation_and_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _collection(workspace)
    timed_out = _service(
        tmp_path / "timeout", workspace, monkeypatch, mode="sleep", timeout=1
    )
    timed = _run(timed_out, suite_id="billing-bruno")
    assert timed.run is not None
    assert timed.run.status is ExecutionStatus.timed_out
    (tmp_path / "timeout" / "bin" / "mode.txt").write_text("sleep", encoding="utf-8")
    cancelling = _service(
        tmp_path / "cancel", workspace, monkeypatch, mode="sleep", timeout=30
    )
    started = _run(cancelling, suite_id="billing-bruno", wait=False)
    assert started.run is not None
    cancelled = cancelling.cancel(started.run.execution_id)
    assert cancelled.status is ExecutionStatus.cancelled
    with pytest.raises(HubError) as blocked:
        _run(cancelling, suite_id="billing-bruno", environment="prod")
    assert blocked.value.code == "unsupported_environment"


def test_registry_and_workflow_rejections(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    _collection(workspace)
    document = load_suite_registry(workspace)
    original = (workspace / "suites" / "suites.yaml").read_text(encoding="utf-8")
    extra = (
        "  - id: billing-bruno\n"
        "    runner: bruno\n"
        "    path: suites/bruno/billing\n"
        "    enabled: true\n"
    )
    (workspace / "suites" / "suites.yaml").write_text(
        original + extra,
        encoding="utf-8",
    )
    with pytest.raises(HubError) as duplicate:
        load_suite_registry(workspace)
    assert duplicate.value.code == "duplicate_suite"
    (workspace / "workflows" / "api" / "copy.yaml").write_text(
        (workspace / "workflows" / "api" / "billing.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    service = ExecutionService(
        ExecutionStore(tmp_path / "runs.sqlite"),
        config_loader=lambda: _config(workspace),
    )
    with pytest.raises(HubError) as workflows:
        service.list_workflows()
    assert workflows.value.code == "duplicate_workflow"
    suites = {item.id: item for item in document.suites}
    cycled = WorkflowDefinition(
        schema_version=1,
        id="cycle",
        name="Cycle",
        implementation_status="IMPLEMENTED",
        enabled=True,
        approved=True,
        evidence_policy="api-only",
        steps=(
            WorkflowStep(
                id="one",
                kind=StepKind.api_suite,
                target="billing-bruno",
                depends_on=("two",),
            ),
            WorkflowStep(
                id="two",
                kind=StepKind.api_suite,
                target="billing-bruno",
                depends_on=("one",),
            ),
        ),
    )
    with pytest.raises(HubError) as cycle:
        validate_workflow(cycled, suites)
    assert cycle.value.code == "workflow_cycle"
    missing = cycled.model_copy(
        update={
            "steps": (
                WorkflowStep(
                    id="one",
                    kind=StepKind.api_suite,
                    target="billing-bruno",
                    depends_on=(),
                    assertion_ids=("missing-check",),
                ),
            )
        }
    )
    with pytest.raises(HubError) as assertion:
        validate_workflow(missing, suites)
    assert assertion.value.code == "missing_assertion"


def test_redaction_preview_and_argument_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _collection(workspace, credentials=True)
    service = _service(
        tmp_path,
        workspace,
        monkeypatch,
        mode="leak",
        secrets={"billing-token": _RUNNER_VALUE},
    )
    preview = _run(service, workflow_id="billing-api", execute=False)
    assert preview.executed is False
    assert preview.plan is not None
    assert preview.plan.executed is False
    assert preview.plan.api_only is True
    assert not (tmp_path / "bin" / "argv.json").exists()
    with pytest.raises(HubError) as injected:
        bruno_arguments(
            report_path=tmp_path / "report.json",
            environment="local;rm",
            env_file=None,
        )
    assert injected.value.code == "argv_rejected"
    import inspect

    assert "shell" not in inspect.signature(run_process).parameters
    assert "command" not in inspect.signature(submit_test_run_tool).parameters
    finished = _run(service, workflow_id="billing-api", execute=True)
    assert finished.run is not None
    assert finished.run.status is ExecutionStatus.passed
    blob = (tmp_path / "runs.sqlite").read_bytes()
    assert _RUNNER_VALUE.encode() not in blob
    argv = json.loads((tmp_path / "bin" / "argv.json").read_text(encoding="utf-8"))
    assert _RUNNER_VALUE not in json.dumps(argv)
    assert "--env-var" not in argv
    assert not list((tmp_path / "runs").rglob("runner-env.json"))


def test_e2e_preview_does_not_claim_database_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _collection(workspace)
    service = _service(tmp_path, workspace, monkeypatch, mode="pass")
    receipt = _run(service, workflow_id="billing-e2e", execute=True)
    assert receipt.executed is False
    assert receipt.plan is not None
    assert receipt.plan.database_verified is False
    assert receipt.plan.kafka_verified is False
    blocked = [
        step
        for step in receipt.plan.steps
        if step.reason == "unavailable_until_milestone_07"
    ]
    assert blocked
    assert not (tmp_path / "bin" / "argv.json").exists()
    workflows, candidates = service.list_workflows(
        issue_key=None, changed_paths=("suites/bruno/billing",)
    )
    assert workflows
    assert candidates
    assert candidates[0].approved is False
    with pytest.raises(HubError) as unknown:
        service.explain(candidates[0].id)
    assert unknown.value.code == "unknown_workflow"


def test_contexts_are_immutable_and_runs_stay_serialized() -> None:
    context = ExecutionContext(
        execution_id="run-a",
        profile_id="alpha",
        workflow_id="billing-api",
        suite_ids=("billing-bruno",),
        suite_version="1",
        source_revision=None,
        timeout_seconds=5,
        environment="local",
        allow_mutations=False,
    )
    with pytest.raises(ValidationError):
        context.timeout_seconds = 1
    manager = JobManager(1)
    other = context.model_copy(update={"execution_id": "run-b", "suite_version": "2"})
    manager.register(context.execution_id)
    manager.register(other.execution_id)
    seen: list[str] = []

    def action(ctx: ExecutionContext, event: threading.Event) -> None:
        del event
        time.sleep(0.2)
        seen.append(ctx.suite_version)

    threads = [
        threading.Thread(
            target=manager.run,
            args=(item, action),
            kwargs={"wait": True},
        )
        for item in (context, other)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2)
    assert manager.peak == 1
    assert seen == ["1", "2"] or seen == ["2", "1"]
    with pytest.raises(HubError):
        transition(ExecutionStatus.passed, ExecutionStatus.failed)
    with pytest.raises(HubError):
        poll_until(
            lambda: True,
            timeout_seconds=61,
            interval_seconds=0.01,
            max_attempts=1,
        )


def test_profile_isolation_and_corrupt_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _collection(workspace)
    service = _service(tmp_path, workspace, monkeypatch, mode="pass")
    finished = _run(service, suite_id="billing-bruno")
    assert finished.run is not None
    with pytest.raises(HubError) as missing:
        service.get_run(finished.run.execution_id, profile="beta")
    assert missing.value.code == "unknown_execution"
    broken = tmp_path / "broken.sqlite"
    broken.write_text("not a database", encoding="utf-8")
    store = ExecutionStore(broken)
    assert store.recovery_warning == "execution_store_recovered"


def test_template_workspace_is_not_executable(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "templates" / "qa-workspace"
    service = ExecutionService(
        ExecutionStore(tmp_path / "runs.sqlite"),
        config_loader=lambda: _config(root),
    )
    catalog = service.list_suites()
    service.close()
    assert catalog.executable is False
    assert {item.id for item in catalog.suites} == {
        "example-api-smoke",
        "example-postman-smoke",
    }
    assert all(item.found for item in catalog.discovered)


@pytest.mark.asyncio
async def test_mcp_execution_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _collection(workspace)
    script = _fake(tmp_path / "bin", "pass")
    monkeypatch.setenv("QA_MCP_BRUNO_BIN", str(script))
    monkeypatch.setenv("QA_MCP_NEWMAN_BIN", str(script))
    monkeypatch.setenv("QA_MCP_EXECUTION_PATH", str(tmp_path / "runs.sqlite"))
    config = _config(workspace, dry_run=False)
    monkeypatch.setattr(
        "qa_mcp_hub.workflows.service.load_config", lambda path=None: config
    )
    async with Client(mcp) as client:
        listed = await client.call_tool("list_registered_suites", {})
        assert listed.structured_content is not None
        assert listed.structured_content["executable"] is True
        explained = await client.call_tool(
            "explain_workflow", {"workflow_id": "billing-api"}
        )
        assert explained.structured_content is not None
        assert explained.structured_content["executed"] is False
        assert explained.structured_content["database_verified"] is False
        preview = await client.call_tool(
            "submit_test_run", {"workflow_id": "billing-api", "execute": False}
        )
        assert preview.structured_content is not None
        assert preview.structured_content["executed"] is False
        submitted = await client.call_tool(
            "submit_test_run", {"suite_id": "billing-bruno", "execute": True}
        )
        assert submitted.structured_content is not None
        assert submitted.structured_content["executed"] is True
        run = submitted.structured_content["run"]
        assert run["status"] == "PASSED"
        assert run["evidence"]["database_verified"] is False
        assert run["evidence"]["kafka_verified"] is False
        loaded = await client.call_tool(
            "get_test_run", {"execution_id": run["execution_id"]}
        )
        assert loaded.structured_content is not None
        assert loaded.structured_content["status"] == "PASSED"
