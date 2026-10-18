"""Store evidence artifacts inside one approved directory.

Purpose: reject traversal, overwrite, and writes outside the evidence root.
Milestone: 10
Status: IMPLEMENTED
Ownership: storage.artifact_store
Dependencies: Path allowlist and artifact digests.
Expected tests: traversal, overwrite, and identical-byte retry.
"""

import os
from pathlib import Path

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.evidence.manifest import digest_bytes
from qa_mcp_hub.security.path_allowlist import resolve_within

_NAMES = frozenset(
    {
        "manifest.json",
        "release.html",
        "release.json",
        "report.html",
        "report.json",
        "summary.html",
        "styles.css",
    }
)


class ArtifactStore:
    """Content-checked files under ``workspace/evidence/artifacts``."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.root = workspace / "evidence" / "artifacts"

    def write(self, execution_id: str, name: str, content: bytes) -> bool:
        """Write one artifact. Identical bytes are kept. Different bytes fail."""
        path = self._path(execution_id, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if digest_bytes(path.read_bytes()) == digest_bytes(content):
                return False
            raise HubError("artifact_rejected", "evidence artifact already exists")
        temporary = path.with_suffix(path.suffix + ".partial")
        temporary.write_bytes(content)
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        os.chmod(path, 0o600)
        return True

    def read(self, execution_id: str, name: str) -> bytes:
        """Read one previously stored artifact."""
        path = self._path(execution_id, name)
        if not path.is_file():
            raise HubError("artifact_rejected", "evidence artifact is missing")
        return path.read_bytes()

    def _path(self, execution_id: str, name: str) -> Path:
        if not execution_id.replace("-", "").replace("_", "").isalnum():
            raise HubError("path_rejected", "execution id is not a safe path")
        if name not in _NAMES or "/" in name or "\\" in name:
            raise HubError("path_rejected", "artifact name is not allowed")
        return resolve_within(self.root / execution_id / name, [self.root])
