"""MCP knowledge tools against a local Git fixture. No provider network call."""

import shutil
import subprocess
from pathlib import Path

import pytest
from fastmcp import Client

from qa_mcp_hub.config.models import (
    CURRENT_SCHEMA_VERSION,
    HubConfig,
    ProfileConfig,
    QAWorkspaceReference,
    RepositoryReference,
)
from qa_mcp_hub.core.enums import IndexingPermission
from qa_mcp_hub.server import mcp


def _git(repo: Path, *args: str) -> None:
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


@pytest.mark.asyncio
async def test_mcp_knowledge_tools_keep_source_text_untrusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "alpha" / "billing"
    repo.mkdir(parents=True)
    executable = shutil.which("git")
    if executable is None:
        pytest.skip("git is not available")
    subprocess.run(  # noqa: S603 - git init with a fixed argument list
        [executable, "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "user.name", "QA")
    (repo / "billing.py").write_text(
        "def charge():\n    return 'QA-12'\n",
        encoding="utf-8",
    )
    _git(repo, "add", "billing.py")
    _git(repo, "commit", "-m", "initial")
    config = HubConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        active_profile="alpha",
        profiles={
            "alpha": ProfileConfig(
                workspace_id="alpha-workspace",
                repository_ids=("billing",),
            )
        },
        workspaces=(
            QAWorkspaceReference(id="alpha-workspace", path=str(tmp_path / "alpha")),
        ),
        repositories=(
            RepositoryReference(
                id="billing",
                display_name="Billing",
                path=str(repo),
                indexing=IndexingPermission.content,
            ),
        ),
    )
    monkeypatch.setenv("QA_MCP_INDEX_PATH", str(tmp_path / "index.sqlite"))
    monkeypatch.setattr(
        "qa_mcp_hub.knowledge.service.load_config",
        lambda path=None: config,
    )
    async with Client(mcp) as client:
        found = await client.call_tool("search_knowledge", {"query": "charge"})
        assert found.structured_content is not None
        assert found.structured_content["untrusted_content"] is True
        assert found.structured_content["hits"]
        assert found.structured_content["hits"][0]["citation"]["commit_sha"]
        implementation = await client.call_tool(
            "find_implementation",
            {"issue_key": "QA-12"},
        )
        assert implementation.structured_content is not None
        assert implementation.structured_content["complete_graph"] is False
        assert implementation.structured_content["relationship"] == "INFERRED"
        trace = await client.call_tool(
            "trace_cross_repo_flow",
            {"symbol": "charge"},
        )
        assert trace.structured_content is not None
        assert trace.structured_content["complete_graph"] is False
        draft = await client.call_tool(
            "generate_test_scenario_draft",
            {"issue_key": "QA-12", "requirements": ["charge returns QA-12"]},
        )
        assert draft.structured_content is not None
        assert draft.structured_content["executable"] is False
        assert draft.structured_content["workflow_created"] is False
        impact = await client.call_tool(
            "analyze_change_impact",
            {"repository_id": "billing", "paths": ["billing.py"]},
        )
        assert impact.structured_content is not None
        assert impact.structured_content["complete_graph"] is False
